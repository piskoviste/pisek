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
import logging
from typing import Any

from pisek.utils.paths import IInputPath, IOutputPath
from pisek.env.env import Env
from pisek.config.config_types import ProgramRole
from pisek.config.task_config import RunSection
from pisek.task_jobs.solution.solution_result import (
    Verdict,
    SolutionResult,
    AbsoluteSolutionResult,
    RelativeSolutionResult,
)

from pisek.task_jobs.checker.checker_base import RunBatchChecker

logger = logging.getLogger(__name__)


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
        input_: IInputPath,
        output: IOutputPath,
        correct_output: IOutputPath,
        seed: int | None,
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
        self.seed = seed

    def _load_stderr(self) -> tuple[str, dict[str, Any]]:
        KEYS = {
            "POINTS": Decimal,
            "LOG": str,
            "NOTE": str,
        }
        FAIL_KWARGS = {
            "status": False,
            "stdout": False,
            "stderr_force_content": True,
        }

        key_values: dict[str, Any] = {}
        with self._open_file(self.checker_log_file) as f:
            message = f.readline().removesuffix("\n")
            if len(message.encode()) > 255:
                raise self._create_program_failure(
                    f"Message longer than 255 bytes: '{message}'",
                    self._result,
                    **FAIL_KWARGS,
                )
            for line in f.readlines():
                line = line.removesuffix("\n")

                if "=" not in line:
                    raise self._create_program_failure(
                        f"Invalid key-value pair: '{line}'", self._result, **FAIL_KWARGS
                    )
                key, val = line.split("=", 1)

                if key not in KEYS:
                    raise self._create_program_failure(
                        f"Invalid key: '{key}'", self._result, **FAIL_KWARGS
                    )
                if key in key_values:
                    raise self._create_program_failure(
                        f"Duplicate key: '{key}'", self._result, **FAIL_KWARGS
                    )
                if len(val.encode()) > 255:
                    raise self._create_program_failure(
                        f"Value longer than 255 bytes: '{val}'",
                        self._result,
                        **FAIL_KWARGS,
                    )
                try:
                    key_values[key] = KEYS[key](val)
                except ValueError:
                    raise self._create_program_failure(
                        f"Value is not of type '{KEYS[key]}': '{val}'",
                        self._result,
                        **FAIL_KWARGS,
                    )

        return (message, key_values)

    def _check(self) -> SolutionResult:
        envs = {}
        if self._env.config.tests.judge_needs_in:
            envs["TEST_INPUT"] = self.input.abspath
            self._access_file(self.input)
        if self._env.config.tests.judge_needs_out:
            envs["TEST_OUTPUT"] = self.correct_output.abspath
            self._access_file(self.correct_output)

        self._result = self._run_program(
            ProgramRole.judge,
            self.judge,
            args=[
                str(self.test),
                f"{self.seed:016x}" if self.seed is not None else OPENDATA_NO_SEED,
            ],
            stdin=self.output,
            stderr=self.checker_log_file,
            env=envs,
        )

        if self._result.returncode not in (self.return_code_ok, self.return_code_wa):
            # We need to check this first to report the correct problem
            raise self._create_program_failure(
                f"Judge failed on output {self.output:n}:",
                self._result,
                stderr_force_content=True,
            )

        message, key_values = self._load_stderr()

        if "LOG" in key_values:
            self._log(
                "info", f"Judge on output {self.output:p}: LOG={key_values['LOG']}"
            )

        if self._result.returncode == self.return_code_ok:
            if "POINTS" not in key_values:
                return RelativeSolutionResult(
                    verdict=Verdict.ok,
                    message=message,
                    solution_rr=self._solution_run_res,
                    checker_rr=self._result,
                    log=key_values.get("LOG"),
                    note=key_values.get("NOTE"),
                    relative_points=Decimal(1),
                )

            max_points = self._env.config.test_sections[self.test].points
            points = key_values["POINTS"]
            if max_points == "unscored" or points == max_points:
                verdict = Verdict.ok
            elif points < max_points:
                verdict = Verdict.partial_ok
            else:
                verdict = Verdict.superopt

            return AbsoluteSolutionResult(
                verdict=verdict,
                message=message,
                solution_rr=self._solution_run_res,
                checker_rr=self._result,
                log=key_values.get("LOG"),
                note=key_values.get("NOTE"),
                absolute_points=points,
            )

        else:
            return RelativeSolutionResult(
                verdict=Verdict.wrong_answer,
                message=message,
                solution_rr=self._solution_run_res,
                checker_rr=self._result,
                log=key_values.get("LOG"),
                note=key_values.get("NOTE"),
                relative_points=Decimal(0),
            )


class RunOpendataV1Judge(RunOpendataJudge):
    """Checks solution output using judge with the opendataV1 interface."""

    @property
    def return_code_ok(self) -> int:
        return 0

    @property
    def return_code_wa(self) -> int:
        return 1


class RunOpendataV2Judge(RunOpendataJudge):
    """Checks solution output using judge with the opendataV2 interface."""

    @property
    def return_code_ok(self) -> int:
        return 42

    @property
    def return_code_wa(self) -> int:
        return 43
