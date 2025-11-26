import unittest

from util import TestFixtureVariant


class TestCmsBatch(TestFixtureVariant):
    @property
    def fixture_path(self) -> str:
        return "examples/cms-batch/"


class TestOpendata(TestFixtureVariant):
    @property
    def time_limit(self) -> float | None:
        return 1.0

    @property
    def fixture_path(self) -> str:
        return "examples/opendata/"


if __name__ == "__main__":
    unittest.main(verbosity=2)
