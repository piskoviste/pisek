# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2019 - 2022 Václav Volhejn <vaclav.volhejn@gmail.com>
# Copyright (c)   2019 - 2022 Jiří Beneš <mail@jiribenes.com>
# Copyright (c)   2020 - 2022 Michal Töpfer <michal.topfer@gmail.com>
# Copyright (c)   2022        Jiří Kalvoda <jirikalvoda@kam.mff.cuni.cz>
# Copyright (c)   2023        Daniel Skýpala <daniel@honza.info>
# Copyright (c)   2024        Benjamin Swart <benjaminswart@email.cz>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from decimal import Decimal
from typing import Any, Optional

from pisek.utils.text import pad, tab
from pisek.utils.terminal import right_aligned_text
from pisek.utils.colors import ColorSettings
from pisek.utils.paths import IInputPath

from pisek.jobs.jobs import State, Job, PipelineItemFailure
from pisek.env.env import Env
from pisek.config.config_types import TaskType
from pisek.task_jobs.tools import SanitizeAbstract
from pisek.task_jobs.data.data import SymlinkData
from pisek.task_jobs.solution.verdicts_eval import check_verdicts, compute_verdict
from pisek.task_jobs.task_job import TaskHelper
from pisek.task_jobs.task_manager import TaskJobManager
from pisek.task_jobs.data.testcase_info import TestcaseInfo, TestcaseGenerationMode
from pisek.task_jobs.generator.generator_manager import TestcaseInfoMixin
from pisek.task_jobs.solution.solution_result import Verdict, SolutionResult
from pisek.task_jobs.solution.solution import (
    RunSolution,
    RunBatchSolution,
    RunInteractive,
)
from pisek.task_jobs.checker.checker import checker_job
from pisek.task_jobs.checker.cms_judge import RunCMSJudge
from pisek.task_jobs.checker.checker_base import RunChecker, RunBatchChecker


