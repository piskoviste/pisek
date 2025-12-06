import os

import unittest

from pisek.utils.paths import TESTS_DIR, GENERATED_SUBDIR
from util import TestFixtureVariant, overwrite_file, modify_config


class TestSumCMS(TestFixtureVariant):
    @property
    def fixture_path(self) -> str:
        return "fixtures/sum_cms/"


class TestMissingGenerator(TestSumCMS):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        os.remove(os.path.join(self.task_dir, "gen.py"))


class TestGeneratorDoesNotCreateTests(TestSumCMS):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        overwrite_file(self.task_dir, "gen.py", "gen_dummy.py")


class TestMissingInputFilesForTest(TestSumCMS):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        overwrite_file(self.task_dir, "gen.py", "gen_incomplete.py")


class TestOldInputsDeleted(TestSumCMS):
    """Do we get rid of out-of-date inputs?"""

    def modify_task(self) -> None:
        self.inputs_dir = os.path.join(self.task_dir, TESTS_DIR, GENERATED_SUBDIR)

        os.makedirs(os.path.join(self.inputs_dir), exist_ok=True)

        with open(os.path.join(self.inputs_dir, "01_outdated.in"), "w") as f:
            # This old input does not conform to the test! Get rid of it.
            f.write("-3 -2\n")

    def check_end_state(self) -> None:
        self.assertNotIn("01_outdated.in", os.listdir(self.inputs_dir))


class TestDifferentlyScoringSolution(TestSumCMS):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        overwrite_file(
            self.task_dir, "solve_0b.py", "solve_3b.cpp", new_file_name="solve_0b.cpp"
        )


class TestNoSolutions(TestSumCMS):
    def modify_task(self) -> None:
        def modification_fn(raw_config):
            for section in raw_config.sections():
                if section.startswith("solution_"):
                    del raw_config[section]

        modify_config(self.task_dir, modification_fn)


class TestPartialJudge(TestSumCMS):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        overwrite_file(self.task_dir, "judge.cpp", "judge_no_partial.cpp")


class TestInvalidJudgeScore(TestSumCMS):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        overwrite_file(self.task_dir, "judge.cpp", "judge_invalid_score.cpp")


class TestStrictValidator(TestSumCMS):
    """A validator whose bounds are stricter than what the generator creates."""

    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        overwrite_file(self.task_dir, "validate.py", "validate_strict.py")


class TestDirtySample(TestSumCMS):
    """Sample without newline at the end."""

    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        with open(os.path.join(self.task_dir, "sample_01.in"), "w") as f:
            f.write("1 2")


class TestNoLFInStrictTextInput(TestSumCMS):
    """Input without newline at the end with in_format=text."""

    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config["tests"]["in_gen"] = "gen_no_lf"
            raw_config["tests"].pop("validator")
            raw_config["tests"].pop("validator_type")

        modify_config(self.task_dir, modification_fn)


class TestNoLFInTextInput(TestSumCMS):
    """Input without newline at the end with in_format=text."""

    def expecting_success(self) -> bool:
        return True

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config["tests"]["in_format"] = "text"
            raw_config["tests"]["in_gen"] = "gen_no_lf"
            raw_config["tests"].pop("validator")
            raw_config["tests"].pop("validator_type")

        modify_config(self.task_dir, modification_fn)


class TestNoLFInBinaryInput(TestSumCMS):
    """Input without newline at the end with in_format=binary."""

    def expecting_success(self) -> bool:
        return True

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config["tests"]["in_format"] = "binary"
            raw_config["tests"]["in_gen"] = "gen_no_lf"
            raw_config["tests"].pop("validator")
            raw_config["tests"].pop("validator_type")

        modify_config(self.task_dir, modification_fn)


class TestNoLFInTextOutput(TestSumCMS):
    """Output without newline at the end with out_format=text."""

    def expecting_success(self) -> bool:
        return True

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config["tests"]["out_format"] = "text"
            raw_config["solution_solve_no_lf"]["tests"] = "1111"

        modify_config(self.task_dir, modification_fn)


class TestNoLFInBinaryOutput(TestSumCMS):
    """Output without newline at the end with out_format=binary."""

    def expecting_success(self) -> bool:
        return True

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config["tests"]["out_format"] = "binary"
            raw_config["solution_solve_no_lf"]["tests"] = "1111"

        modify_config(self.task_dir, modification_fn)


class TestRustJudge(TestSumCMS):
    """A judge written in Rust."""

    def expecting_success(self) -> bool:
        return True

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config["tests"]["out_judge"] = "judge_rust"
            raw_config["tests"]["judge_needs_out"] = "no"

        modify_config(self.task_dir, modification_fn)


if __name__ == "__main__":
    unittest.main(verbosity=2)
