"""
A module for testing pisek itself. The strategy is to take a functioning
fixture of a task and then break it in various small ways to see whether
pisek catches the problem.
"""

from decimal import Decimal
import io
import tempfile
import os
import shutil
import unittest

from util import TestFixture

from pisek.user_errors import UserError
from pisek.task_jobs.data.testcase_info import TestcaseGenerationMode
from pisek.task_jobs.solution.solution_result import Verdict
from pisek.opendata.types import OpendataTestcaseInfo, OpendataVerdict
from pisek.opendata.lib import Task, BuiltTask


class TestFixtureOpendata(TestFixture):
    def expecting_success(self) -> bool:
        return True

    def runTest(self) -> None:
        if not self.fixture_path:
            return

        self.log_files()
        task = Task(self.task_dir)

        self.built_task: BuiltTask

        @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
        @unittest.mock.patch("sys.stderr", new_callable=io.StringIO)
        def run(*args) -> bool:
            try:
                self._build_task_dir = tempfile.mkdtemp(prefix="pisek-test_")
                self.built_task = task.build(self._build_task_dir)
                self.run_opendata_test()
                return True
            except UserError:
                return False

        self.assertEqual(run(), self.expecting_success())

        self.check_end_state()
        self.check_files()

    def tearDown(self) -> None:
        if not self.fixture_path:
            return

        assert self._build_task_dir.startswith(
            "/tmp"
        ) or self._build_task_dir.startswith("/var")
        shutil.rmtree(self._build_task_dir)

    def check_end_state(self):
        # Here we can verify whether some conditions hold when Pisek finishes,
        # making sure that the end state is reasonable
        pass

    def run_opendata_test(self):
        pass


class TestSumKasiopeaOpendataBuild(TestFixtureOpendata):
    @property
    def fixture_path(self) -> str:
        return "../fixtures/sum_kasiopea/"


class TestSumKasiopeaOpendataListInputs(TestSumKasiopeaOpendataBuild):
    def run_opendata_test(self):
        self.assertEqual(
            self.built_task.inputs_list(),
            {
                0: [
                    OpendataTestcaseInfo(
                        TestcaseGenerationMode.static, "sample", 1, False
                    )
                ],
                1: [
                    OpendataTestcaseInfo(
                        TestcaseGenerationMode.generated, "01", 1, True
                    )
                ],
                2: [
                    OpendataTestcaseInfo(
                        TestcaseGenerationMode.generated, "02", 1, True
                    )
                ],
            },
        )


class TestSumKasiopeaOpendataSequential(TestSumKasiopeaOpendataBuild):
    def created_files(self):
        return ["01.in", "01.out"]

    def run_opendata_test(self):
        input_path = os.path.join(self.task_dir, "01.in")
        output_path = os.path.join(self.task_dir, "01.out")

        testcase = self.built_task.get_testcase(
            "01", 1, int("deadbeef", 16), input_path, output_path
        )
        testcase.gen_input()
        self.assertTrue(os.path.exists(input_path))
        testcase.gen_output()
        self.assertTrue(os.path.exists(output_path))
        self.assertEqual(
            testcase.judge(output_path),
            OpendataVerdict(Verdict.ok, None, Decimal(4), None, None),
        )


class TestSumKasiopeaOpendataJudgeRightaway(TestSumKasiopeaOpendataBuild):
    def created_files(self):
        return ["02.in", "02.out"]

    def run_opendata_test(self):
        input_path = os.path.join(self.task_dir, "02.in")
        output_path = os.path.join(self.task_dir, "02.out")

        testcase = self.built_task.get_testcase(
            "02", 2, int("deadbeef", 16), input_path, output_path
        )
        self.assertEqual(
            testcase.judge(os.path.join(self.task_dir, "sample.out")),
            OpendataVerdict(Verdict.wrong_answer, None, Decimal(0), None, None),
        )
        self.assertTrue(os.path.exists(input_path))
        self.assertTrue(os.path.exists(output_path))


class TestSumKasiopeaOpendataJudgeBinary(TestSumKasiopeaOpendataBuild):
    def created_files(self):
        return ["02.in", "02.out", "02.ok"]

    def run_opendata_test(self):
        input_path = os.path.join(self.task_dir, "02.in")
        output_path = os.path.join(self.task_dir, "02.ok")
        contestant_path = os.path.join(self.task_dir, "02.out")
        with open(contestant_path, "xb") as f:
            f.write(b"\x07\n")

        testcase = self.built_task.get_testcase(
            "02", 2, int("deadbeef", 16), input_path, output_path
        )
        self.assertEqual(
            testcase.judge(os.path.join(self.task_dir, contestant_path)),
            OpendataVerdict(
                Verdict.normalization_fail,
                "File contains non-printable character (code 7 at position 0)",
                Decimal(0),
                None,
                None,
            ),
        )
        self.assertTrue(os.path.exists(input_path))
        self.assertTrue(os.path.exists(output_path))


if __name__ == "__main__":
    unittest.main()
