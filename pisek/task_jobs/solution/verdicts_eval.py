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

from typing import Optional

from pisek.config.task_config import TaskConfig
from pisek.task_jobs.solution.solution_result import (
    Verdict,
    TEST_SPEC,
    verdict_always,
)


def check_verdicts(
    verdicts: list[Verdict], expected: str
) -> tuple[bool, bool, Optional[int]]:
    """
    Returns tuple:
        - whether verdicts are as expected
        - whether the result is definitive (cannot be changed)
        - a verdict that makes the result the way it is (if there is one particular)
    """
    result = True
    definitive = True
    guarantor = None

    oks = list(map(TEST_SPEC[expected][0], verdicts))
    ok = all(oks)
    result &= ok
    definitive &= not ok or TEST_SPEC[expected][0] == verdict_always
    if not ok:
        return result, definitive, oks.index(False)

    oks = list(map(TEST_SPEC[expected][1], verdicts))
    ok = any(oks)
    result &= ok
    definitive &= ok
    if not ok and len(verdicts) == 1:
        guarantor = 0
    elif ok and TEST_SPEC[expected][1] != verdict_always:
        guarantor = oks.index(True)

    return result, definitive, guarantor


def compute_verdict(verdicts: list[Verdict]) -> Verdict:
    return max(verdicts, default=Verdict.ok, key=lambda v: v.value)
