# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2019 - 2022 Václav Volhejn <vaclav.volhejn@gmail.com>
# Copyright (c)   2019 - 2022 Jiří Beneš <mail@jiribenes.com>
# Copyright (c)   2020 - 2022 Michal Töpfer <michal.topfer@gmail.com>
# Copyright (c)   2022        Jiří Kalvoda <jirikalvoda@kam.mff.cuni.cz>
# Copyright (c)   2023        Daniel Skýpala <daniel@honza.info>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from abc import ABC, abstractmethod
from dataclasses import dataclass
import os
from typing import TYPE_CHECKING
from pisek.config.config_types import DataFormat

if TYPE_CHECKING:
    from pisek.env.env import Env

BUILD_DIR = "build/"
TESTS_DIR = "tests/"
INTERNALS_DIR = ".pisek/"

GENERATED_SUBDIR = "_generated/"
INPUTS_SUBDIR = "_inputs/"
FUZZING_OUTPUTS_SUBDIR = "_fuzzing/"

INPUTS_LIST = "_inputs_list"


@dataclass(frozen=True)
class TaskPath:
    """Class representing a path to task file."""

    path: str

    def __init__(self, *path: str):
        joined_path = os.path.normpath(os.path.join(*path))
        object.__setattr__(self, "path", joined_path)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self.path})"

    def __init_subclass__(cls):
        return super().__init_subclass__()

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    @property
    def abspath(self) -> str:
        return os.path.abspath(self.path)

    def __format__(self, __format_spec: str) -> str:
        match __format_spec:
            case "":
                return self.path
            case "p":
                return self.path
            case "n":
                return self.name
            case _:
                raise ValueError(
                    f"Invalid format specifier '{__format_spec}' for object of type '{self.__class__.__name__}'"
                )

    def __eq__(self, other_path) -> bool:
        if isinstance(other_path, TaskPath):
            return self.path == other_path.path
        else:
            return False

    def __lt__(self, other_path: "TaskPath") -> bool:
        return self.path < other_path.path

    def col(self, env: "Env") -> str:
        return env.colored(
            self.path + ("/" if os.path.isdir(self.path) else ""), "magenta"
        )

    def replace_suffix(self, new_suffix: str) -> "TaskPath":
        path = os.path.splitext(self.path)[0] + new_suffix
        return TaskPath(path)

    def join(self, *path: str) -> "TaskPath":
        return TaskPath(os.path.join(self.path, *path))

    def exists(self) -> bool:
        return os.path.exists(self.path)

    @staticmethod
    def from_abspath(*path: str) -> "TaskPath":
        return TaskPath(os.path.relpath(os.path.join(*path), "."))

    @staticmethod
    def static_path(env: "Env", *path: str) -> "TaskPath":
        return env.config.tests.static_subdir.join(*path)

    @staticmethod
    def executable_path(*path: str) -> "TaskPath":
        return TaskPath(BUILD_DIR, *path)

    @staticmethod
    def data_path(*path: str) -> "TaskPath":
        return TaskPath(TESTS_DIR, *path)

    @staticmethod
    def generated_path(*path: str) -> "TaskPath":
        return TaskPath.data_path(GENERATED_SUBDIR, *path)


# ----- interfaces -----


class IJudgeablePath(TaskPath, ABC):
    @abstractmethod
    def to_checker_log(self, judge: str) -> "LogPath":
        pass


class ISanitizedPath(TaskPath, ABC):
    @abstractmethod
    def to_raw(self, format: DataFormat) -> "IRawPath":
        pass


class IInputPath(ISanitizedPath):
    @abstractmethod
    def to_second(self) -> "IInputPath":
        pass

    @abstractmethod
    def to_output(self) -> "IOutputPath":
        pass

    @abstractmethod
    def to_log(self, program: str) -> "LogPath":
        pass


class IOutputPath(IJudgeablePath, ISanitizedPath):
    @abstractmethod
    def to_reference_output(self) -> "IOutputPath":
        pass

    @abstractmethod
    def to_fuzzing(self, note: str, seed: int) -> "IOutputPath":
        pass


class IRawPath(TaskPath, ABC):
    @abstractmethod
    def to_sanitized_input(self) -> IInputPath:
        pass

    @abstractmethod
    def to_sanitized_output(self) -> IOutputPath:
        pass

    @abstractmethod
    def to_sanitization_log(self) -> "LogPath":
        pass


# ----- paths inside task -----


