# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2023        Daniel Skýpala <skipy@kam.mff.cuni.cz>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>

from decimal import Decimal, InvalidOperation
from enum import auto, StrEnum
from functools import total_ordering
from pydantic_core import PydanticCustomError
from pydantic import BeforeValidator, Field
from types import NotImplementedType
from typing import Annotated, Any, Literal, overload, get_args
from pydantic_core import core_schema


@total_ordering
class Limit[T: int | Decimal]:
    value: T | Literal["unlimited"]

    def __init__(self, value: T | Literal["unlimited"]) -> None:
        if isinstance(value, str):
            if value != "unlimited":
                raise ValueError(
                    f'Limit string value must be "unlimited", got {value!r}'
                )
            self.value = "unlimited"
        elif isinstance(value, (int, Decimal)):
            if isinstance(value, Decimal) and not value.is_finite():
                raise ValueError("Limit must be finite")
            if value < 0:
                raise ValueError("Limit must be greater then or equal to 0")
            self.value = value
        else:
            raise TypeError(
                f"Limit value must be a number or 'unlimited', got {type(value)!r}"
            )

    @staticmethod
    def from_str(value: str, t: type[T]) -> "Limit[T]":
        if "unlimited".startswith(value):
            return Limit("unlimited")
        try:
            return Limit(t(value))  # type: ignore[arg-type]
        except (ValueError, InvalidOperation):
            pass
        raise ValueError(f"Cannot convert to limit: '{value}'")

    @property
    def is_unlimited(self) -> bool:
        return self.value == "unlimited"

    def unlimited_as[U](self, value: U) -> U | T:
        if self.value == "unlimited":
            return value
        else:
            return self.value

    def __format__(self, format_spec: str) -> str:
        if self.is_unlimited:
            return "unlim"
        else:
            return format(self.value, format_spec)

    def __repr__(self) -> str:
        return f"Limit({self.value!r})"

    def __str__(self) -> str:
        return str(self.value)

    @staticmethod
    def _coerce(
        other: Any,
    ) -> int | Decimal | Literal["unlimited"] | NotImplementedType:
        if isinstance(other, Limit):
            return other.value
        if isinstance(other, str):
            return "unlimited" if other == "unlimited" else NotImplemented
        if isinstance(other, (int, Decimal)):
            return other
        return NotImplemented

    def __eq__(self, other: object) -> bool:
        other_value = self._coerce(other)
        if other_value is NotImplemented:
            return NotImplemented
        return self.value == other_value

    def __lt__(self, other: object) -> bool:
        other_value = self._coerce(other)
        if other_value is NotImplemented:
            return NotImplemented
        if self.value == "unlimited":
            return False
        if other_value == "unlimited":
            return True
        return self.value < other_value

    @overload
    def __mul__(
        self, other: "int | Limit[int] | Literal['unlimited']"
    ) -> "Limit[T]": ...
    @overload
    def __mul__(self, other: "Decimal | Limit[Decimal]") -> "Limit[Decimal]": ...
    def __mul__(self, other: Any) -> "Limit[T] | Limit[Decimal]":
        other_value = self._coerce(other)
        if other_value is NotImplemented:
            return NotImplemented
        if self.value == 0 or other_value == 0:
            # Special hack for clock_mul=0
            if isinstance(self.value, Decimal) or isinstance(other_value, Decimal):
                return Limit(Decimal(0))
            else:
                return Limit(0)  # type: ignore[return-value]
        if self.value == "unlimited" or other_value == "unlimited":
            return Limit("unlimited")
        return Limit(self.value * other_value)  # type: ignore[return-value]

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        (numeric_type,) = get_args(source_type) or (int,)
        numeric_schema = handler.generate_schema(numeric_type)
        unlimited_schema = core_schema.literal_schema(["unlimited"])
        value_schema = core_schema.union_schema([numeric_schema, unlimited_schema])

        return core_schema.chain_schema(
            [value_schema, core_schema.no_info_plain_validator_function(cls)]
        )


type PositiveLimit[T] = Annotated[Limit[T], Field(gt=0)]


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
    opendata_v2 = "opendata-v2"
    codeforces_batch_v1 = "codeforces-batch-v1"


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
        p = Decimal(points)
        assert p >= 0 and p.is_finite()
        return p
    except (AssertionError, InvalidOperation):
        raise PydanticCustomError(
            "test_points_parsing",
            "Input should be non-negative decimal or 'unscored'",
        )


TestPoints = Annotated[
    Decimal | Literal["unscored"], BeforeValidator(validate_test_points)
]


def validate_solution_points(points: str):
    if points == "X":
        return None
    try:
        p = Decimal(points)
        assert p >= 0 and p.is_finite()
        return p
    except (AssertionError, InvalidOperation):
        raise PydanticCustomError(
            "solution_points_parsing",
            "Input should be non-negative decimal or 'X'",
        )


SolutionPoints = Annotated[Decimal | None, BeforeValidator(validate_solution_points)]


class ProgramRole(StrEnum):
    gen = auto()
    validator = auto()
    primary_solution = auto()
    secondary_solution = auto()
    judge = auto()

    def is_solution(self) -> bool:
        return self in (ProgramRole.primary_solution, ProgramRole.secondary_solution)

    @property
    def build_name(self) -> str:
        if self.is_solution():
            return "solution"
        else:
            return self.name


class BuildStrategyName(StrEnum):
    cargo = auto()
    c = auto()
    cpp = auto()
    go = auto()
    haskell = auto()
    java = auto()
    make = auto()
    pascal = auto()
    python = auto()
    shell = auto()
    auto = auto()


class CMSFeedbackLevel(StrEnum):
    full = auto()
    restricted = auto()
    oi_restricted = auto()


class CMSScoreMode(StrEnum):
    max = auto()
    max_subtask = auto()
    max_tokened_last = auto()
