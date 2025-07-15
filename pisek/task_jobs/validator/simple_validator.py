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

from pisek.task_jobs.validator.validator_base import ValidatorJob


class Simple0Validate(ValidatorJob):
    """Runs simple-0 validator on single input."""

    @property
    def _expected_returncode(self):
        return 0

    def _validation_args(self):
        return [str(self.test)]


class Simple42Validate(ValidatorJob):
    """Runs simple-42 validator on single input."""

    @property
    def _expected_returncode(self):
        return 42

    def _validation_args(self):
        return [str(self.test)]
