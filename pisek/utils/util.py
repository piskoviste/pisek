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

import glob
import os
import shutil
from typing import Iterable

from pisek.utils.paths import BUILD_DIR, TESTS_DIR, INTERNALS_DIR, TaskPath


class ChangedCWD:
    def __init__(self, path):
        self._path = path

    def __enter__(self):
        self._orig_path = os.getcwd()
        os.chdir(self._path)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        os.chdir(self._orig_path)


def clean_task_dir(task_dir: str) -> None:
    for subdir in [BUILD_DIR, TESTS_DIR, INTERNALS_DIR]:
        full = os.path.join(task_dir, subdir)
        try:
            shutil.rmtree(full)
        except FileNotFoundError:
            pass


def clean_non_relevant_files(accessed_files: set[str]) -> None:
    accessed_dirs = {os.path.dirname(file) for file in accessed_files}
    for root, _, files in os.walk(TESTS_DIR):
        for file in files:
            path = os.path.join(root, file)
            if root in accessed_dirs and path not in accessed_files:
                os.remove(path)


def globs_to_files(
    globs: Iterable[str], directory: TaskPath, exclude: Iterable[str] = ()
) -> list[TaskPath]:
    files_per_glob = [
        glob.glob(g, root_dir=directory.path, recursive=True, include_hidden=True)
        for g in globs
    ]
    files = sorted(set(sum(files_per_glob, start=[])))
    task_paths = [TaskPath.from_abspath(directory.path, file) for file in files]
    exclude_tp = [TaskPath.from_abspath(directory.path, path) for path in exclude]
    return sorted(
        tp for tp in task_paths if all(not exc_p.is_prefix(tp) for exc_p in exclude_tp)
    )
