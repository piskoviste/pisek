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

from collections import defaultdict
from decimal import Decimal

from pisek.jobs.jobs import State, Job
from pisek.jobs.status import StatusJobManager
from pisek.config.config_types import GenType
from pisek.config.task_config import RunSection
from pisek.env.env import TestingTarget
from pisek.task_jobs.run_result import RunResult
from pisek.task_jobs.task_manager import GENERATE_INPUTS_MAN_CODE, SOLUTION_MAN_CODE
from pisek.task_jobs.solution.solution_result import SolutionResultDetail


class ResourceStatistics(StatusJobManager):
    def __init__(self) -> None:
        super().__init__("Resource statistics")

    def _get_jobs(self) -> list[Job]:
        return []

    def get_status(self) -> str:
        def format_stat(
            run_results: list[RunResult],
            limit: Decimal | int,
            attr: str,
            dec_places: int = 0,
        ) -> list[str]:
            value = max(map(lambda rr: getattr(rr, attr), run_results))
            str_value = f"{value:.{dec_places}f}"

            if limit == 0:
                color = "green"
            elif value < Decimal("0.5") * limit:
                color = "green"
            elif value < Decimal("0.9") * limit:
                color = "yellow"
            elif value <= limit:
                color = "red"
            else:
                color = "white"

            return [self._colored(str_value, color), "/", f"{limit:.{dec_places}f}"]

        def part_statistics(
            name: str, run_results: list[RunResult], run_section: RunSection
        ) -> list[str]:
            return [
                f"{name:<30} ",
                *format_stat(run_results, run_section.time_limit, "time", dec_places=2),
                "s  ",
                *format_stat(run_results, run_section.mem_limit, "memory"),
                "MB  ",
            ]

        if self.state == State.cancelled:
            return self._job_bar(self.name)

        generator_rr: list[RunResult] = self.prerequisites_results[
            GENERATE_INPUTS_MAN_CODE
        ]["generator_run_results"]
        solution_rr: dict[str, list[RunResult]] = defaultdict(list)
        checker_rr: list[RunResult] = []

        for name, data in self.prerequisites_results.items():
            if not name.startswith(SOLUTION_MAN_CODE) or not any(
                data["results"].values()
            ):
                continue

            solution = name[len(SOLUTION_MAN_CODE) :]

            detail: SolutionResultDetail | None
            for detail in data["results"].values():
                if detail is None:
                    continue

                solution_rr[solution].append(detail.solution_run_result)
                if detail.checker_run_result is not None:
                    checker_rr.append(detail.checker_run_result)

        table: list[list[str]] = []

        if (
            self._env.config.tests.in_gen is not None
            and generator_rr
            and self._env.config.tests.gen_type != GenType.cms_old
        ):
            table.append(
                part_statistics(
                    f"generator {self._env.config.tests.in_gen.name}",
                    generator_rr,
                    self._env.config.tests.in_gen,
                )
            )

        if self._env.target in (
            TestingTarget.primary,
            TestingTarget.solutions,
            TestingTarget.all,
        ):
            for name, run_results in solution_rr.items():
                table.append(
                    part_statistics(
                        f"solution {name}",
                        run_results,
                        self._env.config.solutions[name].run,
                    )
                )

            if self._env.config.tests.out_judge is not None:
                table.append(
                    part_statistics(
                        f"judge {self._env.config.tests.out_judge.name}",
                        checker_rr,
                        self._env.config.tests.out_judge,
                    )
                )

        msg = "\n"
        for line in table:
            for part_i in range(len(line)):
                max_len = max(len(l[part_i]) for l in table)
                if part_i == 0:
                    msg += f"{line[part_i]:<{max_len}} "
                else:
                    msg += f"{line[part_i]:>{max_len}} "

            msg += "\n"

        return msg
