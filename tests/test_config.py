"""
A module for testing pisek itself. The strategy is to take a functioning
fixture of a task and then break it in various small ways to see whether
pisek catches the problem.
"""

import unittest

from util import modify_config
from test_cms import TestSumCMS


class TestExtraConfigKeys(TestSumCMS):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config["task"]["foo"] = "bar"

        modify_config(self.task_dir, modification_fn)


class TestExtraConfigKeysInTest(TestSumCMS):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config["test01"]["foo"] = "bar"

        modify_config(self.task_dir, modification_fn)


class TestExtraConfigSection(TestSumCMS):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config.add_section("baz")
            raw_config["baz"]["foo"] = "bar"

        modify_config(self.task_dir, modification_fn)


if __name__ == "__main__":
    unittest.main()
