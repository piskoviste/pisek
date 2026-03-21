# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2026        Daniel Skýpala <skipy@kam.mff.cuni.cz>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from dataclasses import dataclass

from pisek.utils.paths import IInputPath, TaskPath
from pisek.task_jobs.run_result import RunResult
from pisek.task_jobs.data.testcase_info import TestcaseInfo
from pisek.task_jobs.solution.solution_result import SolutionResultDetail, Verdict


@dataclass
class PrepareGeneratorResult:
    inputs: list[TestcaseInfo]


@dataclass
class DataManagerResult:
    testcase_infos: dict[int, list[TestcaseInfo]]


@dataclass
class RunGeneratorResult:
    input_dataset: list[IInputPath]
    inputs: dict[str, tuple[list[int], int | None]]
    generator_run_results: list[RunResult]


@dataclass
class SolutionManagerResult(RunGeneratorResult):
    testcase_results: dict[IInputPath, SolutionResultDetail | None]
    tests_results: dict[int, Verdict]
    checker_outs: set[TaskPath]


@dataclass
class FuzzingManagerResult:
    checker_outs: set[TaskPath]
