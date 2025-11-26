"""
Tests the command-line interface.
"""

import os

import unittest
from io import StringIO
from unittest import mock

from util import TestFixture

from pisek.__main__ import main


class TestCLI(TestFixture):
    @property
    def fixture_path(self) -> str:
        return "fixtures/sum_cms/"

    def args(self) -> list[list[str]]:
        return [["test", "--time-limit", "0.2"]]

    def runTest(self) -> None:
        if not self.fixture_path:
            return

        self.log_files()

        with mock.patch("sys.stdout", new=StringIO()) as std_out:
            with mock.patch("sys.stderr", new=StringIO()) as std_err:
                for args_i in self.args():
                    result = main(args_i)

                    self.assertFalse(
                        result,
                        f"Command failed: {' '.join(args_i)}",
                    )

        self.check_files()


class TestCLITestSolution(TestCLI):
    def args(self) -> list[list[str]]:
        return [["test", "solutions", "solve"]]


class TestCLITestGenerator(TestCLI):
    def args(self) -> list[list[str]]:
        return [["test", "generator"]]


class TestCLIClean(TestCLI):
    def args(self) -> list[list[str]]:
        return [["clean"]]


class TestCLITestingLog(TestCLI):
    def args(self) -> list[list[str]]:
        return [["test", "--testing-log"]]

    def created_files(self) -> list[str]:
        return ["testing_log.json"]


class TestCLIVisualize(TestCLI):
    def args(self) -> list[list[str]]:
        return [["test", "--testing-log"], ["visualize"]]

    def created_files(self) -> list[str]:
        return ["testing_log.json"]


class TestCLIExport(TestCLI):
    @property
    def fixture_path(self) -> str:
        return "fixtures/guess/"

    def args(self) -> list[list[str]]:
        return [["config", "export", "config"], ["test"]]

    def created_files(self) -> list[str]:
        return ["exported-config"]


if __name__ == "__main__":
    unittest.main(verbosity=2)
