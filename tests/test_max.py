import os
import unittest

from util import TestFixtureVariant


class TestMax(TestFixtureVariant):
    @property
    def fixture_path(self) -> str:
        return "fixtures/max/"

    def set_env(self):
        os.environ["DEBUG"] = "false"


if __name__ == "__main__":
    unittest.main(verbosity=2)
