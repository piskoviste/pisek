from typing import Any, Optional

from pisek.env import Env
from pisek.jobs.jobs import State, Job, JobManager
from pisek.jobs.status import tab, colored
from pisek.jobs.parts.task_job import TaskJob, TaskJobManager
from pisek.jobs.parts.program import RunResult, RunResultKind, ProgramJob, Compile


class CheckerManager(TaskJobManager):
    def __init__(self):
        self.skipped_checker = ""
        super().__init__("Running checker")

    def _get_jobs(self) -> list[Job]:
        if self._env.config.checker is None:
            if self._env.strict:
                self._fail("No checker specified in config.")
                return []
            self.skipped_checker = colored(
                "Warning: No checker specified in config.\n"
                "It is recommended to set `checker` is section [tests]",
            "yellow", self._env)
        if self._env.no_checker:
            self.skipped_checker = colored("Skipping checking", "yellow", self._env)

        if self.skipped_checker != "":
            return []

        checker = self._resolve_path(self._env.config.checker)

        jobs : list[Job] = [compile := Compile(self._env).init(checker)]
        
        self.loose_subtasks = []
        for sub_num, sub in self._env.config.subtasks.items():
            if sub_num == '0':
                continue  # Skip samples
            for inp in self._subtask_inputs(sub):
                jobs.append(check := CheckerJob(self._env).init(checker, inp, sub_num, RunResultKind.OK))
                check.add_prerequisite(compile)
            if sub.predecessors:
                self.loose_subtasks.append(LooseCheckJobGroup(sub_num))
                for pred in sub.predecessors:
                    self.loose_subtasks[-1].jobs[pred] = []
                    for inp in self._subtask_new_inputs(sub):
                        jobs.append(check := CheckerJob(self._env).init(checker, inp, pred, None))
                        self.loose_subtasks[-1].jobs[pred].append(check)
                        check.add_prerequisite(compile)

        return jobs
    
    def _evaluate(self) -> Any:
        if len(self.jobs) == 0:
            return

        for loose_subtask in self.loose_subtasks:
            err = loose_subtask.failed(self._env.config.fail_mode)
            if err is not None:
                return self._fail(err)

    def _get_status(self) -> str:
        if self.skipped_checker:
            if self.state == State.succeeded:
                return self.skipped_checker
            else:
                return ""
        else:
            return super()._get_status()

class LooseCheckJobGroup:
    """
    Groups jobs on subtask where checker is run on predecessors instead.
    Checking that checker is strict enough - checking fails when run on predecessor.
    """
    def __init__(self, num: int):
        self.num = num
        self.jobs : dict[int, list[CheckerJob]] = {}

    def failed(self, fail_mode: str) -> Optional[str]:
        """Returns whether jobs resulted as expected."""
        def result_kind(job: CheckerJob) -> RunResultKind:
            if job.result is None:
                raise RuntimeError(f"Job {job.name} has not finished yet.")
            return job.result.kind

        for pred in self.jobs:
            results = list(map(result_kind, self.jobs[pred]))
            if fail_mode == "all" and RunResultKind.OK in results:
                job = self._index_job(pred, results, RunResultKind.OK)
                return (
                    f"Checker is not strict enough:\n"
                    f"All inputs of subtask {self.num} should have not passed on predecessor subtask {pred}\n"
                    f"but on input {job.input_name} did not."
                )
            if fail_mode == "any" and RunResultKind.RUNTIME_ERROR not in results:
                return (
                    f"Checker is not strict enough:\n"
                    f"An input of subtask {self.num} should have not passed on predecessor subtask {pred}\n"
                    f"but all have passed."
                )
            if RunResultKind.TIMEOUT in results:
                to_job = self._index_job(pred, results, RunResultKind.TIMEOUT)
                return (
                    f"Checker timeouted on input {to_job.input_name}, subtask {self.num}."
                )
        return None

    def _index_job(self, pred: int, results: list[RunResultKind], result: RunResultKind) -> 'CheckerJob':
        return self.jobs[pred][results.index(result)]


class CheckerJob(ProgramJob):
    """Runs checker on single input."""
    def _init(self, checker: str, input_name: str, subtask: int, expected: Optional[RunResultKind]):
        self.subtask = subtask
        self.input_name = input_name
        self.input_file = self._data(input_name)
        self.expected = expected
        super()._init(f"Check {input_name} on subtask {subtask}", checker)

    def _check(self) -> Optional[RunResult]:
        return self._run_program(
            [str(self.subtask)],
            stdin=self.input_file
        )

    def _run(self) -> Optional[RunResult]:
        result = self._check()
        if result is None:
            return None
        if self.expected == RunResultKind.OK != result.kind:
            return self._program_fail(
                f"Checker failed on {self.input_name} (subtask {self.subtask}) but should have succeeded.", result
            )
        elif self.expected == RunResultKind.RUNTIME_ERROR != result.kind:
            return self._program_fail(
                f"Checker succeeded on {self.input_name} (subtask {self.subtask}) but should have failed.", result
            )
        return result
