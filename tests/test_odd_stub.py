import unittest

from util import TestFixtureVariant, modify_config


class TestOddStub(TestFixtureVariant):
    @property
    def fixture_path(self) -> str:
        return "fixtures/odd_stub/"


class TestBigInput(TestOddStub):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config.add_section("limits")
            raw_config["limits"]["input_max_size"] = "1"

        modify_config(self.task_dir, modification_fn)


class TestBigOutput(TestOddStub):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config.add_section("limits")
            raw_config["limits"]["output_max_size"] = "1"

        modify_config(self.task_dir, modification_fn)


if __name__ == "__main__":
    unittest.main(verbosity=2)
