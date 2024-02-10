# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2019 - 2022 Václav Volhejn <vaclav.volhejn@gmail.com>
# Copyright (c)   2019 - 2022 Jiří Beneš <mail@jiribenes.com>
# Copyright (c)   2020 - 2022 Michal Töpfer <michal.topfer@gmail.com>
# Copyright (c)   2022        Jiri Kalvoda <jirikalvoda@kam.mff.cuni.cz>
# Copyright (c)   2023        Daniel Skýpala <daniel@honza.info>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os

from pisek.env import Env

BUILD_DIR = "build/"

GENERATED_SUBDIR = "generated/"
INPUTS_SUBDIR = "inputs/"
INVALID_OUTPUTS_SUBDIR = "invalid/"
OUTPUTS_SUBDIR = "outputs/"
SANITIZED_SUBDIR = "sanitized/"
LOG_SUBDIR = "log/"


class TaskPath:
    """Class representing a path to task file."""

    def __init__(self, task_path, *path: str):
        joined_path = os.path.normpath(os.path.join(*path))
        self.fullpath = os.path.join(task_path, joined_path)
        self.relpath = joined_path
        self.name = os.path.basename(joined_path)

    def __format__(self, __format_spec: str) -> str:
        match __format_spec:
            case "f":
                return self.fullpath
            case "p":
                return self.relpath
            case "n":
                return self.name
            case "":
                return self.relpath
            case _:
                raise ValueError(
                    f"Invalid format specifier '{__format_spec}' for object of type '{self.__class__.__name__}'"
                )

    @staticmethod
    def base_path(env: Env, *path: str) -> "TaskPath":
        return TaskPath(env.task_dir, *path)

    @staticmethod
    def from_abspath(env: Env, path: str) -> "TaskPath":
        return TaskPath.base_path(env, os.path.relpath(path, env.task_dir))

    @staticmethod
    def solution_path(env: Env, *path: str) -> "TaskPath":
        return TaskPath(env.task_dir, env.config.solutions_subdir, *path)

    @staticmethod
    def executable_path(env: Env, *path: str) -> "TaskPath":
        return TaskPath(env.task_dir, BUILD_DIR, *path)

    @staticmethod
    def executable_file(env: Env, program: str) -> "TaskPath":
        program = os.path.splitext(os.path.basename(program))[0]
        return TaskPath.executable_path(env, program)

    @staticmethod
    def data_path(env: Env, *path: str) -> "TaskPath":
        return TaskPath(env.task_dir, env.config.data_subdir, *path)

    @staticmethod
    def generated_path(env: Env, *path: str) -> "TaskPath":
        return TaskPath.data_path(env, GENERATED_SUBDIR, *path)

    @staticmethod
    def generated_input_file(env: Env, subtask: int, seed: str) -> "TaskPath":
        return TaskPath(env, f"{subtask:02}_{seed:x}.in")

    @staticmethod
    def input_path(env: Env, *path: str) -> "TaskPath":
        return TaskPath.data_path(env, INPUTS_SUBDIR, *path)

    @staticmethod
    def invalid_path(env: Env, *path: str) -> "TaskPath":
        return TaskPath.data_path(env, INVALID_OUTPUTS_SUBDIR, *path)

    @staticmethod
    def output_path(env: Env, *path: str) -> "TaskPath":
        return TaskPath.data_path(env, OUTPUTS_SUBDIR, *path)

    @staticmethod
    def output_file(env: Env, input_name: str, solution: str) -> "TaskPath":
        input_name = os.path.splitext(os.path.basename(input_name))[0]
        solution = os.path.basename(solution)
        return TaskPath.output_path(env, f"{input_name}.{solution}.out")

    @staticmethod
    def sanitized_path(env: Env, *path: str) -> "TaskPath":
        return TaskPath.data_path(env, SANITIZED_SUBDIR, *path)

    @staticmethod
    def sanitized_file(env: Env, name: str) -> "TaskPath":
        name = os.path.basename(name)
        return TaskPath.sanitized_path(env, f"{name}.clean")

    @staticmethod
    def log_path(env: Env, *path: str) -> "TaskPath":
        return TaskPath.data_path(env, LOG_SUBDIR, *path)

    @staticmethod
    def points_file(env: Env, name: str) -> "TaskPath":
        name = os.path.splitext(name)[0]
        return TaskPath.log_path(env, f"{name}.points")

    @staticmethod
    def log_file(env: Env, name: str, program: str) -> "TaskPath":
        name = os.path.splitext(os.path.basename(name))[0]
        program = os.path.basename(program)
        return TaskPath.log_path(env, f"{name}.{program}.log")
