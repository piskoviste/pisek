# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2019 - 2022 Václav Volhejn <vaclav.volhejn@gmail.com>
# Copyright (c)   2019 - 2022 Jiří Beneš <mail@jiribenes.com>
# Copyright (c)   2020 - 2022 Michal Töpfer <michal.topfer@gmail.com>
# Copyright (c)   2022        Jiří Kalvoda <jirikalvoda@kam.mff.cuni.cz>
# Copyright (c)   2023        Daniel Skýpala <daniel@honza.info>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from typing import cast, Any, Optional
from hashlib import blake2b

from pisek.env.env import Env
from pisek.utils.paths import IInputPath, IOutputPath
from pisek.config.config_types import GenType
from pisek.config.task_config import RunSection
from pisek.jobs.jobs import Job, JobManager
from pisek.task_jobs.task_manager import TaskJobManager
from pisek.task_jobs.data.data import InputSmall, OutputSmall
from pisek.task_jobs.tools import sanitize_job
from pisek.task_jobs.validator.validator_base import ValidatorJob
from pisek.task_jobs.validator.validators import VALIDATORS
from pisek.task_jobs.data.testcase_info import TestcaseInfo, TestcaseGenerationMode

from .base_classes import (
    GeneratorListInputs,
    GenerateInput,
    GeneratorTestDeterminism,
    GeneratorRespectsSeed,
)
from .cms_old import CmsOldListInputs, CmsOldGenerate
from .opendata_v1 import (
    OpendataV1ListInputs,
    OpendataV1Generate,
    OpendataV1TestDeterminism,
)
from .pisek_v1 import (
    PisekV1ListInputs,
    PisekV1Generate,
    PisekV1TestDeterminism,
)

SEED_BYTES = 8
SEED_RANGE = range(0, 1 << (SEED_BYTES * 8))


class PrepareGenerator(TaskJobManager):
    """Prepares generator for use."""

    def __init__(self):
        self._inputs = []
        super().__init__("Prepare generator")

    def _get_jobs(self) -> list[Job]:
        assert self._env.config.tests.in_gen is not None
        jobs: list[Job] = [
            list_inputs := list_inputs_job(self._env, self._env.config.tests.in_gen),
        ]
        self._list_inputs = list_inputs

        return jobs

    def _compute_result(self) -> dict[str, Any]:
        return {"inputs": self._list_inputs.result}


def list_inputs_job(env: Env, generator: RunSection) -> GeneratorListInputs:
    LIST_INPUTS: dict[GenType, type[GeneratorListInputs]] = {
        GenType.opendata_v1: OpendataV1ListInputs,
        GenType.cms_old: CmsOldListInputs,
        GenType.pisek_v1: PisekV1ListInputs,
    }

    assert env.config.tests.gen_type is not None
    return LIST_INPUTS[env.config.tests.gen_type](env=env, generator=generator)


def generate_input(
    env: Env, testcase_info: TestcaseInfo, seed: Optional[int]
) -> GenerateInput:
    return generate_input_direct(
        env, testcase_info, seed, testcase_info.input_path(seed)
    )


def generate_input_direct(
    env: Env, testcase_info: TestcaseInfo, seed: Optional[int], input_path: IInputPath
) -> GenerateInput:
    assert env.config.tests.in_gen is not None
    assert env.config.tests.gen_type is not None
    return {
        GenType.opendata_v1: OpendataV1Generate,
        GenType.cms_old: CmsOldGenerate,
        GenType.pisek_v1: PisekV1Generate,
    }[env.config.tests.gen_type](
        env=env,
        generator=env.config.tests.in_gen,
        testcase_info=testcase_info,
        seed=seed,
        input_path=input_path,
    )


def generator_test_determinism(
    env: Env, generator: RunSection, testcase_info: TestcaseInfo, seed: Optional[int]
) -> Optional[GeneratorTestDeterminism]:
    TEST_DETERMINISM = {
        GenType.opendata_v1: OpendataV1TestDeterminism,
        GenType.pisek_v1: PisekV1TestDeterminism,
    }

    if env.config.tests.gen_type not in TEST_DETERMINISM:
        return None
    return TEST_DETERMINISM[env.config.tests.gen_type](
        env=env, generator=generator, testcase_info=testcase_info, seed=seed
    )


