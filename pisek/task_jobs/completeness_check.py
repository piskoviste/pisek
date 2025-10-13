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

import filecmp

from pisek.utils.paths import TaskPath
from pisek.env.env import TestingTarget
from pisek.config.config_types import JudgeType, TaskType
from pisek.task_jobs.solution.solution_result import Verdict
from pisek.jobs.jobs import Job
from pisek.task_jobs.task_manager import (
    TaskJobManager,
    FUZZ_MAN_CODE,
    SOLUTION_MAN_CODE,
)


class CompletenessCheck(TaskJobManager):
    """Checks task as a whole."""

    def __init__(self):
        super().__init__("Completeness check")

    def _get_jobs(self) -> list[Job]:
        return []

    def _get_checker_outs(self) -> set[TaskPath]:
        checker_outs: set[TaskPath] = set()
        if FUZZ_MAN_CODE in self.prerequisites_results:
            checker_outs |= self.prerequisites_results[FUZZ_MAN_CODE]["checker_outs"]
        for solution in self._env.solutions:
            checker_outs |= self.prerequisites_results[
                f"{SOLUTION_MAN_CODE}{solution}"
            ]["checker_outs"]
        return checker_outs

    def _check_solution_succeeds_only_on(self, sol_name: str, tests: list[int]) -> bool:
        tests_res = self.prerequisites_results[f"{SOLUTION_MAN_CODE}{sol_name}"][
            "tests"
        ]
        for num in self._env.config.test_sections:
            if num == 0:
                continue  # Skip samples
            if (tests_res[num] == Verdict.ok) != (num in tests):
                return False
        return True

    def _check_dedicated_solutions(self) -> None:
        """Checks that each test has it's own dedicated solution."""
        if self._env.config.checks.solution_for_each_test:
            for num, test in self._env.config.test_sections.items():
                if num == 0:
                    continue  # Samples

                ok = False
                for solution in self._env.solutions:
                    if self._check_solution_succeeds_only_on(
                        solution, [num] + test.all_predecessors
                    ):
                        ok = True
                        break

                if not ok:
                    self._warn(f"{test.name} has no dedicated solution")

    def _check_different_outputs(self) -> None:
        """Checks that for each test primary solution's outputs aren't the same."""
        if self._env.config.task.task_type == TaskType.interactive:
            return

        res = self.prerequisites_results[
            f"{SOLUTION_MAN_CODE}{self._env.config.primary_solution}"
        ]["results"]
        for test in self._env.config.test_sections.values():
            if not test.checks_different_outputs:
                continue

            all_same = True
            outs = [inp.to_output() for inp in res if test.in_test(inp.name)]
            if len(outs) <= 1:
                continue

            for out in outs:
                all_same &= filecmp.cmp(outs[0].path, out.path, shallow=False)

            if all_same:
                self._warn(f"All outputs of {test.name} are the same")

    def _check_cms_judge(self) -> None:
        """Checks that cms judge's stdout & stderr contains only one line."""
        if self._env.config.tests.judge_type in (
            JudgeType.cms_batch,
            JudgeType.cms_communication,
        ):
            for judge_out in self._get_checker_outs():
                with open(judge_out.path) as f:
                    lines = f.read().rstrip().split("\n")
                if len(lines) > 1 or lines[0] == "":  # Python splitting is weird
                    self._warn(f"{judge_out:p} should contain exactly one line")
                    if self._env.verbosity <= 0:
                        return

    def _evaluate(self) -> None:
        assert self._env.target == TestingTarget.all

        self._check_cms_judge()
        self._check_different_outputs()
        self._check_dedicated_solutions()
