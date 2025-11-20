# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2023        Daniel Skýpala <daniel@honza.info>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from typing import Optional

from pisek.env.env import Env
from pisek.config.config_types import ProgramRole
from pisek.config.task_config import RunSection
from pisek.utils.paths import IInputPath
from pisek.task_jobs.program import ProgramsJob, RunResultKind
from pisek.task_jobs.data.testcase_info import TestcaseInfo

from .base_classes import GeneratorListInputs, GenerateInput, GeneratorTestDeterminism


class OpendataV1ListInputs(GeneratorListInputs):
    """Lists all inputs for opendata-v1 generator - one for each test."""

    def __init__(self, env: Env, generator: RunSection, **kwargs) -> None:
        super().__init__(env=env, generator=generator, **kwargs)

    def _run(self) -> list[TestcaseInfo]:
        # Although for test in self._env.config.test_sections
        # would be shorter, this doesn't actually access env variables
        # and that leads to caching bug.
        return [
            TestcaseInfo.generated(f"{test:02}")
            for test in range(self._env.config.tests_count)
            if test != 0
        ]


class OpendataV1GeneratorJob(ProgramsJob):
    """Abstract class for jobs with OnlineGenerator."""

    generator: RunSection
    seed: Optional[int]
    testcase_info: TestcaseInfo
    input_path: IInputPath

    def __init__(self, env: Env, *, name: str = "", **kwargs) -> None:
        super().__init__(env=env, name=name, **kwargs)

    def _gen(self) -> None:
        assert self.seed is not None
        if self.seed < 0:
            raise ValueError(f"seed {self.seed} is negative")

        test = int(self.testcase_info.name)

        result = self._run_program(
            ProgramRole.gen,
            self.generator,
            args=[str(test), f"{self.seed:016x}"],
            stdout=self.input_path.to_raw(self._env.config.tests.in_format),
            stderr=self.input_path.to_log(self.generator.name),
        )
        if result.kind != RunResultKind.OK:
            raise self._create_program_failure(
                f"{self.generator.name} failed on test {test}, seed {self.seed:016x}:",
                result,
                stderr_force_content=True,
            )


class OpendataV1Generate(OpendataV1GeneratorJob, GenerateInput):
    """Generates input with given name."""

    pass


class OpendataV1TestDeterminism(OpendataV1GeneratorJob, GeneratorTestDeterminism):
    """Tests determinism of generating a given input."""

    pass
