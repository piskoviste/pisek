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
from typing import Any, Optional

from pisek.env.env import Env
from pisek.utils.paths import InputPath, OutputPath
from pisek.config.config_types import TaskType, OutCheck, JudgeType
from pisek.jobs.jobs import Job
from pisek.task_jobs.task_manager import TaskJobManager
from pisek.task_jobs.checker.chaos_monkey import Incomplete, ChaosMonkey
from pisek.task_jobs.solution.solution_result import Verdict

from pisek.task_jobs.checker.checker_base import RunChecker, RunBatchChecker
from pisek.task_jobs.checker.diff_checker import RunDiffChecker
from pisek.task_jobs.checker.judgelib_checker import RunTokenChecker, RunShuffleChecker
from pisek.task_jobs.checker.cms_judge import RunCMSJudge, RunCMSBatchJudge
from pisek.task_jobs.checker.opendata_judge import RunOpendataV1Judge


class JudgeManager(TaskJobManager):
    """Manager that prepares and test judge."""

    def __init__(self) -> None:
        super().__init__("Preparing judge")

    def _get_jobs(self) -> list[Job]:
        jobs: list[Job] = []

        # All samples must be static, therefore they exist already
        samples = self._get_samples()
        if self._env.config.task_type == TaskType.interactive:
            return jobs

        for inp, out in samples:

            if self._env.config.checks.judge_handles_fuzzed_outputs:
                JOBS = [(Incomplete, 10), (ChaosMonkey, 50)]

                total = sum(map(lambda x: x[1], JOBS))
                random.seed(4)  # Reproducibility!
                seeds = random.sample(range(0, 16**4), total)

                for job, times in JOBS:
                    for _ in range(times):
                        seed = seeds.pop()
                        inv_out = out.to_fuzzing(seed)
                        jobs += [
                            invalidate := job(self._env, out, inv_out, seed),
                            run_judge := checker_job(
                                inp,
                                inv_out,
                                out,
                                0,
                                None,
                                None,
                                self._env,
                            ),
                        ]
                        run_judge.add_prerequisite(invalidate)
        return jobs

    def _compute_result(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        result["judge_outs"] = set()
        for job in self.jobs:
            if isinstance(job, RunChecker):
                if isinstance(job, RunCMSJudge):
                    result["judge_outs"].add(job.points_file)
                result["judge_outs"].add(job.judge_log_file)

        return result


def checker_job(
    input_: InputPath,
    output: OutputPath,
    correct_output: OutputPath,
    test: int,
    seed: Optional[int],
    expected_verdict: Optional[Verdict],
    env: Env,
) -> RunBatchChecker:
    """Returns JudgeJob according to contest type."""
    if env.config.out_check == OutCheck.diff:
        return RunDiffChecker(
            env, test, input_, output, correct_output, expected_verdict
        )

    if env.config.out_check == OutCheck.tokens:
        return RunTokenChecker(
            env, test, input_, output, correct_output, expected_verdict
        )
    elif env.config.out_check == OutCheck.shuffle:
        return RunShuffleChecker(
            env, test, input_, output, correct_output, expected_verdict
        )

    if env.config.out_judge is None:
        raise ValueError(f"Unset judge for out_check={env.config.out_check.name}")

    if env.config.judge_type == JudgeType.cms_batch:
        return RunCMSBatchJudge(
            env,
            env.config.out_judge,
            test,
            input_,
            output,
            correct_output,
            expected_verdict,
        )
    else:
        return RunOpendataV1Judge(
            env,
            env.config.out_judge,
            test,
            input_,
            output,
            correct_output,
            seed,
            expected_verdict,
        )
