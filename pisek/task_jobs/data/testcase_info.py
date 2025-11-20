# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2023        Daniel Skýpala <daniel@honza.info>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Any

from pisek.env.env import Env
from pisek.task_jobs.task_job import TaskJob
from pisek.utils.paths import (
    TESTS_DIR,
    INPUTS_LIST,
    InputPath,
    IInputPath,
    IOutputPath,
    OutputPath,
    TaskPath,
)


class TestcaseGenerationMode(StrEnum):
    static = auto()
    mixed = auto()
    generated = auto()


@dataclass(frozen=True, order=True)
class TestcaseInfo:
    generation_mode: TestcaseGenerationMode
    name: str
    repeat: int = 1
    seeded: bool = True

    @staticmethod
    def generated(name: str, repeat: int = 1, seeded: bool = True) -> "TestcaseInfo":
        return TestcaseInfo(TestcaseGenerationMode.generated, name, repeat, seeded)

    @staticmethod
    def mixed(name: str) -> "TestcaseInfo":
        return TestcaseInfo(TestcaseGenerationMode.mixed, name, 1, False)

    @staticmethod
    def static(name: str) -> "TestcaseInfo":
        return TestcaseInfo(TestcaseGenerationMode.static, name, 1, False)

    def input_path(
        self, seed: int | None = None, solution: str | None = None
    ) -> IInputPath:
        filename = self.name
        if self.seeded:
            assert seed is not None
            filename += f"_{seed:016x}"
        filename += ".in"

        return InputPath.new(filename, solution=solution)

    def reference_output(
        self, env: Env, seed: int | None = None, solution: str | None = None
    ) -> IOutputPath:
        is_static = self.generation_mode == TestcaseGenerationMode.static

        input_path = self.input_path(seed, solution=env.config.primary_solution)
        path: IOutputPath
        if is_static:
            path = OutputPath.static(input_path.replace_suffix(".out").name)
        else:
            path = input_path.to_output()

        if solution is not None:
            path = OutputPath(TESTS_DIR, solution, path.name).to_reference_output()

        return path

    def to_str(self) -> str:
        return f"{self.generation_mode} {self.name} repeat={self.repeat} seeded={str(self.seeded).lower()}"

    @staticmethod
    def from_str(line: str) -> "TestcaseInfo":
        line = line.rstrip("\n")
        if not line:
            raise ValueError("Line empty")

        args = line.split(" ")

        generation_mode = TestcaseGenerationMode(args[0])
        input_name = args[1]
        info_args: dict[str, Any] = {}

        for arg in args[2:]:
            if not arg.strip():
                raise ValueError("Argument empty. (Check whitespace.)")

            if "=" not in arg:
                raise ValueError("Missing '='")
            parts = arg.split("=")
            if len(parts) != 2:
                raise ValueError("Too many '='")
            arg_name, arg_value = parts
            if arg_name in info_args:
                raise ValueError(f"Repeated key '{arg_name}'")
            elif arg_name == "repeat":
                try:
                    repeat_times = int(arg_value)
                    assert repeat_times > 0
                except (ValueError, AssertionError):
                    raise ValueError("'repeat' should be a positive number")

                info_args[arg_name] = repeat_times
            elif arg_name == "seeded":
                if arg_value not in ("true", "false"):
                    raise ValueError("'seeded' should be 'true' or 'false'")
                info_args[arg_name] = arg_value == "true"
            else:
                raise ValueError(f"Unknown argument: '{arg_name}'")

        if not info_args.get("seeded", True) and info_args.get("repeat", 1) > 1:
            raise ValueError("For an unseeded input 'repeat' must be '1'")

        return TestcaseInfo(generation_mode, input_name, **info_args)


class ExportInputsList(TaskJob):
    def __init__(self, env: Env, testcases: list[TestcaseInfo]) -> None:
        self._testcases = testcases
        super().__init__(env=env, name=f"Export inputs list")

    def _run(self) -> None:
        assert list(sorted(self._testcases)) == self._testcases
        with self._open_file(TaskPath(TESTS_DIR, INPUTS_LIST), "w") as f:
            for testcase in self._testcases:
                f.write(testcase.to_str() + "\n")
