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

from pisek.utils.paths import IInputPath, IOutputPath, IRawPath
from pisek.jobs.jobs import Job
from pisek.task_jobs.task_manager import TaskJobManager, SOLUTION_MAN_CODE
from pisek.task_jobs.manager_results import SolutionManagerResult, FuzzingManagerResult
from pisek.task_jobs.checker.chaos_monkey import (
    Invalidate,
    Incomplete,
    BlankLine,
    ChaosMonkey,
    TrailingString,
)

from pisek.task_jobs.solution.solution_result import Verdict
from pisek.task_jobs.checker.checker_base import RunChecker
from pisek.task_jobs.checker.cms_judge import RunCMSJudge
from pisek.task_jobs.checker.checker import checker_job


class FuzzingManager(TaskJobManager):
    """Manager that prepares and test judge."""

    def __init__(self) -> None:
        super().__init__("Fuzz judge")

    def _get_jobs(self) -> list[Job]:
        jobs: list[Job] = []

        primary_sol = self.prerequisite_result(
            SOLUTION_MAN_CODE + self._env.config.primary_solution, SolutionManagerResult
        )

        self._inputs = primary_sol.inputs
        testcases: list[tuple[IInputPath, IOutputPath]] = []
        for inp, res in primary_sol.testcase_results.items():
            assert res is not None and isinstance(
                res.solution_run_result.stdout_file, IRawPath
            )  # Batch task
            testcases.append(
                (inp, res.solution_run_result.stdout_file.to_sanitized_output())
            )

        jt = self._env.config.tests.checks_fuzzing_thoroughness
        CHOICE_JOBS: list[tuple[type[Invalidate], int]] = [
            (Incomplete, jt // 10),
            (BlankLine, jt // 10),
            (ChaosMonkey, 4 * jt // 5),
        ]
        ALL_JOBS: list[type[Invalidate]] = [TrailingString]

        total_times = sum(map(lambda x: x[1], CHOICE_JOBS)) + len(ALL_JOBS) * len(
            testcases
        )
        rand_gen = random.Random(4)  # Reproducibility!
        seeds = rand_gen.sample(range(0, 16**8), total_times)

        if self._env.config.tests.checks_fuzzing_thoroughness:
            for job, times in CHOICE_JOBS:
                for _ in range(times):
                    seed = seeds.pop()
                    inp, out = rand_gen.choice(testcases)
                    jobs += self._fuzz_jobs(job, inp, out, seed, rand_gen)

        if self._env.config.tests.checks_judge_rejects_trailing_string:
            for inp, out in testcases:
                jobs += self._fuzz_jobs(
                    TrailingString,
                    inp,
                    out,
                    seeds.pop(),
                    rand_gen,
                    Verdict.wrong_answer,
                )

        return jobs

    def _fuzz_jobs(
        self,
        job: type[Invalidate],
        inp: IInputPath,
        out: IOutputPath,
        seed: int,
        rand_gen: random.Random,
        expected_verdict: Verdict | None = None,
    ):
        inv_out = out.to_fuzzing(job.__name__.lower(), seed)
        jobs = [
            invalidate := job(self._env, out, inv_out, seed),  # type: ignore[arg-type, call-arg]
            run_judge := checker_job(
                inp,
                inv_out,
                out,
                rand_gen.choice(self._inputs[inp.name][0]),
                self._inputs[inp.name][1],
                expected_verdict,
                self._env,
            ),
        ]
        run_judge.add_prerequisite(invalidate)
        return jobs

    def _compute_result(self) -> FuzzingManagerResult:
        checker_outs = set()
        for job in self.jobs:
            if isinstance(job, RunChecker):
                if isinstance(job, RunCMSJudge):
                    checker_outs.add(job.points_file)
                checker_outs.add(job.checker_log_file)

        return FuzzingManagerResult(checker_outs)
