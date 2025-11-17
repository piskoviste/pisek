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

from pisek.env.env import Env
from pisek.utils.paths import IInputPath
from pisek.config.task_config import ProgramRole, RunSection
from pisek.task_jobs.run_result import RunResult
from pisek.task_jobs.program import ProgramsJob


class ValidatorJob(ProgramsJob):
    """Runs validator on single input. (Abstract class)"""

    def __init__(
        self,
        env: Env,
        validator: RunSection,
        input_: IInputPath,
        test: int,
        **kwargs,
    ):
        super().__init__(env=env, name=f"Validate {input_:n} on test {test}", **kwargs)
        self.validator = validator
        self.test = test
        self.input = input_
        self.log_file = input_.to_log(f"{validator.name}{test}")

    @property
    @abstractmethod
    def _expected_returncode(self) -> int:
        pass

    @abstractmethod
    def _validation_args(self) -> list[str]:
        pass

    def _validate(self) -> RunResult:
        return self._run_program(
            ProgramRole.validator,
            self.validator,
            args=self._validation_args(),
            stdin=self.input,
            stderr=self.log_file,
        )

    def _run(self) -> None:
        result = self._validate()
        if result.returncode != self._expected_returncode:
            raise self._create_program_failure(
                f"Validator failed on {self.input:p} (test {self.test}):",
                result,
                stderr_force_content=True,
            )
