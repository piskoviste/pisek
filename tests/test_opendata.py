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

from util import TestFixture, modify_config

from pisek.user_errors import UserError
from pisek.task_jobs.data.testcase_info import TestcaseGenerationMode
from pisek.task_jobs.solution.solution_result import Verdict
from pisek.opendata.types import OpendataTestcaseInfo, OpendataVerdict
from pisek.opendata.lib import Task, BuiltTask


class TestFixtureOpendata(TestFixture):
    def expecting_success(self) -> bool:
        return True

    def modify_task(self) -> None:
        pass

    @property
    def _testcase_files(self) -> list[str]:
        files = []
        for file in [self.input_path, self.output_path, self.contestant_path]:
            if file is not None:
                files.append(file)
        return files

    def created_files(self):
        return [os.path.basename(file) for file in self._testcase_files]

    def runTest(self) -> None:
        if not self.fixture_path:
            return

        self.log_files()
        task = Task(self.task_dir)

        self.built_task: BuiltTask

        self.input_path: str | None = None
        self.output_path: str | None = None
        self.contestant_path: str | None = None

        @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
        @unittest.mock.patch("sys.stderr", new_callable=io.StringIO)
        def run(*args) -> bool:
            try:
                self.modify_task()
                self._build_task_dir = tempfile.mkdtemp(prefix="pisek-test_")
                self.built_task = task.build(self._build_task_dir)
                self.run_opendata_test()
                return True
            except UserError as e:
                print(e)
                return False

        self.assertEqual(run(), self.expecting_success())

        for file in self._testcase_files:
            self.assertTrue(os.path.isfile(file))

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
        return "fixtures/sum_kasiopea/"

    def init_testcase(self, name: str) -> None:
        self.input_path = os.path.join(self.task_dir, f"{name}.opendata.in")
        self.output_path = os.path.join(self.task_dir, f"{name}.opendata.out")
        self.testcase = self.built_task.get_testcase(
            name, int(name), int("deadbeef", 16), self.input_path, self.output_path
        )

    def create_contestant_file(self, content: str | bytes) -> None:
        self.contestant_path = os.path.join(self.task_dir, "02.out")

        if isinstance(content, bytes):
            with open(self.contestant_path, "xb") as f:
                f.write(content)
        else:
            with open(self.contestant_path, "x") as f:
                f.write(content)


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
    def run_opendata_test(self) -> None:
        self.init_testcase("01")
        assert self.input_path is not None
        assert self.output_path is not None

        self.testcase.gen_input()
        self.assertTrue(os.path.exists(self.input_path))
        self.testcase.gen_output()
        self.assertTrue(os.path.exists(self.output_path))
        self.assertEqual(
            self.testcase.check(self.output_path),
            OpendataVerdict(Verdict.ok, None, Decimal(4), None, None),
        )


class TestSumKasiopeaOpendataCheckRightaway(TestSumKasiopeaOpendataBuild):
    def run_opendata_test(self) -> None:
        self.init_testcase("02")
        self.assertEqual(
            self.testcase.check(os.path.join(self.task_dir, "sample.out")),
            OpendataVerdict(Verdict.wrong_answer, None, Decimal(0), None, None),
        )


class TestSumKasiopeaOpendataCheckBinary(TestSumKasiopeaOpendataBuild):
    def run_opendata_test(self):
        self.init_testcase("02")
        self.create_contestant_file(b"\x07\n")

        self.assertEqual(
            self.testcase.check(os.path.join(self.task_dir, self.contestant_path)),
            OpendataVerdict(
                Verdict.normalization_fail,
                "File contains non-printable character (code 7 at position 0)",
                Decimal(0),
                None,
                None,
            ),
        )


class TestSumKasiopeaOpendataJudge(TestSumKasiopeaOpendataBuild):
    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config["tests"]["out_check"] = "judge"
            raw_config["tests"]["out_judge"] = "judge"
            raw_config["tests"]["judge_type"] = "opendata-v2"

        modify_config(self.task_dir, modification_fn)

    def run_opendata_test(self):
        self.init_testcase("02")
        self.create_contestant_file("0\n")

        self.assertEqual(
            self.testcase.check(os.path.join(self.task_dir, self.contestant_path)),
            OpendataVerdict(
                Verdict.wrong_answer,
                "Wrong answer",
                Decimal(0),
                None,
                None,
            ),
        )


if __name__ == "__main__":
    unittest.main()
