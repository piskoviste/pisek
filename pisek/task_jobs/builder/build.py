# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2023        Daniel Skýpala <daniel@honza.info>
# Copyright (c)   2024        Benjamin Swart <benjaminswart@email.cz>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import shutil
from typing import Optional
import uuid

from pisek.utils.text import tab
from pisek.utils.paths import TaskPath, BUILD_DIR

from pisek.env.env import Env, TestingTarget
from pisek.config.task_config import BuildSection, RunSection
from pisek.config.config_types import BuildStrategyName, OutCheck

from pisek.task_jobs.tools import PrepareTokenJudge, PrepareShuffleJudge
from pisek.jobs.jobs import Job, PipelineItemFailure
from pisek.task_jobs.task_job import TaskJob
from pisek.task_jobs.task_manager import TaskJobManager

from pisek.task_jobs.builder.strategies import (
    BuildStrategy,
    AUTO_STRATEGIES,
    ALL_STRATEGIES,
)

WORKING_DIR_BASE = "_workspace"


class BuildManager(TaskJobManager):
    """Builds task programs."""

    def __init__(self):
        super().__init__("Build programs")

    def _build_program_job(self, run: Optional[RunSection]) -> Optional["Build"]:
        if run is None or run.build.section_name in self._built_sections:
            return None
        self._built_sections.add(run.build.section_name)
        return Build(self._env, run.build)

    def _get_jobs(self) -> list[Job]:
        self._built_sections: set[str] = set()
        jobs: list[Job | None] = []

        jobs.append(self._build_program_job(self._env.config.tests.in_gen))
        jobs.append(self._build_program_job(self._env.config.tests.validator))

        # If builds from previous run ended unsuccessfully, clean up
        for path in os.listdir(BUILD_DIR):
            if path.startswith(WORKING_DIR_BASE):
                shutil.rmtree(os.path.join(BUILD_DIR, path))

        if self._env.target in (
            TestingTarget.build,
            TestingTarget.solutions,
            TestingTarget.all,
        ):
            if self._env.config.tests.out_check == OutCheck.judge:
                jobs.append(self._build_program_job(self._env.config.tests.out_judge))
            elif self._env.config.tests.out_check == OutCheck.tokens:
                jobs.append(PrepareTokenJudge(self._env))
            elif self._env.config.tests.out_check == OutCheck.shuffle:
                jobs.append(PrepareShuffleJudge(self._env))

            for solution in self._env.solutions:
                jobs.append(
                    self._build_program_job(self._env.config.solutions[solution].run)
                )

        filtered_jobs: list[Job] = []
        for j in jobs:
            if j is not None:
                filtered_jobs.append(j)

        return filtered_jobs


