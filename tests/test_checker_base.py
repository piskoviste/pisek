from decimal import Decimal
import os
import tempfile
import unittest
from unittest import mock

from pisek.jobs.jobs import PipelineItemFailure
from pisek.task_jobs.checker.checker_base import RunChecker
from pisek.task_jobs.run_result import RunResultKind
from pisek.task_jobs.solution.solution_result import RelativeSolutionResult, Verdict
from pisek.utils.paths import InputPath, LogPath


class StubRunChecker(RunChecker):
    def _get_solution_run_res_kind(self) -> RunResultKind:
        return RunResultKind.OK

    def _check(self) -> RelativeSolutionResult:
        raise AssertionError("Result should be mocked")

    def _checking_message(self) -> str:
        return "output sample.out"


class TestExpectedVerdictFeedback(unittest.TestCase):
    def _checker(self, log_file: LogPath) -> StubRunChecker:
        env = mock.MagicMock()
        env.get_accessed.return_value = set()
        env.colored.side_effect = lambda message, color: message
        return StubRunChecker(
            env=env,
            name="Check sample",
            test=0,
            checker_name="judge",
            input_=InputPath.new("sample.in"),
            checker_log_file=log_file,
            expected_verdict=Verdict.ok,
        )

    def _wrong_answer(self) -> RelativeSolutionResult:
        return RelativeSolutionResult(
            verdict=Verdict.wrong_answer,
            message=None,
            relative_points=Decimal(0),
        )

    def test_verdict_mismatch_includes_checker_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_file = LogPath(os.path.join(directory, "sample.judge.log"))
            with open(log_file.path, "w") as file:
                file.write("expected integer, got token\n")

            checker = self._checker(log_file)
            with mock.patch.object(
                checker, "_get_solution_result", return_value=self._wrong_answer()
            ):
                with self.assertRaises(PipelineItemFailure) as error:
                    checker._run()

        self.assertIn("should have got verdict", str(error.exception))
        self.assertIn("judge log:", str(error.exception))
        self.assertIn(log_file.path, str(error.exception))
        self.assertIn("expected integer, got token", str(error.exception))

    def test_verdict_mismatch_without_checker_log(self) -> None:
        checker = self._checker(LogPath("missing.judge.log"))
        with mock.patch.object(
            checker, "_get_solution_result", return_value=self._wrong_answer()
        ):
            with self.assertRaises(PipelineItemFailure) as error:
                checker._run()

        self.assertNotIn("judge log:", str(error.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
