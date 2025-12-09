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

from typing import Optional

from pisek.jobs.job_pipeline import JobPipeline
from pisek.env.env import Env, TestingTarget
from pisek.config.config_types import TaskType, OutCheck
from pisek.utils.paths import InputPath
from pisek.task_jobs.task_manager import (
    TOOLS_MAN_CODE,
    INPUTS_MAN_CODE,
    BUILD_MAN_CODE,
    GENERATOR_MAN_CODE,
    FUZZ_MAN_CODE,
    SOLUTION_MAN_CODE,
)

from pisek.jobs.jobs import JobManager
from pisek.task_jobs.tools import ToolsManager
from pisek.task_jobs.data.data_manager import DataManager
from pisek.task_jobs.generator.generator_manager import (
    PrepareGenerator,
    RunGenerator,
    TestcaseInfoMixin,
)
from pisek.task_jobs.checker.fuzzing_manager import FuzzingManager
from pisek.task_jobs.builder.build import BuildManager
from pisek.task_jobs.solution.ui_managers import EmptyLineManager, TestsHeaderManager
from pisek.task_jobs.solution.solution_manager import SolutionManager
from pisek.task_jobs.testing_log import CreateTestingLog
from pisek.task_jobs.completeness_check import CompletenessCheck


class TaskPipeline(JobPipeline):
    """JobPipeline that checks whether task behaves as expected."""

    def __init__(self, env: Env):
        super().__init__()
        self.job_managers = [job_man for job_man, _ in self._get_named_pipeline(env)]

    def _get_named_pipeline(self, env: Env) -> list[tuple[JobManager, str]]:
        named_pipeline: list[tuple[JobManager, str]] = [
            tools := (ToolsManager(), TOOLS_MAN_CODE),
            build := (BuildManager(), BUILD_MAN_CODE),
        ]
        build[0].add_prerequisite(*tools)
        if env.config.tests.in_gen is not None:
            named_pipeline.append(generator := (PrepareGenerator(), GENERATOR_MAN_CODE))
            generator[0].add_prerequisite(*build)
        named_pipeline.append(inputs := (DataManager(), INPUTS_MAN_CODE))

        inputs[0].add_prerequisite(*build)
        if env.config.tests.in_gen is not None:
            inputs[0].add_prerequisite(*generator)

        if env.target == TestingTarget.build:
            return named_pipeline

        solutions = []
        self.input_generator: TestcaseInfoMixin

        if env.target == TestingTarget.generator or not env.config.solutions:
            named_pipeline.append(gen_inputs := (RunGenerator(), ""))
            gen_inputs[0].add_prerequisite(*inputs)
            self.input_generator = gen_inputs[0]

        else:
            # First solution generates inputs
            assert (
                not env.config.tests.judge_needs_out
                or env.solutions[0] == env.config.primary_solution
            )

            named_pipeline.append((EmptyLineManager(), ""))
            if env.verbosity == 0:
                named_pipeline.append(th := (TestsHeaderManager(), ""))
                th[0].add_prerequisite(*inputs)

            named_pipeline.append(
                first_solution := (
                    SolutionManager(env.solutions[0], True),
                    f"{SOLUTION_MAN_CODE}{env.solutions[0]}",
                )
            )
            solutions.append(first_solution)
            self.input_generator = first_solution[0]

            for sol_name in env.solutions[1:]:
                named_pipeline.append(
                    solution := (
                        SolutionManager(sol_name, False),
                        f"{SOLUTION_MAN_CODE}{sol_name}",
                    )
                )

                solution[0].add_prerequisite(*first_solution)
                solutions.append(solution)

            for solution in solutions:
                solution[0].add_prerequisite(*inputs)

            if env.verbosity == 0:
                named_pipeline.append((EmptyLineManager(), ""))

        if env.testing_log:
            named_pipeline.append(testing_log := (CreateTestingLog(), ""))
            for solution in solutions:
                testing_log[0].add_prerequisite(*solution)

        fuzz_judge: tuple[Optional[FuzzingManager], Optional[str]]
        if (
            env.target == TestingTarget.all
            and env.config.solutions
            and env.config.task.task_type != TaskType.interactive
            and env.config.tests.out_check == OutCheck.judge
            and (
                env.config.checks.fuzzing_thoroughness > 0
                or env.config.checks.judge_rejects_trailing_string
            )
        ):
            named_pipeline.append(fuzz_judge := (FuzzingManager(), FUZZ_MAN_CODE))
            fuzz_judge[0].add_prerequisite(*first_solution)
        else:
            fuzz_judge = (None, None)

        if solutions and env.target == TestingTarget.all:
            named_pipeline.append(completeness_check := (CompletenessCheck(), ""))
            completeness_check[0].add_prerequisite(*fuzz_judge)
            for solution in solutions:
                completeness_check[0].add_prerequisite(*solution)

        return named_pipeline

    def input_dataset(self) -> list[InputPath]:
        if self.input_generator.result is None:
            raise RuntimeError("Input dataset has not been computed yet.")
        return self.input_generator.result["input_dataset"]
