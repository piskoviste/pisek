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
from copy import deepcopy
from enum import Enum, auto
import dataclasses
from functools import wraps
import glob
import hashlib
import logging
import os.path
import time
from typing import (
    Optional,
    AbstractSet,
    MutableSet,
    Any,
    Callable,
    NamedTuple,
    TYPE_CHECKING,
)

from pisek.jobs.cache import Cache, CacheEntry
from pisek.utils.paths import TaskPath

if TYPE_CHECKING:
    from pisek.env.env import Env

logger = logging.getLogger(__name__)


class State(Enum):
    in_queue = auto()
    running = auto()
    succeeded = auto()
    failed = auto()
    cancelled = auto()

    def finished(self) -> bool:
        return self in (State.succeeded, State.failed, State.cancelled)


class PipelineItemFailure(Exception):
    pass


class PipelineItemAbort(Exception):
    def __init__(self, item: "PipelineItem"):
        super().__init__(f'"{item.name}" was aborted.')


class CaptureInitParams:
    """
    Class that stores __init__ args and kwargs of its descendants
    and gets accessed Env reads. Only does that to the topmost __init__.
    """

    _initialized = False
    _accessed_envs: MutableSet[tuple[str, ...]]

    def __init_subclass__(cls):
        real_init = cls.__init__

        @wraps(real_init)
        def wrapped_init(self, env: "Env", *args, **kwargs):
            toplevel = not self._initialized
            if toplevel:
                self._args = args
                self._kwargs = kwargs
                self._initialized = True
                self._env = env
                self._env.clear_accesses()

            real_init(self, self._env, *args, **kwargs)

            if toplevel:
                self._accessed_envs |= self._env.get_accessed()
                self._env.clear_accesses()

        cls.__init__ = wrapped_init


class RequiredBy(NamedTuple):
    pipeline_item: "PipelineItem"
    name: Optional[str]
    run_condition: Callable[[Any], bool]


class PipelineItem(ABC):
    """Generic PipelineItem with state and dependencies."""

    _env: "Env"
    run_always: bool = False  # Runs even if prerequisites failed

    def __init__(self, name: str) -> None:
        self.name = name
        self.state = State.in_queue
        self.result: Optional[Any] = None
        self.fail_msg = ""

        self.prerequisites = 0
        self.required_by: list[RequiredBy] = []
        self.prerequisites_results: dict[str, Any] = {}
        # List of prints (string to print, whether to use stderr)
        self.terminal_output: list[tuple[str, bool]] = []

    def _colored(self, msg: str, color: str) -> str:
        return self._env.colored(msg, color)

    def _print(self, msg: str, end: str = "\n", stderr: bool = False) -> None:
        """Adds text for printing to stdout/stderr later."""
        self.terminal_output.append((msg + end, stderr))

    def _warn(self, msg: str) -> None:
        if self._env.strict:
            raise PipelineItemFailure(msg)
        else:
            self._print(self._colored(msg, "yellow"))

    def _fail(self, failure: PipelineItemFailure) -> None:
        """End this job in failure."""
        if self.fail_msg != "":
            raise RuntimeError("PipelineItem cannot fail twice.")
        self.fail_msg = str(failure)
        self.state = State.failed

    def cancel(self) -> None:
        """Cancels job and all that require it."""
        if self.state.finished():
            return  # No need to cancel
        self.state = State.cancelled
        for item, _, _ in self.required_by:
            if not item.run_always:
                item.cancel()

    def _check_prerequisites(self) -> None:
        """Checks if all prerequisites are finished raises error otherwise."""
        if not self.run_always and self.prerequisites > 0:
            raise RuntimeError(
                f"{self.__class__.__name__} {self.name} prerequisites not finished ({self.prerequisites} remaining)."
            )

    def add_prerequisite(
        self,
        item: Optional["PipelineItem"],
        name: Optional[str] = None,
        condition: Callable[[Any], bool] = lambda _: True,
    ) -> None:
        """Adds given PipelineItem as a prerequisite to this job."""
        if item is None:
            return

        self.prerequisites += 1
        item.required_by.append(RequiredBy(self, name, condition))

    def finish(self) -> None:
        """Notifies PipelineItems that depend on this job."""
        for item, name, condition in self.required_by:
            if item.run_always or (
                self.state == State.succeeded and condition(self.result)
            ):
                item.prerequisites -= 1
                if name is not None:
                    item.prerequisites_results[name] = deepcopy(self.result)
            else:
                item.cancel()


