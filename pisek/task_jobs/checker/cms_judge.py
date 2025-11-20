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

import os
from decimal import Decimal, InvalidOperation
from typing import Optional
from tempfile import gettempdir
from uuid import uuid4

from pisek.utils.paths import IInputPath, IOutputPath
from pisek.env.env import Env
from pisek.config.task_config import RunSection
from pisek.config.config_types import ProgramRole
from pisek.task_jobs.run_result import RunResult
from pisek.task_jobs.solution.solution_result import (
    Verdict,
    SolutionResult,
    RelativeSolutionResult,
)
from pisek.task_jobs.checker.checker_base import RunChecker, RunBatchChecker


class RunCMSJudge(RunChecker):
    """Judge class with CMS helper functions"""

    def __init__(
        self,
        env: Env,
        judge: RunSection,
        **kwargs,
    ) -> None:
        super().__init__(env=env, checker_name=judge.name, **kwargs)
        self.judge = judge
        self.points_file = self.checker_log_file.replace_suffix(".points")

    def _load_points(self, result: RunResult) -> Decimal:
        with self._open_file(result.stdout_file) as f:
            points_str = f.read().split("\n")[0]
        try:
            points = Decimal(points_str)
        except (ValueError, InvalidOperation):
            raise self._create_program_failure(
                "Judge didn't write points on stdout:",
                result,
                status=False,
                stdout_force_content=True,
            )

        if not 0 <= points <= 1:
            raise self._create_program_failure(
                "Judge must give between 0 and 1 points:",
                result,
                status=False,
                stdout_force_content=True,
            )

        return points

    def _load_solution_result(self, judge_run_result: RunResult) -> SolutionResult:
        if judge_run_result.returncode == 0:
            points = self._load_points(judge_run_result)
            if points == 1.0:
                verdict = Verdict.ok
            elif points == 0.0:
                verdict = Verdict.wrong_answer
            else:
                verdict = Verdict.partial_ok

            with self._open_file(judge_run_result.stderr_file) as f:
                message = f.readline().removesuffix("\n")

            return RelativeSolutionResult(
                verdict=verdict,
                message=message,
                solution_rr=self._solution_run_res,
                checker_rr=judge_run_result,
                relative_points=points,
            )
        else:
            raise self._create_program_failure(
                f"Judge failed on {self._checking_message()}:",
                judge_run_result,
                stderr_force_content=True,
            )


class RunCMSBatchJudge(RunCMSJudge, RunBatchChecker):
    """Checks solution output using judge with CMS interface."""

    def __init__(
        self,
        env: Env,
        judge: RunSection,
        test: int,
        input_: IInputPath,
        output: IOutputPath,
        correct_output: IOutputPath,
        expected_verdict: Optional[Verdict],
        **kwargs,
    ) -> None:
        super().__init__(
            env=env,
            judge=judge,
            test=test,
            input_=input_,
            output=output,
            correct_output=correct_output,
            expected_verdict=expected_verdict,
            **kwargs,
        )

    @staticmethod
    def _invalid_path(name: str):
        return os.path.join(gettempdir(), f"the-{name}-is-not-available-{uuid4()}")

    def _check(self) -> SolutionResult:
        config = self._env.config

        self._access_file(self.output)
        if config.tests.judge_needs_in:
            self._access_file(self.input)
        if config.tests.judge_needs_out:
            self._access_file(self.correct_output)

        result = self._run_program(
            ProgramRole.judge,
            self.judge,
            args=[
                (
                    self.input.abspath
                    if config.tests.judge_needs_in
                    else RunCMSBatchJudge._invalid_path("input")
                ),
                (
                    self.correct_output.abspath
                    if config.tests.judge_needs_out
                    else RunCMSBatchJudge._invalid_path("output")
                ),
                self.output.abspath,
            ],
            stdout=self.points_file,
            stderr=self.checker_log_file,
        )

        sol_result = self._load_solution_result(result)
        return sol_result
