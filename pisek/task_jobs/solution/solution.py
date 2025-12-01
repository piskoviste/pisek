# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2023        Daniel Skýpala <daniel@honza.info>
# Copyright (c)   2024        Benjamin Swart <benjaminswart@email.cz>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import tempfile
import time
from typing import Optional

from pisek.env.env import Env
from pisek.jobs.jobs import State
from pisek.utils.paths import IInputPath, IOutputPath
from pisek.config.config_types import ProgramRole
from pisek.config.task_config import RunSection
from pisek.task_jobs.program import RunResult, ProgramsJob
from pisek.task_jobs.solution.solution_result import Verdict, SolutionResult
from pisek.task_jobs.checker.cms_judge import RunCMSJudge


class RunSolution(ProgramsJob):
    """Runs solution on given input."""

    def __init__(
        self,
        env: Env,
        name: str,
        solution: RunSection,
        is_primary: bool,
        **kwargs,
    ) -> None:
        super().__init__(env=env, name=name, **kwargs)
        self._needed_by = 1
        self.solution = solution
        self.is_primary = is_primary

    def require(self):
        self._needed_by += 1

    def unrequire(self):
        self._needed_by -= 1
        if self._needed_by == 0 and self.state == State.in_queue:
            self.cancel()
        assert self._needed_by >= 0

    def _solution_type(self) -> ProgramRole:
        return (
            (ProgramRole.primary_solution)
            if self.is_primary
            else (ProgramRole.secondary_solution)
        )


class RunBatchSolution(RunSolution):
    def __init__(
        self,
        env: Env,
        solution: RunSection,
        is_primary: bool,
        input_: IInputPath,
        output: IOutputPath,
        **kwargs,
    ) -> None:
        super().__init__(
            env=env,
            name=f"Run {solution.name} on input {input_:n}",
            solution=solution,
            is_primary=is_primary,
            **kwargs,
        )
        self.input = input_
        self.output = output.to_raw(env.config.tests.out_format)
        self.log_file = input_.to_log("solution")

    def _run(self) -> RunResult:
        return self._run_program(
            program_role=self._solution_type(),
            program=self.solution,
            stdin=self.input,
            stdout=self.output,
            stderr=self.log_file,
        )


class RunInteractive(RunCMSJudge, RunSolution):
    def __init__(
        self,
        env: Env,
        solution: RunSection,
        is_primary: bool,
        judge: RunSection,
        test: int,
        input_: IInputPath,
        expected_verdict: Optional[Verdict] = None,
        **kwargs,
    ):
        self.sol_log_file = input_.to_log("solution")
        super().__init__(
            env=env,
            name=f"Run {solution.name} on input {input_:n}",
            judge=judge,
            test=test,
            input_=input_,
            expected_verdict=expected_verdict,
            checker_log_file=self.sol_log_file.to_checker_log(judge.name),
            solution=solution,
            is_primary=is_primary,
            **kwargs,
        )

    def _get_solution_run_res(self) -> RunResult:
        with tempfile.TemporaryDirectory() as fifo_dir:
            fifo_from_solution = os.path.join(fifo_dir, "solution-to-manager")
            fifo_to_solution = os.path.join(fifo_dir, "manager-to-solution")

            os.mkfifo(fifo_from_solution)
            os.mkfifo(fifo_to_solution)

            pipes = [
                os.open(fifo_from_solution, os.O_RDWR),
                os.open(fifo_to_solution, os.O_RDWR),
                # Open fifos to prevent blocking on future opens
                fd_from_solution := os.open(fifo_from_solution, os.O_WRONLY),
                fd_to_solution := os.open(fifo_to_solution, os.O_RDONLY),
            ]

            self._load_program(
                ProgramRole.judge,
                self.judge,
                stdin=self.input,
                stdout=self.points_file,
                stderr=self.checker_log_file,
                args=[fifo_from_solution, fifo_to_solution],
            )

            self._load_program(
                self._solution_type(),
                self.solution,
                stdin=fd_to_solution,
                stdout=fd_from_solution,
                stderr=self.sol_log_file,
            )

            def close_pipes(_):
                time.sleep(0.05)
                for pipe in pipes:
                    os.close(pipe)

            self._load_callback(close_pipes)

            judge_res, sol_res = self._run_programs()
            self._judge_run_result = judge_res

            return sol_res

    def _check(self) -> SolutionResult:
        return self._load_solution_result(self._judge_run_result)

    def _checking_message(self) -> str:
        return f"solution {self.solution.name} on input {self.input.col(self._env)}"