class Job(PipelineItem, CaptureInitParams):
    """One simple cacheable task in pipeline."""

    _args: list[Any]
    _kwargs: dict[str, Any]

    def __init__(self, env: "Env", name: str) -> None:
        self._env = env
        self._accessed_envs: MutableSet[tuple[str, ...]] = set()
        self._accessed_globs: MutableSet[str] = set()
        self._accessed_files: MutableSet[str] = set()
        self._logs: list[tuple[str, str]] = []
        self.name = name
        self.started: float | None = None
        super().__init__(name)

    def _log(self, kind: str, message: str) -> None:
        self._logs.append((kind, message))
        getattr(logger, kind)(message)

    def _access_file(self, filename: TaskPath) -> None:
        """Add file this job depends on."""
        self._accessed_files.add(filename.path)

    @property
    def accessed_files(self) -> set[str]:
        return set(self._accessed_files)

    def _signature(
        self,
        envs: AbstractSet[tuple[str, ...]],
        paths: AbstractSet[str],
        globs: AbstractSet[str],
        results: dict[str, Any],
        cache: Cache,
    ) -> tuple[Optional[str], Optional[str]]:
        """Compute a signature (i.e. hash) of given envs, files and prerequisites results."""
        sign = hashlib.sha256()
        sign.update(f"{self.__class__.__name__}\n".encode())
        for i, arg in enumerate(self._args):
            sign.update(f"{i}={arg}\n".encode())
        for key, val in self._kwargs.items():
            sign.update(f"{key}={val}\n".encode())

        for env_key in sorted(envs):
            try:
                value = self._env.get_compound(env_key)
            except (AttributeError, TypeError, ValueError, KeyError):
                return (None, f"Key nonexistent: {env_key}")
            sign.update(f"{env_key}={value}\n".encode())

        for path in sorted(paths):
            while os.path.islink(path):
                path = os.path.normpath(
                    os.path.join(os.path.dirname(path), os.readlink(path))
                )

            if os.path.isfile(path):
                sign.update(f"{path}={cache.file_hash(path)}\n".encode())
            elif os.path.isdir(path):
                sign.update(f"{path} is directory\n".encode())
            else:
                return (None, f"File nonexistent: {path}")

        for g in sorted(globs):
            glob_sign = f"{g} -> " + " ".join(
                glob.glob(g, recursive=True, include_hidden=True)
            )
            sign.update(glob_sign.encode())

        for name, result in sorted(results.items()):
            # Trying to prevent hashing object.__str__ which is non-deterministic
            assert (
                result is None
                or isinstance(result, (str, int, float))
                or dataclasses.is_dataclass(result)
            )
            sign.update(f"{name}={result}\00".encode())

        return (sign.hexdigest(), None)

    def _find_entry(self, cache: Cache) -> Optional[CacheEntry]:
        """Finds a corresponding CacheEntry for this Job."""
        for cache_entry in cache[self.name]:
            sign, err = self._signature(
                set(cache_entry.envs),
                set(cache_entry.files),
                set(cache_entry.globs),
                self.prerequisites_results,
                cache,
            )
            if cache_entry.signature == sign:
                return cache_entry
        return None

    def _export(self, result: Any, cache: Cache) -> CacheEntry:
        """Export this job into CacheEntry."""
        sign, err = self._signature(
            self._accessed_envs,
            self._accessed_files,
            self._accessed_globs,
            self.prerequisites_results,
            cache,
        )
        if sign is None:
            raise RuntimeError(
                f"Computing signature of job {self.name} failed:\n  {err}."
            )
        return CacheEntry(
            self.name,
            sign,
            result,
            self._accessed_envs,
            self._accessed_files,
            self._accessed_globs,
            self.prerequisites_results,
            self.terminal_output,
            self._logs,
        )

    def prepare(self, cache: Cache | None) -> None:
        if self.state == State.cancelled:
            return None
        self._check_prerequisites()

        if (
            cache is not None
            and self.name in cache
            and (entry := self._find_entry(cache))
        ):
            logger.info(f"Loading cached '{self.name}'")
            cache.move_to_top(entry)
            self.terminal_output = entry.output
            for level, message in entry.logs:
                getattr(logger, level)(message)
            self._accessed_files = set(entry.files)
            self.result = entry.result
            self.state = State.succeeded

    def run(self, env: "Env") -> None:
        """Run this job."""
        if self.state == State.cancelled:
            return
        self.state = State.running
        self.started = time.time()
        logger.info(f"Running '{self.name}'")

        try:
            self._env = env
            self._env.clear_accesses()
            self.result = self._run()
            self._accessed_envs |= self._env.get_accessed()
        except PipelineItemFailure as failure:
            self._fail(failure)

    def finalize(self, cache: Cache | None):
        if self.state == State.running:
            if cache is not None:
                cache.add(self._export(self.result, cache))
            self.state = State.succeeded
        return self.finish()

    @abstractmethod
    def _run(self) -> Any:
        """What this job actually does (without all the management)."""
        pass


