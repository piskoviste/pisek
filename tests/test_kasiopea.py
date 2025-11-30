"""
A module for testing pisek itself. The strategy is to take a functioning
fixture of a task and then break it in various small ways to see whether
pisek catches the problem.
"""

import unittest
import os

from util import TestFixtureVariant, overwrite_file, modify_config


class TestSumKasiopea(TestFixtureVariant):
    @property
    def fixture_path(self) -> str:
        return "fixtures/sum_kasiopea/"


class TestMissingSampleIn(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        os.remove(os.path.join(self.task_dir, "sample.in"))


class TestMissingSampleOut(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        os.remove(os.path.join(self.task_dir, "sample.out"))


class TestWrongSampleOut(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        with open(os.path.join(self.task_dir, "sample.out"), "a") as f:
            f.write("0\n")


class TestMissingGenerator(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        os.remove(os.path.join(self.task_dir, "gen.cpp"))


class TestBadGenerator(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        generator_filename = os.path.join(self.task_dir, "gen.cpp")
        os.remove(generator_filename)

        with open(generator_filename, "w") as f:
            f.write("int main() { return 0; }\n")


class TestPythonGenerator(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return True

    def modify_task(self) -> None:
        overwrite_file(self.task_dir, "gen.cpp", "gen_2.py", new_file_name="gen.py")


class TestNonHexaPythonGenerator(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        os.remove(os.path.join(self.task_dir, "gen.cpp"))

        new_program = [
            "#!/usr/bin/env python3",
            "import sys",
            "print(sys.argv[1])",
            "print(int(sys.argv[2], 10))",
        ]
        with open(os.path.join(self.task_dir, "gen.py"), "w") as f:
            f.write("\n".join(new_program))


class TestNonHexaGenerator(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        os.remove(os.path.join(self.task_dir, "gen.cpp"))

        new_program = [
            "#include <iostream>",
            "#include <string>",
            "int main(int argc, char* argv[]) {",
            "if (argc != 3) { return 1; }",
            "std::cout << argv[1] << std::endl;"
            "std::cout << std::strtoull(argv[2], NULL, 10) << std::endl;"
            "return 0;}",
        ]
        with open(os.path.join(self.task_dir, "gen.cpp"), "w") as f:
            f.write("\n".join(new_program))


class TestDifferentlyScoringSolution(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        overwrite_file(
            self.task_dir, "solve_0b.py", "solve_4b.cpp", new_file_name="solve_0b.cpp"
        )


class TestJudge(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return True

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config["tests"]["out_check"] = "judge"
            raw_config["tests"]["out_judge"] = "judge"
            raw_config["tests"]["judge_type"] = "opendata-v2"

        modify_config(self.task_dir, modification_fn)


class TestJudgeWithNoInput(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config["tests"]["judge_needs_in"] = "0"
            raw_config["tests"]["out_check"] = "judge"
            raw_config["tests"]["out_judge"] = "judge"
            raw_config["tests"]["judge_type"] = "opendata-v2"

        modify_config(self.task_dir, modification_fn)


class TestJudgeWithNoOutput(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config["tests"]["judge_needs_out"] = "0"
            raw_config["tests"]["out_check"] = "judge"
            raw_config["tests"]["out_judge"] = "judge"
            raw_config["tests"]["judge_type"] = "opendata-v2"

        modify_config(self.task_dir, modification_fn)


class TestPythonJudge(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return True

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config["tests"]["out_check"] = "judge"
            raw_config["tests"]["out_judge"] = "judge_py"
            raw_config["tests"]["judge_type"] = "opendata-v2"

        modify_config(self.task_dir, modification_fn)


class TestBadJudge(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config["tests"]["out_check"] = "judge"
            raw_config["tests"]["out_judge"] = "judge_bad"
            raw_config["tests"]["judge_type"] = "opendata-v1"

        modify_config(self.task_dir, modification_fn)


class TestPythonCRLF(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        os.remove(os.path.join(self.task_dir, "solve.py"))

        new_program = [
            "#!/usr/bin/env python3",
            "t = int(input())",
            "for i in range(t):",
            "    a, b = [int(x) for x in input().split()]",
            "    c = a + b",
            "    print(c)",
        ]
        with open(os.path.join(self.task_dir, "solve.py"), "w") as f:
            f.write("\r\n".join(new_program))


class TestStrictValidator(TestSumKasiopea):
    """A validator whose bounds are stricter than what the generator creates."""

    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        overwrite_file(self.task_dir, "validate.py", "validate_strict.py")


class TestDirtySample(TestSumKasiopea):
    """Sample without newline at the end."""

    def expecting_success(self) -> bool:
        return False

    def modify_task(self) -> None:
        sample = ["3", "1 2", "-8 5", "0 0"]
        with open(os.path.join(self.task_dir, "sample.in"), "w") as f:
            f.write("\n".join(sample))


class TestExtraConfigKeys(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return False

    def catch_exceptions(self) -> bool:
        return True

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config["task"]["foo"] = "bar"

        modify_config(self.task_dir, modification_fn)


class TestExtraConfigKeysInTest(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return False

    def catch_exceptions(self) -> bool:
        return True

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config["test01"]["foo"] = "bar"

        modify_config(self.task_dir, modification_fn)


class TestExtraConfigSection(TestSumKasiopea):
    def expecting_success(self) -> bool:
        return False

    def catch_exceptions(self) -> bool:
        return True

    def modify_task(self) -> None:
        def modification_fn(raw_config):
            raw_config.add_section("baz")
            raw_config["baz"]["foo"] = "bar"

        modify_config(self.task_dir, modification_fn)


if __name__ == "__main__":
    unittest.main()
