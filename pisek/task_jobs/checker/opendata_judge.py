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
from dataclasses import dataclass
from decimal import Decimal
import sys
from typing import NoReturn, Optional

from pisek.utils.paths import InputPath, OutputPath
from pisek.env.env import Env
from pisek.config.config_types import ProgramType
from pisek.config.task_config import RunSection
from pisek.task_jobs.solution.solution_result import (
    Verdict,
    SolutionResult,
    AbsoluteSolutionResult,
    RelativeSolutionResult,
)

from pisek.task_jobs.checker.checker_base import RunBatchChecker


OPENDATA_NO_SEED = "-"
ALLOWED_KEYS = ["POINTS", "LOG", "NOTE"]

@dataclass
class OpendataCheckingInfo:
    message: str | None
    points: Decimal | None = None
    log: str | None = None
    note: str | None = None


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

    def _load_stderr(self) -> OpendataCheckingInfo:
        def fail(msg: str) -> NoReturn:
            raise self._create_program_failure(
                msg, self._result, status=False, force_stderr=True
            )
        with self._open_file(self.checker_log_file) as f:
            msg = f.readline().removesuffix("\n")
            if sys.getsizeof(msg) > 255:
                fail("Message too long (maximum is 255 bytes):")

            info = OpendataCheckingInfo(msg if msg else None)

            for line in f.readlines():
                if "=" not in line:
                    fail(f"Line not a KEY=VALUE pair: '{line}'")

                key, val = line.removesuffix("\n").split("=", 1)
                if key not in ALLOWED_KEYS:
                    fail(f"Unknown key: '{key}'")
                key = key.lower()

                if sys.getsizeof(val) > 255:
                    fail(f"Value too long (maximum is 255 bytes): '{val}'")

                setattr(info, key, val)
        
        return info

    def _check(self) -> SolutionResult:
        envs = {}
        if self._env.config.tests.judge_needs_in:
            envs["TEST_INPUT"] = self.input.abspath
            self._access_file(self.input)
        if self._env.config.tests.judge_needs_out:
            envs["TEST_OUTPUT"] = self.correct_output.abspath
            self._access_file(self.correct_output)

        self._result = self._run_program(
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
        info = self._load_stderr()

        if self._result.returncode == self.return_code_ok:
            if info.points is None:
                return RelativeSolutionResult(
                    Verdict.ok, info.message, self._solution_run_res, self._result, Decimal(1)
                )
            # TODO: Think about superoptimal verdict type
            elif self.test_sec.points == "unscored" or True:
                return AbsoluteSolutionResult(
                    Verdict.ok, info.message, self._solution_run_res, self._result, info.points
                )
        elif self._result.returncode == self.return_code_wa:
            return RelativeSolutionResult(
                Verdict.wrong_answer, info.message, self._solution_run_res, self._result, Decimal(0)
            )
        else:
            raise self._create_program_failure(
                f"Judge failed on output {self.output:n}:", self._result
            )


class RunOpendataV1Judge(RunOpendataJudge):
    """Checks solution output using judge with the opendata-v1 interface."""

    @property
    def return_code_ok(self) -> int:
        return 0

    @property
    def return_code_wa(self) -> int:
        return 1