class SolutionManager(TaskJobManager, TestcaseInfoMixin):
    """Runs a solution and checks if it works as expected."""

    def __init__(self, solution_label: str, generate_inputs: bool) -> None:
        self.solution_label: str = solution_label
        self._generate_inputs = generate_inputs
        self.solution_points: Optional[Decimal] = None
        self.tests: list[TestJobGroup] = []
        self._tests_results: dict[int, Verdict] = {}
        super().__init__(f"Test {solution_label}")

    def _get_jobs(self) -> list[Job]:
        self._solution = self._env.config.solutions[self.solution_label]
        self.is_primary: bool = self._solution.primary

        self._sols: dict[IInputPath, RunSolution] = {}
        self._checkers: dict[IInputPath, RunChecker] = {}
        self._static_out_checkers: dict[IInputPath, RunChecker] = {}

        for sub_num, inputs in self._all_testcases().items():
            self.tests.append(
                TestJobGroup(self._env, sub_num, self._solution.tests[sub_num])
            )
            for inp in inputs:
                self._add_testcase_info_jobs(inp, sub_num)

        return self._jobs

    def _register_skipped_testcase(
        self, testcase_info: TestcaseInfo, seed: Optional[int], test: int
    ) -> None:
        super()._register_skipped_testcase(testcase_info, seed, test)
        input_path = testcase_info.input_path(seed, solution=self.solution_label)
        if self._env.config.test_sections[test].new_in_test(input_path.name):
            self.tests[-1].new_run_jobs.append(self._sols[input_path])
            self.tests[-1].new_jobs.append(self._checkers[input_path])
            self._sols[input_path].require()
        else:
            self.tests[-1].previous_jobs.append(self._checkers[input_path])

    def _add_generate_input_jobs(
        self,
        testcase_info: TestcaseInfo,
        seed: Optional[int],
        test: int,
        test_determinism: bool,
    ) -> None:
        if self._generate_inputs:
            super()._add_generate_input_jobs(
                testcase_info, seed, test, test_determinism
            )

        self._add_job(
            SymlinkData(
                self._env,
                testcase_info.input_path(seed),
                testcase_info.input_path(seed, solution=self.solution_label),
            ),
            new_last=True,
        )

    def _add_respects_seed_jobs(
        self, testcase_info: TestcaseInfo, seeds: list[int], test: int
    ) -> None:
        if self._generate_inputs:
            super()._add_respects_seed_jobs(testcase_info, seeds, test)

    def _add_solution_jobs(
        self,
        testcase_info: TestcaseInfo,
        seed: Optional[int],
        test: int,
    ) -> None:
        input_path = testcase_info.input_path(seed, solution=self.solution_label)

        run_sol: RunSolution
        run_checker: RunChecker
        if self._env.config.task.task_type == TaskType.batch:
            if (
                testcase_info.generation_mode == TestcaseGenerationMode.static
                and self._generate_inputs
            ):
                # Check static outputs against themselves
                inp = testcase_info.input_path(seed)
                out = testcase_info.reference_output(self._env, seed)

                checker_j = checker_job(
                    inp, out, out, test, seed, Verdict.ok, self._env
                )
                self._add_check_output_jobs(out)
                self._add_job(
                    checker_j,
                    prerequisite_name=(
                        "sanitize"
                        if isinstance(self._testcase_last, SanitizeAbstract)
                        else None
                    ),
                )
                self._static_out_checkers[inp] = checker_j

            run_batch_sol, run_checker = self._create_batch_jobs(
                testcase_info, seed, test
            )
            run_sol = run_batch_sol
            self._add_job(run_batch_sol, new_last=True)

            self._add_check_output_jobs(run_batch_sol.output.to_sanitized_output())

            if isinstance(self._testcase_last, SanitizeAbstract):
                run_checker.add_prerequisite(self._testcase_last, "sanitize")

            if self._env.config.tests.judge_needs_out:
                self._add_job(
                    SymlinkData(
                        self._env,
                        testcase_info.reference_output(self._env, seed),
                        testcase_info.reference_output(
                            self._env, seed, solution=self.solution_label
                        ),
                    ),
                    new_last=True,
                )

            self._add_job(run_checker)

        elif self._env.config.task.task_type == TaskType.interactive:
            run_sol = run_checker = self._create_interactive_jobs(input_path, test)
            self._add_job(run_sol)

        self._sols[input_path] = run_sol
        self._checkers[input_path] = run_checker
        self.tests[-1].new_jobs.append(run_checker)
        self.tests[-1].new_run_jobs.append(run_sol)

    def _create_batch_jobs(
        self, testcase_info: TestcaseInfo, seed: Optional[int], test: int
    ) -> tuple[RunBatchSolution, RunBatchChecker]:
        """Create RunSolution and RunBatchChecker jobs for batch task type."""
        input_path = testcase_info.input_path(seed, solution=self.solution_label)
        run_solution = RunBatchSolution(
            self._env,
            self._solution.run,
            self.is_primary,
            input_path,
            input_path.to_output(),
        )

        out = input_path.to_output()
        run_checker = checker_job(
            input_path,
            out,
            testcase_info.reference_output(
                self._env,
                seed,
                solution=(
                    self.solution_label
                    if self._env.config.tests.judge_needs_out
                    else None
                ),
            ),
            test,
            seed,
            None,
            self._env,
        )
        run_checker.add_prerequisite(run_solution, name="run_solution")

        return (run_solution, run_checker)

    def _create_interactive_jobs(self, inp: IInputPath, test: int) -> RunInteractive:
        """Create RunInteractive job for interactive task type."""
        if self._env.config.tests.out_judge is None:
            raise RuntimeError("Unset judge for interactive.")

        return RunInteractive(
            self._env,
            self._solution.run,
            self.is_primary,
            self._env.config.tests.out_judge,
            test,
            inp,
        )

    def update(self):
        """Cancel running on inputs that can't change anything."""
        for test in self.tests:
            if test.definitive():
                test.cancel()

    def get_status(self) -> str:
        msg = self.solution_label
        if self.state == State.cancelled:
            return self._job_bar(msg)

        points = self._format_points(self.solution_points)
        total_points = self._format_points(self._env.config.total_points)

        max_time_f = max((s.slowest_time for s in self.tests), default=0.0)
        max_time = self._format_time(max_time_f)

        if not self.state.finished() or self._env.verbosity == 0:
            header = self._solution_header_verbosity0(
                msg, self.solution_points, max_time_f
            )
            tests_text = "".join(sub.status_verbosity0() for sub in self.tests)
        else:
            header = (
                right_aligned_text(
                    f"{msg}: {points}/{total_points}", f"slowest {max_time}"
                )
                + "\n"
            )
            header = self._colored(header, "cyan")
            tests_text = tab(
                "\n".join(
                    sub.status(self.tests, self._env.verbosity) for sub in self.tests
                )
            )
            if self._env.verbosity == 1:
                tests_text += "\n"

        return header + tests_text

    def _evaluate(self) -> None:
        """Evaluates whether solution preformed as expected."""
        self.solution_points = Decimal(0)
        for sub_job in self.tests:
            self.solution_points += sub_job.points
            self._tests_results[sub_job.num] = sub_job.verdict

        solution_conf = self._env.config.solutions[self.solution_label]
        for sub_job in self.tests:
            sub_job.assert_as_expected()

        points = solution_conf.points
        p_min = solution_conf.points_min
        p_max = solution_conf.points_max

        if points is not None and self.solution_points != points:
            raise PipelineItemFailure(
                f"Solution {self.solution_label} should have gotten {points} but got {self.solution_points} points."
            )
        elif p_min is not None and self.solution_points < p_min:
            raise PipelineItemFailure(
                f"Solution {self.solution_label} should have gotten at least {p_min} but got {self.solution_points} points."
            )
        elif p_max is not None and self.solution_points > p_max:
            raise PipelineItemFailure(
                f"Solution {self.solution_label} should have gotten at most {p_max} but got {self.solution_points} points."
            )

    def _compute_result(self) -> dict[str, Any]:
        result: dict[str, Any] = super()._compute_result()

        def add_checker_out(cj: RunChecker) -> None:
            if cj.result is None or cj.result.verdict not in (
                Verdict.ok,
                Verdict.partial_ok,
                Verdict.wrong_answer,
            ):
                return

            if isinstance(checker_job, RunCMSJudge):
                result["checker_outs"].add(cj.points_file)
            result["checker_outs"].add(cj.checker_log_file)

        result["results"] = {}
        result["checker_outs"] = set()
        for inp, checker_job in self._checkers.items():
            result["results"][inp] = checker_job.result
            add_checker_out(checker_job)

        for checker_job in self._static_out_checkers.values():
            add_checker_out(checker_job)

        result["tests"] = self._tests_results

        return result


