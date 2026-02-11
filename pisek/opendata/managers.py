# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2026        Daniel Skýpala <skipy@kam.mff.cuni.cz>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from pisek.jobs.jobs import Job
from pisek.task_jobs.task_manager import TaskJobManager
from pisek.jobs.job_pipeline import JobPipeline
from pisek.utils.paths import IInputPath, IOutputPath, IRawPath

from pisek.task_jobs.tools import sanitize_job, sanitize_job_direct
from pisek.task_jobs.data.testcase_info import TestcaseInfo, TestcaseGenerationMode
from pisek.task_jobs.data.data import LinkData
from pisek.task_jobs.run_result import RunResultKind
from pisek.task_jobs.generator.generator_manager import generate_input_direct
from pisek.task_jobs.solution.solution import RunBatchSolution
from pisek.task_jobs.checker.checker import checker_job
from pisek.opendata.types import OpendataVerdict


class OpendataPipeline(JobPipeline):
    def __init__(
        self,
        gen_input: bool,
        gen_output: bool,
        check: bool,
        input_: IInputPath,
        info: TestcaseInfo,
        test: int,
        seed: int | None,
        correct_output: IOutputPath,
        contestant_output: IRawPath | None,
    ):
        super().__init__()
        self.job_managers = []

        if gen_input:
            self.job_managers.append(InputManager(input_, info, seed))

        if gen_output:
            self.job_managers.append(OutputManager(input_, info, correct_output))

        self._checker_man: CheckerManager | None = None
        if check:
            assert contestant_output is not None
            self._checker_man = CheckerManager(
                input_, test, seed, correct_output, contestant_output
            )
            self.job_managers.append(self._checker_man)

        for i in range(1, len(self.job_managers)):
            self.job_managers[i].add_prerequisite(self.job_managers[i - 1])

    @property
    def verdict(self) -> OpendataVerdict:
        assert self._checker_man is not None
        return self._checker_man.judging_result


class InputManager(TaskJobManager):
    def __init__(self, input_: IInputPath, info: TestcaseInfo, seed: int | None):
        super().__init__(f"Generate input {input_:n}")
        self._input = input_
        self._info = info
        self._seed = seed

    def _get_jobs(self) -> list[Job]:
        jobs: list[Job] = []
        if self._info.generation_mode == TestcaseGenerationMode.generated:
            jobs.append(
                gen := generate_input_direct(
                    self._env, self._info, self._seed, self._input
                )
            )
            sanitize = sanitize_job(self._env, self._input, True)
            if sanitize is not None:
                jobs.append(sanitize)
                sanitize.add_prerequisite(gen)
        else:
            jobs.append(
                LinkData(self._env, self._info.input_path(self._seed), self._input)
            )

        return jobs


class OutputManager(TaskJobManager):
    def __init__(self, input_: IInputPath, info: TestcaseInfo, output: IOutputPath):
        self._input = input_
        self._info = info
        self._output = output
        super().__init__(f"Generate output {self._output:n}")

    def _get_jobs(self) -> list[Job]:
        self._solve: RunBatchSolution | None = None
        jobs: list[Job] = []
        if self._info.generation_mode == TestcaseGenerationMode.static:
            jobs.append(
                LinkData(
                    self._env, self._info.reference_output(self._env), self._output
                )
            )
        else:
            self._solve = RunBatchSolution(
                self._env,
                self._env.config.solutions[self._env.config.primary_solution].run,
                True,
                self._input,
                self._output,
            )
            jobs.append(self._solve)
            sanitize = sanitize_job(self._env, self._output, False)
            if sanitize is not None:
                jobs.append(sanitize)
                sanitize.add_prerequisite(self._solve, name="create-source")

        return jobs

    def _evaluate(self):
        if self._solve is not None and self._solve.solution_rr.kind != RunResultKind.OK:
            raise self._create_program_failure(
                "Primary solution failed",
                self._solve.solution_rr,
                stderr_force_content=True,
            )


class CheckerManager(TaskJobManager):
    def __init__(
        self,
        input_: IInputPath,
        test: int,
        seed: int | None,
        correct_output: IOutputPath,
        contestant_output: IRawPath,
    ):
        self._input = input_
        self._test = test
        self._seed = seed
        self._correct_output = correct_output
        self._contestant_output = contestant_output
        super().__init__(f"Check {contestant_output:n}")

    def _get_jobs(self) -> list[Job]:
        jobs: list[Job] = []

        sanitize = sanitize_job_direct(
            self._env,
            self._contestant_output,
            self._contestant_output.to_sanitized_output(),
            False,
        )
        self._check = checker_job(
            self._input,
            self._contestant_output.to_sanitized_output(),
            self._correct_output,
            self._test,
            self._seed,
            None,
            self._env,
        )

        if sanitize is not None:
            jobs.append(sanitize)
            self._check.add_prerequisite(sanitize, name="sanitize")
        jobs.append(self._check)

        return jobs

    @property
    def judging_result(self) -> OpendataVerdict:
        res = self._check.result
        assert res is not None
        return OpendataVerdict(
            res.verdict,
            res.message,
            res.points(self._env, self._env.config.test_sections[self._test].points),
            res.log,
            res.note,
        )
