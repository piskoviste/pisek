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
from pisek.utils.paths import IInputPath, IOutputPath, LogPath
from pisek.env.env import Env
from pisek.config.config_types import DataFormat
from pisek.task_jobs.tools import SanitizationResultKind
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
        checker_name: str,
        input_: IInputPath,
        checker_log_file: LogPath,
        expected_verdict: Optional[Verdict],
        **kwargs,
    ) -> None:
        super().__init__(env=env, name=name, **kwargs)
        self.test = test
        self.input = input_
        self.checker_name = checker_name
        self.checker_log_file = checker_log_file
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
    def _check(self) -> SolutionResult:
        """Here actually do the output checking."""
        pass

    @abstractmethod
    def _checking_message(self) -> str:
        pass

    def _checking_message_capitalized(self) -> str:
        msg = self._checking_message()
        return msg[0].upper() + msg[1:]

    def _run(self) -> SolutionResult:
        self._load_solution_run_res()
        result = self._get_solution_result()

        if (
            self.expected_verdict is not None
            and result.verdict != self.expected_verdict
        ):
            raise PipelineItemFailure(
                f"{self._checking_message_capitalized()} should have got verdict '{self.expected_verdict}' but got '{result.verdict}'."
            )

        return result

    def _get_solution_result(self) -> SolutionResult:
        if self._solution_run_res.kind == RunResultKind.OK:
            out_form = self._env.config.tests.out_format
            san_res = self.prerequisites_results.get("sanitize")
            if san_res is None:
                pass
            elif san_res.kind == SanitizationResultKind.invalid:
                return RelativeSolutionResult(
                    verdict=Verdict.normalization_fail,
                    message=san_res.msg,
                    solution_rr=self._solution_run_res,
                    checker_rr=None,
                    relative_points=Decimal(0),
                )
            elif (
                out_form == DataFormat.strict_text
                and san_res.kind == SanitizationResultKind.changed
            ):
                return RelativeSolutionResult(
                    verdict=Verdict.normalization_fail,
                    message=f"Output not normalized. (Check encoding, missing newline at the end or '\\r'.)",
                    solution_rr=self._solution_run_res,
                    checker_rr=None,
                    relative_points=Decimal(0),
                )

            return self._check()
        elif self._solution_run_res.kind == RunResultKind.RUNTIME_ERROR:
            return RelativeSolutionResult(
                verdict=Verdict.error,
                message=None,
                solution_rr=self._solution_run_res,
                checker_rr=None,
                relative_points=Decimal(0),
            )
        elif self._solution_run_res.kind == RunResultKind.TIMEOUT:
            return RelativeSolutionResult(
                verdict=Verdict.timeout,
                message=None,
                solution_rr=self._solution_run_res,
                checker_rr=None,
                relative_points=Decimal(0),
            )

        raise ValueError(
            f"Invalid solution run result kind: '{self._solution_run_res.kind}'"
        )

    def message(self) -> str:
        """Message about how checking ended."""
        if self.result is None:
            raise RuntimeError(f"Job {self.name} has not finished yet.")

        sol_rr = self.result.solution_rr
        checker_rr = self.result.checker_rr

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
        if checker_rr is not None:
            text += (
                f"{self.checker_name}:\n"
                + tab(
                    self._format_run_result(
                        checker_rr,
                        status=checker_rr.stderr_file is None,
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
        else:
            return self.result.verdict.mark


class RunBatchChecker(RunChecker):
    """Runs batch checker on single input. (Abstract class)"""

    def __init__(
        self,
        env: Env,
        checker_name: str,
        test: int,
        input_: IInputPath,
        output: IOutputPath,
        correct_output: IOutputPath,
        expected_verdict: Optional[Verdict],
        **kwargs,
    ) -> None:
        super().__init__(
            env=env,
            name=f"Check {output:p}",
            checker_name=checker_name,
            test=test,
            input_=input_,
            checker_log_file=output.to_checker_log(checker_name),
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
            # There is no solution (checking static tests against themselves)
            # XXX: It didn't technically finish in 0 time.
            return RunResult(RunResultKind.OK, 0, 0.0, 0.0)

    def _checking_message(self) -> str:
        return (
            f"output {self.output.col(self._env)} for input {self.input.col(self._env)}"
        )
