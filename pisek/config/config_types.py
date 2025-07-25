# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2023        Daniel Skýpala <daniel@honza.info>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>

from enum import auto, StrEnum
from pydantic_core import PydanticCustomError
from pydantic import BeforeValidator
from typing import Annotated, Literal


class TaskType(StrEnum):
    batch = auto()
    interactive = auto()


class OutCheck(StrEnum):
    diff = auto()
    tokens = auto()
    shuffle = auto()
    judge = auto()


class GenType(StrEnum):
    opendata_v1 = "opendata-v1"
    cms_old = "cms-old"
    pisek_v1 = "pisek-v1"


class ValidatorType(StrEnum):
    simple_0 = "simple-0"
    simple_42 = "simple-42"


class JudgeType(StrEnum):
    cms_batch = "cms-batch"
    cms_communication = "cms-communication"
    opendata_v1 = "opendata-v1"


class ShuffleMode(StrEnum):
    lines = auto()
    words = auto()
    lines_words = auto()
    tokens = auto()


class DataFormat(StrEnum):
    text = auto()
    strict_text = "strict-text"
    binary = auto()


def validate_test_points(points: str):
    if points == "unscored":
        return "unscored"
    try:
        p = int(points)
        assert p >= 0
        return p
    except (AssertionError, ValueError):
        raise PydanticCustomError(
            "test_points_parsing",
            "Input should be non-negative integer or 'unscored'",
        )


TestPoints = Annotated[int | Literal["unscored"], BeforeValidator(validate_test_points)]


class ProgramType(StrEnum):
    gen = auto()
    validator = auto()
    primary_solution = auto()
    secondary_solution = auto()
    judge = auto()

    def is_solution(self) -> bool:
        return self in (ProgramType.primary_solution, ProgramType.secondary_solution)

    @property
    def build_name(self) -> str:
        if self.is_solution():
            return "solution"
        else:
            return self.name


class BuildStrategyName(StrEnum):
    python = auto()
    shell = auto()
    c = auto()
    cpp = auto()
    pascal = auto()
    make = auto()
    cargo = auto()
    auto = auto()


class CMSFeedbackLevel(StrEnum):
    full = auto()
    restricted = auto()


class CMSScoreMode(StrEnum):
    max = auto()
    max_subtask = auto()
    max_tokened_last = auto()
