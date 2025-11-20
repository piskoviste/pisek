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

from decimal import Decimal
import subprocess
from typing import Optional

from pisek.env.env import Env
from pisek.utils.paths import IInputPath, IOutputPath
from pisek.jobs.jobs import PipelineItemFailure
from pisek.utils.text import tab
from pisek.task_jobs.run_result import RunResult, RunResultKind
from pisek.task_jobs.solution.solution_result import (
    Verdict,
    SolutionResult,
    RelativeSolutionResult,
)
from pisek.task_jobs.checker.checker_base import RunBatchChecker


class RunDiffChecker(RunBatchChecker):
    """Checks solution output and correct output using diff."""

    def __init__(
        self,
        env: Env,
        test: int,
        input_: IInputPath,
        output: IOutputPath,
        correct_output: IOutputPath,
        expected_verdict: Optional[Verdict],
    ) -> None:
        super().__init__(
            env=env,
            checker_name="diff",
            test=test,
            input_=input_,
            output=output,
            correct_output=correct_output,
            expected_verdict=expected_verdict,
        )

    def _check(self) -> SolutionResult:
        self._access_file(self.output)
        self._access_file(self.correct_output)
        diff = self._run_subprocess(
            ["diff", "-Bbq", self.output.path, self.correct_output.path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # XXX: Okay, it didn't finish in no time, but this is not meant to be used
        rr = RunResult(
            RunResultKind.OK,
            diff.returncode,
            0,
            0,
            status=("Files are the same" if diff.returncode == 0 else "Files differ")
            + f": {self.output.col(self._env)} {self.correct_output.col(self._env)}",
        )
        if diff.returncode == 0:
            return RelativeSolutionResult(
                verdict=Verdict.ok,
                message=None,
                solution_rr=self._solution_run_res,
                checker_rr=rr,
                relative_points=Decimal(1),
            )
        elif diff.returncode == 1:
            return RelativeSolutionResult(
                verdict=Verdict.wrong_answer,
                message=None,
                solution_rr=self._solution_run_res,
                checker_rr=rr,
                relative_points=Decimal(0),
            )
        else:
            assert diff.stderr is not None
            raise PipelineItemFailure(
                f"Diff failed:\n{tab(diff.stderr.read().decode('utf-8'))}"
            )