class Build(TaskJob):
    """Job that compiles a program."""

    def __init__(
        self,
        env: Env,
        build_section: BuildSection,
        **kwargs,
    ) -> None:
        super().__init__(env=env, name=f"Build {build_section.program_name}", **kwargs)
        self.build_section = build_section

    def _resolve_program(self, glob: TaskPath) -> set[TaskPath]:
        result = self._globs_to_files([f"{glob.path}.*", glob.path], TaskPath("."))
        if len(result) == 0:
            raise PipelineItemFailure(f"No paths found for {glob.col(self._env)}.")
        return set(result)

    def _check_valid_sources(self, sources: set[TaskPath]) -> None:
        """Checks that sources are one directory or multiple files."""
        source_dir = any(map(self._is_dir, sources))
        source_file = any(map(self._is_file, sources))
        if source_dir and source_file:
            raise PipelineItemFailure(
                f"Mixed files and directories for sources:\n"
                + tab(self._path_list(list(sorted(sources))))
            )
        elif source_dir and len(sources) > 1:
            raise PipelineItemFailure(
                f"Only one directory allowed in sources:\n"
                + tab(self._path_list(list(sorted(sources))))
            )

    def _strategy_sources(
        self, strategy: type[BuildStrategy], sources: set[TaskPath]
    ) -> set[TaskPath]:
        new_sources = set()
        if strategy.extra_sources is not None:
            for part in getattr(self.build_section, strategy.extra_sources):
                new_sources |= self._resolve_program(part)
        return sources | new_sources

    def _strategy_extras(
        self, strategy: type[BuildStrategy], extras: set[TaskPath]
    ) -> set[TaskPath]:
        new_extras = set()
        if strategy.extra_nonsources is not None:
            new_extras = set(getattr(self.build_section, strategy.extra_nonsources))
        return extras | new_extras

    def _run(self) -> None:
        sources: set[TaskPath] = set()
        extras: set[TaskPath] = set(self.build_section.extras)
        for part in self.build_section.sources:
            sources |= self._resolve_program(part)

        # We need to check valid sources twice:
        # - First in order to report correct error
        # - Second time because we added extra sources
        self._check_valid_sources(sources)

        if self.build_section.strategy == BuildStrategyName.auto:
            strategy_cls = self._resolve_strategy(sources)
        else:
            strategy_cls = ALL_STRATEGIES[self.build_section.strategy]

        sources = self._strategy_sources(strategy_cls, sources)
        extras = self._strategy_extras(strategy_cls, extras)
        self._check_valid_sources(sources)

        workdir = os.path.join(BUILD_DIR, f"{WORKING_DIR_BASE}_{uuid.uuid4()}")
        os.makedirs(workdir)

        for path in sources | extras:
            # Intentionally avoiding caching results
            dst = os.path.join(workdir, path.name)
            if os.path.exists(dst):
                raise PipelineItemFailure(
                    f"Duplicate filename / dirname: '{path.name}'"
                )
            if self._is_dir(path):
                shutil.copytree(path.path, dst)
                self._access_dir(path)
            elif self._is_file(path):
                shutil.copy(path.path, dst)
                self._access_file(path)
            else:
                raise PipelineItemFailure(f"No path {path.col(self._env)} exists.")

        target = TaskPath(BUILD_DIR, self.build_section.program_name)
        self.make_filedirs(target)
        if os.path.isdir(target.path):
            shutil.rmtree(target.path)
        elif os.path.isfile(target.path):
            os.remove(target.path)

        strategy = strategy_cls(self.build_section, self._env, self._run_subprocess)
        executable_name = strategy.build(
            workdir,
            list(map(lambda p: p.name, sources)),
            list(map(lambda p: p.name, extras)),
        )

        if self._env.verbosity >= 1 or strategy.stderr_output:
            msg = f"Built '{self.build_section.program_name}' using build strategy '{strategy_cls.name}'."
            self._print(self._colored(msg, "magenta"))
            self._print(strategy.stderr_output, end="", stderr=True)

        executable = os.path.join(workdir, executable_name)
        # Intentionally avoiding caching sources
        if os.path.isdir(executable):
            shutil.copytree(executable, target.path, symlinks=True)
            self._access_dir(target)
        else:
            shutil.copy(executable, target.path)
            self._access_file(target)

        shutil.rmtree(workdir)

    def _resolve_strategy(self, sources: set[TaskPath]) -> type[BuildStrategy]:
        applicable = []
        for strategy in AUTO_STRATEGIES:
            strat_sources = self._strategy_sources(strategy, sources)
            if strategy.applicable(
                self.build_section, list(map(lambda p: p.path, strat_sources))
            ):
                applicable.append(strategy)
        if len(applicable) == 0:
            raise PipelineItemFailure(
                f"No applicable build strategy for [{self.build_section.section_name}] with sources:\n"
                + tab(self._path_list(list(sorted(sources))))
            )
        elif len(applicable) >= 2:
            names = " ".join(s.name for s in applicable)
            raise RuntimeError(f"Multiple strategies applicable: {names}")

        return applicable[0]
