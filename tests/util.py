import configparser
import io
import os
import shutil
import tempfile
from typing import Callable
import unittest
from unittest import mock

from pisek.user_errors import UserError
from pisek.config import config_hierarchy
from pisek.__main__ import test_task_path
from pisek.utils.util import clean_task_dir
from pisek.utils.pipeline_tools import assert_task_dir


class TestFixture(unittest.TestCase):
    @property
    def fixture_path(self) -> str | None:
        return None

    def set_env(self) -> None:
        pass

    def setUp(self) -> None:
        os.environ["LOG_LEVEL"] = "debug"

        if not self.fixture_path:
            return
        assert self.fixture_path[-1] == "/"

        self.task_dir_orig = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", self.fixture_path)
        )
        self.fixtures_dir = tempfile.mkdtemp(prefix="pisek-test_")
        self.task_dir = os.path.join(
            self.fixtures_dir, os.path.basename(os.path.dirname(self.fixture_path))
        )

        # shutil.copytree() requires that the destination directory does not exist,
        os.rmdir(self.fixtures_dir)
        shutil.copytree(
            self.task_dir_orig,
            self.task_dir,
        )

        pisek_dir = os.path.join(self.task_dir_orig, "../pisek")
        if os.path.exists(pisek_dir):
            os.environ["PISEK_DIRECTORY"] = "../pisek"
            shutil.copytree(
                pisek_dir,
                os.path.join(self.fixtures_dir, "pisek"),
            )

        self.set_env()

        assert_task_dir(
            self.task_dir,
            os.environ.get("PISEK_DIRECTORY"),
            config_hierarchy.DEFAULT_CONFIG_FILENAME,
        )
        clean_task_dir(self.task_dir)

        self.cwd_orig = os.getcwd()
        os.chdir(self.task_dir)

    def runTest(self) -> None:
        # Implement this!
        pass

    def tearDown(self) -> None:
        if not self.fixture_path:
            return

        os.chdir(self.cwd_orig)

        assert self.fixtures_dir.startswith("/tmp") or self.fixtures_dir.startswith(
            "/var"
        )
        shutil.rmtree(self.fixtures_dir)

    def log_files(self) -> None:
        """Log all files for checking whether new ones have been created."""
        self.original_files = os.listdir(self.task_dir)

    def created_files(self) -> list[str]:
        """Additional files that are expected to be created."""
        return []

    def check_files(self) -> None:
        """
        Check whether there are no new unexpected files.
        Ignored:
            .pisek_cache data/* build/*
        """
        directories = ["build", "tests", ".pisek"]

        all_paths = set(self.original_files + directories + self.created_files())

        for path in os.listdir(self.task_dir):
            self.assertIn(
                path,
                all_paths,
                f"Pisek generated new file {path}.",
            )


class TestFixtureVariant(TestFixture):
    def expecting_success(self) -> bool:
        return True

    def catch_exceptions(self) -> bool:
        return False

    def modify_task(self) -> None:
        """
        Code which modifies the task before running the tests should go here.
        For example, if we want to check that the presence of `sample.in` is
        correctly checked for, we would remove the file here.
        """
        pass

    @property
    def time_limit(self) -> float | None:
        return None

    def runTest(self) -> None:
        if not self.fixture_path:
            return

        self.set_env()
        self.modify_task()
        self.log_files()

        # We lower the time limit to make the self-tests run faster. The solutions
        # run instantly, with the exception of `solve_slow_4b`, which takes 10 seconds
        # and we want to consider it a time limit
        @mock.patch("sys.stdout", new_callable=io.StringIO)
        @mock.patch("sys.stderr", new_callable=io.StringIO)
        def run(*args) -> bool:
            try:
                test_task_path(
                    self.task_dir,
                    inputs=1,
                    strict=False,
                    full=False,
                    time_limit=self.time_limit,
                    plain=False,
                    pisek_dir=os.environ.get("PISEK_DIRECTORY"),
                )
                return True
            except UserError:
                return False

        self.assertEqual(run(), self.expecting_success())

        self.check_end_state()
        self.check_files()

    def check_end_state(self):
        # Here we can verify whether some conditions hold when Pisek finishes,
        # making sure that the end state is reasonable
        pass


def overwrite_file(
    task_dir: str, old_file: str, new_file: str, new_file_name: str | None = None
) -> None:
    os.remove(os.path.join(task_dir, old_file))
    shutil.copy(
        os.path.join(task_dir, new_file),
        os.path.join(task_dir, new_file_name or old_file),
    )


def modify_config(
    task_dir: str, modification_fn: Callable[[configparser.ConfigParser], None]
) -> None:
    """
    `modification_fn` accepts the config (in "raw" ConfigParser format) and may
    modify it. The modified version is then saved.

    For example, if we want to change the evaluation method ("out_check")
    from `diff` to `judge`, we would do that in `modification_fn` via:
        config["tests"]["out_check"] = "judge"
        config["tests"]["out_judge"] = "judge"  # To specify the judge program file
    """

    config = config_hierarchy.new_config_parser()
    config_path = os.path.join(task_dir, config_hierarchy.DEFAULT_CONFIG_FILENAME)
    read_files = config.read(config_path)
    if not read_files:
        raise FileNotFoundError(f"Missing configuration file {config_path}.")

    modification_fn(config)

    with open(config_path, "w") as f:
        config.write(f)
