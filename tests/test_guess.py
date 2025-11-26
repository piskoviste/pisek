import unittest

from util import TestFixtureVariant


class TestGuess(TestFixtureVariant):
    @property
    def fixture_path(self) -> str:
        return "fixtures/guess/"


if __name__ == "__main__":
    unittest.main(verbosity=2)
