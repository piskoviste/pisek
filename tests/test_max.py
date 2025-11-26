import unittest

from util import TestFixtureVariant


class TestMax(TestFixtureVariant):
    @property
    def fixture_path(self) -> str:
        return "fixtures/max/"


if __name__ == "__main__":
    unittest.main(verbosity=2)
