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

from dataclasses import dataclass
from decimal import Decimal
from enum import auto, StrEnum
from typing import Optional

from pisek.utils.paths import TaskPath


class RunResultKind(StrEnum):
    OK = auto()
    RUNTIME_ERROR = auto()
    TIMEOUT = auto()


@dataclass(frozen=True)
class RunResult:
    """Represents the way the program execution ended. Specially, a program
    that finished successfully, but got Wrong Answer, still gets the OK
    RunResult."""

    kind: RunResultKind
    returncode: int
    time: Decimal
    wall_time: Decimal
    memory: int
    stdin_file: TaskPath | int | None = None
    stdout_file: TaskPath | int | None = None
    stderr_file: Optional[TaskPath] = None
    status: str = ""