class TestJobGroup(TaskHelper):
    """Groups jobs of a single test."""

    def __init__(self, env: Env, num: int, expected_str: str) -> None:
        self._env = env
        self.num = num
        self.test = env.config.test_sections[num]
        self.expected_str = expected_str

        self.new_run_jobs: list[RunSolution] = []
        self.previous_jobs: list[RunChecker] = []
        self.new_jobs: list[RunChecker] = []

        self._canceled: bool = False

    @property
    def all_jobs(self) -> list[RunChecker]:
        return self.previous_jobs + self.new_jobs

    @property
    def points(self) -> Decimal:
        results = self._results(self.all_jobs)
        points = map(lambda r: r.points(self._env, self.test.points), results)
        return min(points, default=Decimal(self.test.max_points))

    @property
    def verdict(self) -> Verdict:
        return compute_verdict(self._verdicts(self.all_jobs))

    @property
    def slowest_time(self) -> float:
        results = self._results(self.all_jobs)
        times = map(lambda r: r.solution_rr.time, results)
        return max(times, default=0.0)

    def _job_results(self, jobs: list[RunChecker]) -> list[Optional[SolutionResult]]:
        return list(map(lambda j: j.result, jobs))

    def _finished_jobs(self, jobs: list[RunChecker]) -> list[RunChecker]:
        return list(filter(lambda j: j.result is not None, jobs))

    def _results(self, jobs: list[RunChecker]) -> list[SolutionResult]:
        filtered = []
        for res in self._job_results(jobs):
            if res is not None:
                filtered.append(res)
        return filtered

    def _verdicts(self, jobs: list[RunChecker]) -> list[Verdict]:
        return list(map(lambda r: r.verdict, self._results(jobs)))

    def status(
        self, all_tests: list["TestJobGroup"], verbosity: Optional[int] = None
    ) -> str:
        verbosity = self._env.verbosity if verbosity is None else verbosity

        if verbosity <= 0:
            return self.status_verbosity0()
        elif verbosity == 1:
            return self.status_verbosity1()
        elif verbosity >= 2:
            return self.status_verbosity2(all_tests)

        raise RuntimeError(f"Unknown verbosity {verbosity}")

    def _verdict_marks(self, jobs: list[RunChecker]) -> str:
        return "".join(job.verdict_mark() for job in jobs)

    def _predecessor_summary(self) -> str:
        if not self.previous_jobs:
            return ""

        verdicts = self._verdicts(self.previous_jobs)
        if not verdicts:
            return "p |"

        _, _, guarantor = self._as_expected(self.previous_jobs)
        if guarantor is not None:
            assert guarantor.result is not None
            verdict = guarantor.result.verdict
        else:
            verdict = compute_verdict(verdicts)

        return f"p{verdict.mark}|"

    def status_verbosity0(self) -> str:
        left_bracket = "["
        right_bracket = "]"
        if self.definitive():
            color = self.verdict.color
            left_bracket = ColorSettings.colored(left_bracket, color)
            right_bracket = ColorSettings.colored(right_bracket, color)

        return (
            left_bracket
            + self._predecessor_summary()
            + self._verdict_marks(self.new_jobs)
            + right_bracket
        )

    def status_verbosity1(self) -> str:
        max_sub_name_len = max(
            len(test.name) for test in self._env.config.test_sections.values()
        )
        max_sub_points_len = max(
            len(self._format_points(sub.max_points))
            for sub in self._env.config.test_sections.values()
        )

        return right_aligned_text(
            f"{self.test.name:<{max_sub_name_len}}  "
            f"{self._format_points(self.points):>{max_sub_points_len}}  "
            f"{self.status_verbosity0()}",
            f"slowest {self._format_time(self.slowest_time)}",
            offset=-2,
        )

    def status_verbosity2(self, all_tests: list["TestJobGroup"]):
        def test_name(num: int) -> str:
            return self._env.config.test_sections[num].name

        text = ""
        max_inp_name_len = max(
            (len(j.input.name) for j in self.new_jobs if j.result is not None),
            default=0,
        )
        test_info = (
            right_aligned_text(
                f"{self.test.name}: {self._format_points(self.points)}/{self._format_points(self.test.max_points)}",
                f"slowest {self._format_time(self.slowest_time)}",
                offset=-2,
            )
            + "\n"
        )
        text += self._env.colored(test_info, "magenta")

        max_pred_name_len = max(
            (len(test_name(pred)) for pred in self.test.all_predecessors),
            default=0,
        )
        for pred in self.test.all_predecessors:
            pred_group = all_tests[pred]
            text += right_aligned_text(
                tab(
                    f"Predecessor {pad(test_name(pred) + ':', max_pred_name_len + 1)}  "
                    f"{pred_group.status_verbosity0()}"
                ),
                f"slowest {self._format_time(pred_group.slowest_time)}",
                offset=-2,
            )
            text += "\n"

        if len(self.test.all_predecessors) and any(
            map(lambda j: j.result, self.new_jobs)
        ):
            text += "\n"

        for job in self.new_jobs:
            if job.result is not None:
                points = ColorSettings.colored(
                    f"({self._format_points(job.result.points(self._env, self.test.points))})",
                    job.result.verdict.color,
                )
                input_verdict = tab(
                    f"{job.input.name:<{max_inp_name_len}} {points}: {job.verdict_text()}"
                )
                text += right_aligned_text(
                    input_verdict,
                    self._format_time(job.result.solution_rr.time),
                    offset=-2,
                )
                text += "\n"

        return text

    def definitive(self) -> bool:
        """Checks whether test jobs have resulted in outcome that cannot be changed."""
        if len(self._results(self.all_jobs)) == len(self.all_jobs):
            return True

        if self._env.all_inputs:
            return False

        if self.expected_str == "X" and not self.verdict.is_zero_point():
            return False  # Cause X is very very special

        return self._as_expected(self.all_jobs)[1]

    def assert_as_expected(self) -> None:
        """Checks this test resulted as expected. Raises PipelineItemFailure otherwise."""
        ok, _, breaker = self._as_expected(self.all_jobs)
        if not ok:
            msg = f"{self.test.name} did not result as expected: '{self.expected_str}'"
            if breaker is not None:
                msg += f"\n{tab(breaker.message())}"
            raise PipelineItemFailure(msg)

    def _as_expected(
        self, jobs: list[RunChecker]
    ) -> tuple[bool, bool, Optional[RunChecker]]:
        finished_jobs = self._finished_jobs(jobs)
        verdicts = self._results(jobs)

        result, definitive, guarantor = check_verdicts(
            list(map(lambda r: r.verdict, verdicts)), self.expected_str
        )

        guarantor_job = None if guarantor is None else finished_jobs[guarantor]

        return result, definitive, guarantor_job

    def cancel(self):
        if self._canceled:
            return

        self._canceled = True
        for job in self.new_run_jobs:
            job.unrequire()
