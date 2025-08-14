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

import random
from typing import Any

from pisek.utils.paths import InputPath, OutputPath
from pisek.jobs.jobs import Job
from pisek.task_jobs.task_manager import TaskJobManager, SOLUTION_MAN_CODE
from pisek.task_jobs.checker.chaos_monkey import Incomplete, ChaosMonkey

from pisek.task_jobs.checker.checker_base import RunChecker
from pisek.task_jobs.checker.cms_judge import RunCMSJudge
from pisek.task_jobs.checker.checker import checker_job


class FuzzingManager(TaskJobManager):
    """Manager that prepares and test judge."""

    def __init__(self) -> None:
        super().__init__("Fuzz judge")

    def _get_jobs(self) -> list[Job]:
        jobs: list[Job] = []

        primary_sol = self.prerequisites_results[
            SOLUTION_MAN_CODE + self._env.config.primary_solution
        ]

        inputs: dict[str, tuple[list[int], int | None]] = primary_sol["inputs"]
        testcases: list[tuple[InputPath, OutputPath]] = []
        for inp, res in primary_sol["results"].items():
            testcases.append((inp, res.solution_rr.stdout_file.to_sanitized_output()))

        jt = self._env.config.checks.fuzzing_thoroughness
        JOBS = [(Incomplete, jt // 5), (ChaosMonkey, 4 * jt // 5)]

        total_times = sum(map(lambda x: x[1], JOBS))
        rand_gen = random.Random(4)  # Reproducibility!
        seeds = rand_gen.sample(range(0, 16**8), total_times)
        for job, times in JOBS:
            for _ in range(times):
                seed = seeds.pop()
                inp, out = rand_gen.choice(testcases)
                inv_out = out.to_fuzzing(seed)
                jobs += [
                    invalidate := job(self._env, out, inv_out, seed),
                    run_judge := checker_job(
                        inp,
                        inv_out,
                        out,
                        rand_gen.choice(inputs[inp.name][0]),
                        inputs[inp.name][1],
                        None,
                        self._env,
                    ),
                ]
                run_judge.add_prerequisite(invalidate)

        return jobs

    def _compute_result(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        result["checker_outs"] = set()
        for job in self.jobs:
            if isinstance(job, RunChecker):
                if isinstance(job, RunCMSJudge):
                    result["checker_outs"].add(job.points_file)
                result["checker_outs"].add(job.checker_log_file)

        return result
