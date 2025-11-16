import unittest

from util import TestFixtureVariant


class TestGuess(TestFixtureVariant):
    def fixture_path(self):
        return "../fixtures/guess/"


if __name__ == "__main__":
    unittest.main(verbosity=2)
