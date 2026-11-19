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

from decimal import Decimal

from pisek.utils.paths import IInputPath, IOutputPath
from pisek.env.env import Env
from pisek.config.config_types import ProgramRole
from pisek.config.task_config import RunSection
from pisek.task_jobs.solution.solution_result import (
    Verdict,
    SolutionResult,
    RelativeSolutionResult,
)

from pisek.task_jobs.checker.checker_base import RunBatchChecker


class RunCodeforcesBatchV1Judge(RunBatchChecker):
    """Checks solution output using judge with the codeforces interface. (Abstract class)"""

    def __init__(
        self,
        env: Env,
        judge: RunSection,
        test: int,
        input_: IInputPath,
        output: IOutputPath,
        correct_output: IOutputPath,
        expected_verdict: Verdict | None,
        **kwargs,
    ) -> None:
        super().__init__(
            env=env,
            checker_name=judge.name,
            test=test,
            input_=input_,
            output=output,
            correct_output=correct_output,
            expected_verdict=expected_verdict,
            **kwargs,
        )
        self.judge = judge

    def _check(self) -> SolutionResult:
        config = self._env.config
        report = self.checker_log_file.replace_suffix(".report")

        self._access_file(self.output)
        self._access_file(report)
        if config.judge_needs_in:
            self._access_file(self.input)
        if config.judge_needs_out:
            self._access_file(self.correct_output)

        self.checker_rr = self._run_program(
            ProgramRole.judge,
            self.judge,
            args=[
                self._maybe_input_path(),
                self.output.abspath,
                self._maybe_correct_output_path(),
                report.abspath,
            ],
            stderr=self.checker_log_file,
        )

        if self.checker_rr.returncode == 0:
            return RelativeSolutionResult(
                verdict=Verdict.ok,
                message="OK",
                relative_points=Decimal(1),
            )
        elif self.checker_rr.returncode == 1:
            return RelativeSolutionResult(
                verdict=Verdict.wrong_answer,
                message="Wrong answer",
                relative_points=Decimal(0),
            )
        elif self.checker_rr.returncode == 2:
            return RelativeSolutionResult(
                verdict=Verdict.wrong_answer,
                message="Presentation error",
                relative_points=Decimal(0),
            )
        else:
            raise self._create_program_failure(
                f"Judge failed on output {self.output:n}:",
                self.checker_rr,
                stderr_force_content=True,
            )
