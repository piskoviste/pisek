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

from abc import abstractmethod
from decimal import Decimal
from typing import Optional
from functools import cache

from pisek.utils.text import tab
from pisek.utils.paths import InputPath, OutputPath, LogPath
from pisek.env.env import Env
from pisek.jobs.jobs import State, PipelineItemFailure
from pisek.task_jobs.run_result import RunResult, RunResultKind
from pisek.task_jobs.program import ProgramsJob
from pisek.task_jobs.solution.solution_result import (
    Verdict,
    SolutionResult,
    RelativeSolutionResult,
    AbsoluteSolutionResult,
)


class RunChecker(ProgramsJob):
    """Runs checker on single input. (Abstract class)"""

    def __init__(
        self,
        env: Env,
        name: str,
        test: int,
        judge_name: str,
        input_: InputPath,
        judge_log_file: LogPath,
        expected_verdict: Optional[Verdict],
        **kwargs,
    ) -> None:
        super().__init__(env=env, name=name, **kwargs)
        self.test = test
        self.input = input_
        self.judge_name = judge_name
        self.judge_log_file = judge_log_file
        self.expected_verdict = expected_verdict

        self.result: Optional[SolutionResult]

    @cache
    def _load_solution_run_res(self) -> None:
        """
        Loads solution's RunResult into self.solution_res
        """
        self._solution_run_res = self._get_solution_run_res()

    @abstractmethod
    def _get_solution_run_res(self) -> RunResult:
        """
        Gets solution's RunResult.
        Call this only through _load_solution_run_res as this can run the solution.
        """
        pass

    @abstractmethod
    def _judge(self) -> SolutionResult:
        """Here actually do the judging."""
        pass

    @abstractmethod
    def _judging_message(self) -> str:
        pass

    def _judging_message_capitalized(self) -> str:
        msg = self._judging_message()
        return msg[0].upper() + msg[1:]

    def _run(self) -> SolutionResult:
        self._load_solution_run_res()
        if self._solution_run_res.kind == RunResultKind.OK:
            result = self._judge()
        elif self._solution_run_res.kind == RunResultKind.RUNTIME_ERROR:
            result = RelativeSolutionResult(
                Verdict.error, None, self._solution_run_res, None, Decimal(0)
            )
        elif self._solution_run_res.kind == RunResultKind.TIMEOUT:
            result = RelativeSolutionResult(
                Verdict.timeout, None, self._solution_run_res, None, Decimal(0)
            )

        if (
            self.expected_verdict is not None
            and result.verdict != self.expected_verdict
        ):
            raise PipelineItemFailure(
                f"{self._judging_message_capitalized()} should have got verdict '{self.expected_verdict}' but got '{result.verdict}'."
            )

        return result

    def message(self) -> str:
        """Message about how judging ended."""
        if self.result is None:
            raise RuntimeError(f"Job {self.name} has not finished yet.")

        sol_rr = self.result.solution_rr
        judge_rr = self.result.judge_rr

        text = f"input: {self._quote_file_with_name(self.input)}"
        if isinstance(self, RunBatchChecker):
            text += f"correct output: {self._quote_file_with_name(self.correct_output)}"
        text += f"result: {self.result.verdict.name}\n"

        text += "solution:\n"
        text += tab(
            self._format_run_result(
                sol_rr,
                status=sol_rr.kind != RunResultKind.OK,
                stderr_force_content=sol_rr.kind == RunResultKind.RUNTIME_ERROR,
                time=True,
            )
        )
        text += "\n"
        if judge_rr is not None:
            text += (
                f"{self.judge_name}:\n"
                + tab(
                    self._format_run_result(
                        judge_rr,
                        status=judge_rr.stderr_file is None,
                        stderr_force_content=True,
                    )
                )
                + "\n"
            )

        return text

    def verdict_text(self) -> str:
        if self.result is not None:
            if self.result.message is not None:
                return self.result.message
            return self.result.verdict.name
        else:
            return self.state.name

    def verdict_mark(self) -> str:
        if self.state == State.cancelled:
            return "-"
        elif self.result is None:
            return " "
        elif self.result.verdict == Verdict.partial_ok:
            if isinstance(self.result, RelativeSolutionResult):
                return f"[{self.result.relative_points:.2f}]"
            elif isinstance(self.result, AbsoluteSolutionResult):
                return f"[={self.result.absolute_points:.{self._env.config.score_precision}f}]"
            else:
                raise ValueError(
                    f"Unexpected SolutionResult type: '{type(self.result)}'"
                )
        else:
            return self.result.verdict.mark()

    @property
    def full_points(self) -> float:
        return self.rel_to_abs_points(1.0)

    def rel_to_abs_points(self, rel_points: float) -> float:
        return self._env.config.tests[self.test].points * rel_points


class RunBatchChecker(RunChecker):
    """Runs batch judge on single input. (Abstract class)"""

    def __init__(
        self,
        env: Env,
        judge_name: str,
        test: int,
        input_: InputPath,
        output: OutputPath,
        correct_output: OutputPath,
        expected_verdict: Optional[Verdict],
        **kwargs,
    ) -> None:
        super().__init__(
            env=env,
            name=f"Judge {output:p}",
            judge_name=judge_name,
            test=test,
            input_=input_,
            judge_log_file=output.to_judge_log(judge_name),
            expected_verdict=expected_verdict,
            **kwargs,
        )
        self.output = output
        self.correct_output_name = correct_output
        self.correct_output = correct_output

    def _get_solution_run_res(self) -> RunResult:
        if "run_solution" in self.prerequisites_results:
            return self.prerequisites_results["run_solution"]
        else:
            # There is no solution (judging samples)
            # XXX: It didn't technically finish in 0 time.
            return RunResult(RunResultKind.OK, 0, 0.0, 0.0)

    def _judging_message(self) -> str:
        return f"output {self.output:p} for input {self.input:p}"
