from pisek.jobs.jobs import Job
from pisek.jobs.status import StatusJobManager
from pisek.jobs.job_pipeline import JobPipeline
from pisek.utils.paths import IInputPath, IOutputPath, IRawPath

from pisek.task_jobs.tools import sanitize_job, sanitize_job_direct
from pisek.task_jobs.data.testcase_info import TestcaseInfo, TestcaseGenerationMode
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


class InputManager(StatusJobManager):
    def __init__(self, input_: IInputPath, info: TestcaseInfo, seed: int | None):
        super().__init__(f"Generate input {input_:n}")
        self._input = input_
        self._info = info
        self._seed = seed

    def _get_jobs(self) -> list[Job]:
        if self._info.generation_mode == TestcaseGenerationMode.generated:
            jobs: list[Job] = [
                gen := generate_input_direct(
                    self._env, self._info, self._seed, self._input
                ),
            ]
        else:
            raise NotImplementedError()

        sanitize = sanitize_job(self._env, self._input, True)
        if sanitize is not None:
            jobs.append(sanitize)
            sanitize.add_prerequisite(gen)

        return jobs


class OutputManager(StatusJobManager):
    def __init__(self, input_: IInputPath, info: TestcaseInfo, output: IOutputPath):
        self._input = input_
        self._info = info
        self._output = output
        super().__init__(f"Generate output {self._output:n}")

    def _get_jobs(self) -> list[Job]:
        if self._info.generation_mode == TestcaseGenerationMode.static:
            raise NotImplementedError()
        else:
            jobs: list[Job] = [
                solve := RunBatchSolution(
                    self._env,
                    self._env.config.solutions[self._env.config.primary_solution].run,
                    True,
                    self._input,
                    self._output,
                ),
            ]

        sanitize = sanitize_job(self._env, self._output, False)
        if sanitize is not None:
            jobs.append(sanitize)
            sanitize.add_prerequisite(solve, name="create-source")

        return jobs


class CheckerManager(StatusJobManager):
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
