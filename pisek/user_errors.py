# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2025        Daniel Skýpala <daniel@honza.info>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


class UserError(Exception):
    pass


class TaskConfigError(UserError):
    pass


class TaskConfigParsingError(TaskConfigError):
    def __init__(self, path: str, msg: str) -> None:
        super().__init__(f"Unable to parse '{path}': {msg}")


class MissingFile(UserError):
    pass


class TestingFailed(UserError):
    pass


class InvalidArgument(UserError):
    pass


class InvalidOperation(UserError):
    pass