class JudgeablePath(IJudgeablePath):
    def to_checker_log(self, judge: str) -> "LogPath":
        return LogPath(self.replace_suffix(f".{os.path.basename(judge)}.log").path)


class SanitizedPath(ISanitizedPath):
    def to_raw(self, format: DataFormat) -> "RawPath":
        if format == DataFormat.binary:
            return RawPath(self.path)
        return RawPath(self.path + ".raw")


class InputPath(SanitizedPath, IInputPath):
    @staticmethod
    def new(*path: str, solution: str | None = None) -> "InputPath":
        if solution is None:
            return InputPath(TESTS_DIR, INPUTS_SUBDIR, *path)
        else:
            return InputPath(TESTS_DIR, solution, *path)

    def to_second(self) -> IInputPath:
        return InputPath(self.replace_suffix(".in2").path)

    def to_output(self) -> IOutputPath:
        return OutputPath(self.replace_suffix(f".out").path)

    def to_log(self, program: str) -> "LogPath":
        return LogPath(self.replace_suffix(f".{os.path.basename(program)}.log").path)


class OutputPath(JudgeablePath, SanitizedPath, IOutputPath):
    @staticmethod
    def static(*path) -> "OutputPath":
        return OutputPath(TESTS_DIR, INPUTS_SUBDIR, *path)

    def to_reference_output(self) -> IOutputPath:
        return OutputPath(self.replace_suffix(f".ok").path)

    def to_fuzzing(self, note: str, seed: int) -> IOutputPath:
        return OutputPath(
            TESTS_DIR,
            FUZZING_OUTPUTS_SUBDIR,
            self.replace_suffix(f".{note}.{seed:x}.out").name,
        )


class LogPath(JudgeablePath):
    @staticmethod
    def generator_log(generator: str) -> "LogPath":
        return LogPath(TESTS_DIR, INPUTS_SUBDIR, f"{os.path.basename(generator)}.log")


class RawPath(IRawPath):
    def to_sanitized_input(self) -> IInputPath:
        return InputPath(self.path.removesuffix(".raw"))

    def to_sanitized_output(self) -> IOutputPath:
        return OutputPath(self.path.removesuffix(".raw"))

    def to_sanitization_log(self) -> LogPath:
        return LogPath(self.replace_suffix(".sanitizer.log").path)


# ----- opendata paths = paths outside task -----


class OpendatadPath(TaskPath):
    def __init__(self, tmp_dir: str, *path: str):
        self._tmp_dir = tmp_dir
        super().__init__(*path)


class OpendataJudgeablePath(OpendatadPath, IJudgeablePath):
    def to_checker_log(self, judge: str) -> "LogPath":
        return LogPath(
            self._tmp_dir, self.replace_suffix(f".{os.path.basename(judge)}.log").name
        )


class OpendataSanitizedPath(OpendatadPath, ISanitizedPath):
    def to_raw(self, format: DataFormat) -> IRawPath:
        if format == DataFormat.binary:
            return OpendataRawPath(self._tmp_dir, self.path)
        return RawPath(self._tmp_dir, self.name + ".raw")


class OpendataInputPath(OpendataSanitizedPath, IInputPath):
    def to_second(self) -> IInputPath:
        return InputPath(self._tmp_dir, self.replace_suffix(".in2").name)

    def to_output(self) -> IOutputPath:
        return OutputPath(self._tmp_dir, self.replace_suffix(f".out").name)

    def to_log(self, program: str) -> "LogPath":
        return LogPath(
            self._tmp_dir, self.replace_suffix(f".{os.path.basename(program)}.log").name
        )


class OpendataOutputPath(OpendataSanitizedPath, OpendataJudgeablePath, IOutputPath):
    def to_reference_output(self) -> IOutputPath:
        return OutputPath(self._tmp_dir, self.replace_suffix(f".ok").name)

    def to_fuzzing(self, note: str, seed: int) -> IOutputPath:
        return OutputPath(
            self._tmp_dir,
            self.replace_suffix(f".{note}.{seed:x}.out").name,
        )


class OpendataRawPath(OpendataSanitizedPath, IRawPath):
    def to_sanitized_input(self) -> IInputPath:
        return InputPath(self._tmp_dir, self.name.removesuffix(".raw"))

    def to_sanitized_output(self) -> IOutputPath:
        return OutputPath(self._tmp_dir, self.name.removesuffix(".raw"))

    def to_sanitization_log(self) -> LogPath:
        return LogPath(self._tmp_dir, self.replace_suffix(".sanitizer.log").name)
