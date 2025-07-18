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

from pisek.utils.paths import InputPath, OutputPath
from pisek.env.env import Env
from pisek.config.config_types import ProgramType
from pisek.config.task_config import RunSection
from pisek.task_jobs.solution.solution_result import (
    Verdict,
    SolutionResult,
    RelativeSolutionResult,
)

from pisek.task_jobs.checker.checker_base import RunBatchChecker


OPENDATA_NO_SEED = "-"


class RunOpendataJudge(RunBatchChecker):
    """Checks solution output using judge with the opendata interface. (Abstract class)"""

    @property
    @abstractmethod
    def return_code_ok(self) -> int:
        pass

    @property
    @abstractmethod
    def return_code_wa(self) -> int:
        pass

    def __init__(
        self,
        env: Env,
        judge: RunSection,
        test: int,
        input_: InputPath,
        output: OutputPath,
        correct_output: OutputPath,
        seed: Optional[int],
        expected_verdict: Optional[Verdict],
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
        self.seed = seed

    def _check(self) -> SolutionResult:
        envs = {}
        if self._env.config.tests.judge_needs_in:
            envs["TEST_INPUT"] = self.input.abspath
            self._access_file(self.input)
        if self._env.config.tests.judge_needs_out:
            envs["TEST_OUTPUT"] = self.correct_output.abspath
            self._access_file(self.correct_output)

        result = self._run_program(
            ProgramType.judge,
            self.judge,
            args=[
                str(self.test),
                f"{self.seed:016x}" if self.seed is not None else OPENDATA_NO_SEED,
            ],
            stdin=self.output,
            stderr=self.checker_log_file,
            env=envs,
        )
        if result.returncode == self.return_code_ok:
            return RelativeSolutionResult(
                Verdict.ok, None, self._solution_run_res, result, Decimal(1)
            )
        elif result.returncode == self.return_code_wa:
            return RelativeSolutionResult(
                Verdict.wrong_answer, None, self._solution_run_res, result, Decimal(0)
            )
        else:
            raise self._create_program_failure(
                f"Judge failed on output {self.output:n}:", result
            )


class RunOpendataV1Judge(RunOpendataJudge):
    """Checks solution output using judge with the opendataV1 interface."""

    @property
    def return_code_ok(self) -> int:
        return 0

    @property
    def return_code_wa(self) -> int:
        return 1