class TestcaseInfoMixin(JobManager):
    def __init__(self, name: str, **kwargs) -> None:
        self.inputs: dict[str, tuple[set[int], int | None]] = {}
        self.input_dataset: set[IInputPath] = set()
        self._gen_inputs_job: dict[Optional[int], GenerateInput] = {}

        self._jobs: list[Job] = []
        self._testcase_last: Job | None = None

        super().__init__(name=name, **kwargs)

    def _add_job(
        self,
        job: Job | None,
        new_last: bool = False,
        prerequisite_name: str | None = None,
    ) -> None:
        if job is not None:
            self._jobs.append(job)
            job.add_prerequisite(self._testcase_last, prerequisite_name)
            if new_last:
                self._testcase_last = job

    def _begin_new_testcase(self) -> None:
        self._testcase_last = None

    def _get_seed(self, iteration: int, testcase_info: TestcaseInfo) -> int:
        name_hash = blake2b(digest_size=SEED_BYTES)
        name_hash.update(
            f"{self._env.iteration} {iteration} {testcase_info.name}".encode()
        )
        return int.from_bytes(name_hash.digest())

    def _add_testcase_info_jobs(self, testcase_info: TestcaseInfo, test: int) -> None:
        seeds: list[Optional[int]]
        if testcase_info.seeded:
            seeds = []
            for i in range(testcase_info.repeat):
                seeds.append(self._get_seed(i, testcase_info))
        else:
            seeds = [None]

        self._gen_inputs_job = {}

        skipped: bool = False
        for i, seed in enumerate(seeds):
            if self._skip_testcase(testcase_info, seed, test):
                skipped = True
                self._register_skipped_testcase(testcase_info, seed, test)
                continue

            self._begin_new_testcase()
            input_path = testcase_info.input_path(seed)
            self.inputs[input_path.name] = ({test}, seed)
            self.input_dataset.add(input_path)

            self._add_generate_input_jobs(testcase_info, seed, test, i == 0)
            self._add_solution_jobs(testcase_info, seed, test)

        if (
            self._env.config.checks.generator_respects_seed
            and testcase_info.seeded
            and not skipped
        ):
            self._add_respects_seed_jobs(testcase_info, cast(list[int], seeds), test)

    def _skip_testcase(
        self, testcase_info: TestcaseInfo, seed: Optional[int], test: int
    ) -> bool:
        return testcase_info.input_path(seed) in self.input_dataset

    def _register_skipped_testcase(
        self, testcase_info: TestcaseInfo, seed: Optional[int], test: int
    ) -> None:
        input_path = testcase_info.input_path(seed)
        assert self.inputs[input_path.name][1] == seed
        self.inputs[input_path.name][0].add(test)

    def _add_generate_input_jobs(
        self,
        testcase_info: TestcaseInfo,
        seed: Optional[int],
        test: int,
        test_determinism: bool,
    ) -> None:
        input_path = testcase_info.input_path(seed)

        if testcase_info.generation_mode == TestcaseGenerationMode.generated:
            self._add_job(self._generate_input_job(testcase_info, seed), new_last=True)

        if (
            testcase_info.generation_mode == TestcaseGenerationMode.generated
            and test_determinism
        ):
            assert self._env.config.tests.in_gen is not None
            self._add_job(
                generator_test_determinism(
                    self._env, self._env.config.tests.in_gen, testcase_info, seed
                )
            )

        self._check_input_jobs(input_path)

        if self._env.config.tests.validator is not None:
            for t in range(self._env.config.tests_count):
                if not self._env.config.test_sections[t].in_test(input_path.name):
                    continue
                if not self._env.config.test_sections[t].checks_validate:
                    continue

                self._add_job(
                    self._validate(
                        input_path,
                        t,
                    )
                )

    def _validate(self, input_path: IInputPath, test_num: int) -> ValidatorJob:
        assert self._env.config.tests.validator is not None
        assert self._env.config.tests.validator_type is not None

        return VALIDATORS[self._env.config.tests.validator_type](
            self._env, self._env.config.tests.validator, input_path, test_num
        )

    def _generate_input_job(
        self, testcase_info: TestcaseInfo, seed: Optional[int]
    ) -> GenerateInput:
        assert self._env.config.tests.in_gen is not None
        self._gen_inputs_job[seed] = gen_inp = generate_input(
            self._env, testcase_info, seed
        )
        return gen_inp

    def _add_solution_jobs(
        self,
        testcase_info: TestcaseInfo,
        seed: Optional[int],
        test: int,
    ) -> None:
        pass

    def _add_respects_seed_jobs(
        self, testcase_info: TestcaseInfo, seeds: list[int], test: int
    ) -> None:
        assert (
            testcase_info.generation_mode == TestcaseGenerationMode.generated
            and testcase_info.seeded
        )

        if len(seeds) == 1:
            seeds.append(seed := self._get_seed(1, testcase_info))
            self._add_job(self._generate_input_job(testcase_info, seed))

        self._add_job(
            check_seeded := GeneratorRespectsSeed(self._env, testcase_info, *seeds[:2])
        )
        for i in range(2):
            check_seeded.add_prerequisite(self._gen_inputs_job[seeds[i]])

    def _check_input_jobs(self, input_path: IInputPath) -> None:
        self._add_job(
            sanitize_job(self._env, input_path, True),
            new_last=True,
        )

        if self._env.config.limits.input_max_size != 0:
            self._add_job(InputSmall(self._env, input_path))

    def _add_check_output_jobs(
        self,
        output_path: IOutputPath,
    ) -> None:
        self._add_job(
            sanitize_job(self._env, output_path, False),
            prerequisite_name="create-source",
            new_last=True,
        )

        if self._env.config.limits.output_max_size != 0:
            self._add_job(OutputSmall(self._env, output_path))

    def _compute_result(self) -> dict[str, Any]:
        return {
            "input_dataset": list(sorted(self.input_dataset, key=lambda i: i.name)),
            "inputs": {i: (list(sorted(t)), s) for i, (t, s) in self.inputs.items()},
        }


class RunGenerator(TaskJobManager, TestcaseInfoMixin):
    def __init__(self) -> None:
        super().__init__("Run generator")

    def _get_jobs(self) -> list[Job]:
        for sub_num, inputs in self._all_testcases().items():
            for inp in inputs:
                self._add_testcase_info_jobs(inp, sub_num)

        return self._jobs
