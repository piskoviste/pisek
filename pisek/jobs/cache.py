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

import hashlib
import time
from typing import Any, Iterable
import os
import pickle

from pisek.version import __version__
from pisek.utils.text import eprint
from pisek.utils.colors import ColorSettings
from pisek.utils.paths import INTERNALS_DIR


CACHE_VERSION_FILE = os.path.join(INTERNALS_DIR, "cache_version")
CACHE_CONTENT_FILE = os.path.join(INTERNALS_DIR, "cache")
HASH_INDEX_FILE = os.path.join(INTERNALS_DIR, "hash_index")
SAVED_LAST_SIGNATURES = 5
CACHE_SAVE_INTERVAL = 1  # seconds


class CacheEntry:
    """Object representing single cached job."""

    def __init__(
        self,
        name: str,
        signature: str,
        result: Any,
        envs: Iterable[tuple[str, ...]],
        files: Iterable[str],
        globs: Iterable[str],
        prerequisites_results: Iterable[str],
        output: list[tuple[str, bool]],
        logs: list[tuple[str, str]],
    ) -> None:
        self.name = name
        self.signature = signature
        self.result = result
        self.prerequisites_results = list(sorted(prerequisites_results))
        self.envs = list(sorted(envs))
        self.files = list(sorted(files))
        self.globs = list(sorted(globs))
        self.output = output
        self.logs = logs

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(name={self.name}, signature={self.signature}, "
            f"result={self.result}, prerequisites_results={self.prerequisites_results}, "
            f"envs={self.envs}, files={self.files}, globs={self.globs}, output={self.output},"
            f"logs={self.logs})"
        )


class Cache:
    """Object for caching jobs and file hashes."""

    def __init__(self) -> None:
        os.makedirs(INTERNALS_DIR, exist_ok=True)
        with open(CACHE_VERSION_FILE, "w") as f:
            f.write(f"{__version__}\n")
        self.cache: dict[str, list[CacheEntry]] = {}
        self.hash_index: dict[str, tuple[float, str]] = {}
        self.last_save = time.time()

    @classmethod
    def load(cls) -> "Cache":
        """Load cache file."""
        CACHE_FILES = [CACHE_VERSION_FILE, CACHE_CONTENT_FILE, HASH_INDEX_FILE]
        cache_existence = list(map(os.path.exists, CACHE_FILES))

        if not all(cache_existence):
            if any(cache_existence):
                eprint(
                    ColorSettings.colored(
                        "Incomplete cache found. Starting from scratch...",
                        "yellow",
                    )
                )
            return Cache()

        with open(CACHE_VERSION_FILE) as f:
            version = f.read().strip()

        if version != __version__:
            eprint(
                ColorSettings.colored(
                    "Different version of cache found. Starting from scratch...",
                    "yellow",
                )
            )
            return Cache()

        cache = Cache()
        cache.cache = cls.pickle_load(CACHE_CONTENT_FILE)
        cache.hash_index = cls.pickle_load(HASH_INDEX_FILE)
        return cache

    def add(self, cache_entry: CacheEntry):
        """Add entry to cache."""
        if cache_entry.name not in self.cache:
            self.cache[cache_entry.name] = []
        self.cache[cache_entry.name].append(cache_entry)

        # trim number of entries per cache name in order to limit cache size
        self.cache[cache_entry.name] = self.cache[cache_entry.name][
            -SAVED_LAST_SIGNATURES:
        ]

        # Throttling saves time massively
        if time.time() - self.last_save > CACHE_SAVE_INTERVAL:
            self.export()

    def __contains__(self, name: str) -> bool:
        return name in self.cache

    def __getitem__(self, name: str) -> list[CacheEntry]:
        return self.cache[name]

    def entry_names(self) -> list[str]:
        return list(self.cache.keys())

    def last_entry(self, name: str) -> CacheEntry:
        return self[name][-1]

    def move_to_top(self, entry: CacheEntry):
        """Move given entry to most recent position."""
        if entry in self.cache[entry.name]:
            self.cache[entry.name].remove(entry)
            self.cache[entry.name].append(entry)
        else:
            raise ValueError(
                f"Cannot move to top entry which is not in Cache:\n{entry}"
            )

    @staticmethod
    def pickle_load(path: str) -> Any:
        with open(path, "rb") as f:
            return pickle.load(f)

    @staticmethod
    def pickle_dump(obj: Any, path: str) -> None:
        """Atomic pickle.dump."""
        tmp_path = path + ".tmp"
        with open(tmp_path, "wb") as f:
            pickle.dump(obj, f)
        os.rename(tmp_path, path)

    def export(self) -> None:
        """Export cache into a file."""
        self.pickle_dump(self.cache, CACHE_CONTENT_FILE)
        self.pickle_dump(self.hash_index, HASH_INDEX_FILE)
        self.last_save = time.time()

    def file_hash(self, path: str):
        mtime = os.path.getmtime(path)
        if path not in self.hash_index or self.hash_index[path][0] != mtime:
            with open(path, "rb") as f:
                file_sign = hashlib.file_digest(f, "sha256")
            self.hash_index[path] = (mtime, file_sign.hexdigest())

        return self.hash_index[path][1]
