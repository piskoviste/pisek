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

from typing import Optional

from pisek.env.env import Env
from pisek.utils.paths import IInputPath, IOutputPath
from pisek.config.config_types import OutCheck, JudgeType
from pisek.task_jobs.solution.solution_result import Verdict

from pisek.task_jobs.checker.checker_base import RunBatchChecker
from pisek.task_jobs.checker.diff_checker import RunDiffChecker
from pisek.task_jobs.checker.judgelib_checker import RunTokenChecker, RunShuffleChecker
from pisek.task_jobs.checker.cms_judge import RunCMSBatchJudge
from pisek.task_jobs.checker.opendata_judge import (
    RunOpendataV1Judge,
    RunOpendataV2Judge,
)


def checker_job(
    input_: IInputPath,
    output: IOutputPath,
    correct_output: IOutputPath,
    test: int,
    seed: Optional[int],
    expected_verdict: Optional[Verdict],
    env: Env,
) -> RunBatchChecker:
    """Returns JudgeJob according to contest type."""
    if env.config.tests.out_check == OutCheck.diff:
        return RunDiffChecker(
            env, test, input_, output, correct_output, expected_verdict
        )

    if env.config.tests.out_check == OutCheck.tokens:
        return RunTokenChecker(
            env, test, input_, output, correct_output, expected_verdict
        )
    elif env.config.tests.out_check == OutCheck.shuffle:
        return RunShuffleChecker(
            env, test, input_, output, correct_output, expected_verdict
        )

    if env.config.tests.out_judge is None:
        raise ValueError(f"Unset judge for out_check={env.config.tests.out_check.name}")

    if env.config.tests.judge_type == JudgeType.cms_batch:
        return RunCMSBatchJudge(
            env,
            env.config.tests.out_judge,
            test,
            input_,
            output,
            correct_output,
            expected_verdict,
        )
    elif env.config.tests.judge_type == JudgeType.opendata_v1:
        return RunOpendataV1Judge(
            env,
            env.config.tests.out_judge,
            test,
            input_,
            output,
            correct_output,
            seed,
            expected_verdict,
        )
    elif env.config.tests.judge_type == JudgeType.opendata_v2:
        return RunOpendataV2Judge(
            env,
            env.config.tests.out_judge,
            test,
            input_,
            output,
            correct_output,
            seed,
            expected_verdict,
        )
    else:
        raise ValueError(f"Unknown judge type: {env.config.tests.judge_type}")