class JobManager(PipelineItem):
    """Object that can create jobs and compute depending on their results."""

    def set_env(self, env: "Env") -> None:
        self._env = env

    def create_jobs(self) -> list[Job]:
        """Crates this JobManager's jobs."""
        self.result: Optional[dict[str, Any]]
        if self.state == State.cancelled:
            self.jobs = []
        else:
            self.state = State.running
            self._check_prerequisites()
            try:
                self.jobs = self._get_jobs()
            except PipelineItemFailure as failure:
                self._fail(failure)
                self.jobs = []

        return self.jobs

    @abstractmethod
    def _get_jobs(self) -> list[Job]:
        """Actually creates this JobManager's jobs (without management)."""
        pass

    def _job_states(self) -> tuple[State, ...]:
        """States of this manager's jobs."""
        return tuple(map(lambda j: j.state, self.jobs))

    def jobs_with_state(self, state: State) -> list[Job]:
        """Filter this manager's jobs by state."""
        return list(filter(lambda j: j.state == state, self.jobs))

    def update(self) -> None:
        """Update this manager's state according to its jobs."""
        pass

    @abstractmethod
    def get_status(self) -> str:
        """Return status of job manager to be displayed on stdout."""
        return ""

    def ready(self) -> bool:
        """
        Returns whether manager is ready for evaluation.
        (i.e. All of it's jobs have finished)
        """
        return self.state == State.running and len(
            self.jobs_with_state(State.succeeded)
            + self.jobs_with_state(State.cancelled)
        ) == len(self.jobs)

    def any_failed(self) -> bool:
        """Returns whether this manager or its jobs had any failures so far."""
        return self.state == State.failed or len(self.jobs_with_state(State.failed)) > 0

    def finalize(self) -> None:
        """Does final evaluation and computes the result of this job manager."""
        if not self.any_failed():
            try:
                self._evaluate()
            except PipelineItemFailure as failure:
                self._fail(failure)
            else:
                self.state = State.succeeded
        else:
            self.state = State.failed

        self.result = self._compute_result()
        super().finish()

    def _evaluate(self) -> None:
        """Decide whether jobs did run as expected and return result."""
        pass

    def _compute_result(self) -> dict[str, Any]:
        """Creates result to be read by other managers."""
        return {}
