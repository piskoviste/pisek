# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2019 - 2022 Václav Volhejn <vaclav.volhejn@gmail.com>
# Copyright (c)   2019 - 2022 Jiří Beneš <mail@jiribenes.com>
# Copyright (c)   2020 - 2022 Michal Töpfer <michal.topfer@gmail.com>
# Copyright (c)   2022        Jiří Kalvoda <jirikalvoda@kam.mff.cuni.cz>
# Copyright (c)   2023        Daniel Skýpala <daniel@honza.info>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import auto, Enum
from functools import partial, cache, cached_property
from typing import Callable, Optional, TYPE_CHECKING

from pisek.utils.colors import ColorSettings
from pisek.config.config_types import TestPoints
from pisek.task_jobs.run_result import RunResult

if TYPE_CHECKING:
    from pisek.env.env import Env


class Verdict(Enum):
    # Higher value means more unsuccessful verdict.
    superopt = auto()
    ok = auto()
    partial_ok = auto()
    timeout = auto()
    wrong_answer = auto()
    normalization_fail = auto()
    error = auto()

    def is_zero_point(self) -> bool:
        return self in (
            Verdict.timeout,
            Verdict.wrong_answer,
            Verdict.error,
            Verdict.normalization_fail,
        )

    @cached_property
    def mark(self) -> str:
        mark = {
            Verdict.ok: "·",
            Verdict.superopt: "S",
            Verdict.partial_ok: "P",
            Verdict.timeout: "T",
            Verdict.wrong_answer: "W",
            Verdict.error: "!",
            Verdict.normalization_fail: "N",
        }[self]
        return ColorSettings.colored(mark, self.color)

    @cached_property
    def color(self) -> str:
        return {
            Verdict.ok: "green",
            Verdict.superopt: "blue",
            Verdict.partial_ok: "yellow",
            Verdict.timeout: "red",
            Verdict.wrong_answer: "red",
            Verdict.error: "red",
            Verdict.normalization_fail: "red",
        }[self]

    @staticmethod
    @cache
    def pad_length() -> int:
        return max(len(v.name) for v in Verdict)


@dataclass(init=False)
class SolutionResult(ABC):
    """Class representing result of a solution on given input."""

    verdict: Verdict
    message: str | None
    solution_rr: RunResult
    checker_rr: RunResult | None
    log: str | None = None
    note: str | None = None

    def points(self, env: "Env", test_points: TestPoints) -> Decimal:
        if test_points == "unscored":
            return Decimal("0")
        else:
            return self._points(env, test_points)

    @abstractmethod
    def _points(self, env: "Env", test_points: int) -> Decimal:
        pass


@dataclass(kw_only=True)
class RelativeSolutionResult(SolutionResult):
    verdict: Verdict
    message: Optional[str]
    solution_rr: RunResult
    checker_rr: Optional[RunResult]
    log: str | None = None
    note: str | None = None
    relative_points: Decimal

    def _points(self, env: "Env", test_points: int) -> Decimal:
        return (self.relative_points * test_points).quantize(
            Decimal("0.1") ** env.config.task.score_precision
        )


@dataclass(kw_only=True)
class AbsoluteSolutionResult(SolutionResult):
    verdict: Verdict
    message: Optional[str]
    solution_rr: RunResult
    checker_rr: Optional[RunResult]
    log: str | None = None
    note: str | None = None
    absolute_points: Decimal

    def _points(self, env: "Env", test_points: int) -> Decimal:
        return self.absolute_points


def verdict_always(res: Verdict) -> bool:
    return True


def verdict_accepted(res: Verdict) -> bool:
    return res in (Verdict.ok, Verdict.superopt)


def specific_verdict(res: Verdict, verdict: Verdict) -> bool:
    return res == verdict


# Specifies how expected str should be interpreted
# First function must be true for all
# Second function must be true for any
TEST_SPEC: dict[str, tuple[Callable[[Verdict], bool], Callable[[Verdict], bool]]] = {
    "1": (
        verdict_accepted,
        partial(specific_verdict, verdict=Verdict.ok),
    ),
    "S": (partial(specific_verdict, verdict=Verdict.superopt), verdict_always),
    "A": (verdict_accepted, verdict_always),
    "0": (verdict_always, lambda verdict: verdict.is_zero_point()),
    "X": (verdict_always, verdict_always),
    "P": (
        lambda verdict: not verdict.is_zero_point(),
        partial(specific_verdict, verdict=Verdict.partial_ok),
    ),
    "W": (
        verdict_always,
        partial(specific_verdict, verdict=Verdict.wrong_answer),
    ),
    "N": (
        verdict_always,
        partial(specific_verdict, verdict=Verdict.normalization_fail),
    ),
    "!": (verdict_always, partial(specific_verdict, verdict=Verdict.error)),
    "T": (verdict_always, partial(specific_verdict, verdict=Verdict.timeout)),
}
