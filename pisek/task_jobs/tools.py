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

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from importlib.resources import files
import os

from pisek.jobs.jobs import Job, PipelineItemFailure
from pisek.config.config_types import DataFormat
from pisek.env.env import Env
from pisek.utils.paths import TaskPath, IRawPath, ISanitizedPath
from pisek.task_jobs.task_job import TaskJob
from pisek.task_jobs.task_manager import TaskJobManager
from pisek.task_jobs.program import ProgramsJob
from pisek.task_jobs.run_result import RunResult, RunResultKind


class ToolsManager(TaskJobManager):
    """Manager that prepares all tools necessary for task testing."""

    def __init__(self):
        super().__init__("Preparing tools")

    def _get_jobs(self) -> list[Job]:
        self.makedirs(TaskPath.executable_path("."))
        jobs: list[Job] = [
            PrepareMinibox(self._env),
            PrepareTextPreprocessor(self._env),
        ]
        return jobs


class PrepareMinibox(TaskJob):
    """Compiles minibox."""

    def __init__(self, env: Env, **kwargs) -> None:
        super().__init__(env=env, name="Prepare Minibox", **kwargs)

    def _run(self):
        source = files("pisek").joinpath("tools/minibox.c")
        executable = TaskPath.executable_path("_minibox")
        self._access_file(executable)
        gcc = self._run_subprocess(
            [
                "gcc",
                source,
                "-o",
                executable.path,
                "-std=gnu11",
                "-D_GNU_SOURCE",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Wno-parentheses",
                "-Wno-sign-compare",
                "-Wno-unused-result",
            ]
        )
        if gcc.returncode != 0:
            raise PipelineItemFailure("Minibox compilation failed.")


class PrepareTextPreprocessor(TaskJob):
    """Compiles Text Preprocessor."""

    def __init__(self, env: Env, **kwargs) -> None:
        super().__init__(env=env, name="Prepare text preprocessor", **kwargs)

    def _run(self):
        source = files("pisek").joinpath("tools/text-preproc.c")
        executable = TaskPath.executable_path("_text-preproc")
        self._access_file(executable)
        gcc = self._run_subprocess(
            [
                "gcc",
                source,
                "-o",
                executable.path,
                "-std=gnu11",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Wno-parentheses",
                "-Wno-sign-compare",
            ]
        )
        if gcc.returncode != 0:
            raise PipelineItemFailure("Text preprocessor compilation failed.")


class PrepareJudgeLibChecker(TaskJob):
    """Compiles judge from judgelib."""

    def __init__(self, env: Env, checker_name: str, judge: str, **kwargs) -> None:
        self.judge = judge
        super().__init__(env=env, name=f"Prepare {checker_name}", **kwargs)

    def _run(self):
        source_files = ["util.cc", "io.cc", "token.cc", "random.cc", f"{self.judge}.cc"]
        source_dir = files("pisek").joinpath("tools/judgelib")
        sources = [source_dir.joinpath(file) for file in source_files]

        executable = TaskPath.executable_path("_" + self.judge)
        self._access_file(executable)

        gpp = self._run_subprocess(
            [
                "g++",
                *sources,
                "-I",
                source_dir,
                "-o",
                executable.path,
                "-std=gnu++17",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Wno-parentheses",
                "-Wno-sign-compare",
            ]
        )

        if gpp.returncode != 0:
            raise PipelineItemFailure(f"{self.checker_name} compilation failed.")


class PrepareTokenJudge(PrepareJudgeLibChecker):
    """Compiles judge-token from judgelib."""

    def __init__(self, env: Env, **kwargs) -> None:
        super().__init__(
            env=env, checker_name="token judge", judge="judge-token", **kwargs
        )


class PrepareShuffleJudge(PrepareJudgeLibChecker):
    """Compiles judge-shuffle from judgelib."""

    def __init__(self, env: Env, **kwargs) -> None:
        super().__init__(
            env=env, checker_name="shuffle judge", judge="judge-shuffle", **kwargs
        )


class SanitizationResultKind(Enum):
    ok = auto()
    changed = auto()
    invalid = auto()
    skipped = auto()


@dataclass(frozen=True)
class SanitizationResult:
    kind: SanitizationResultKind
    msg: str | None = None


class TextPreprocAbstract(ProgramsJob):
    """Abstract job that has method for file sanitization."""

    def _run_text_preproc(
        self, input_: IRawPath, output: ISanitizedPath
    ) -> SanitizationResult:
        try:
            os.remove(output.path)
        except FileNotFoundError:
            pass

        result = self._run_tool(
            "_text-preproc",
            stdin=input_,
            stdout=output,
            stderr=input_.to_sanitization_log(),
        )
        msg = self._read_file(result.stderr_file).strip()
        if result.returncode == 42:
            if self._files_equal(input_, output):
                return SanitizationResult(SanitizationResultKind.ok, msg)
            else:
                return SanitizationResult(SanitizationResultKind.changed, msg)
        elif result.returncode == 43:
            return SanitizationResult(SanitizationResultKind.invalid, msg)
        else:
            raise RuntimeError(f"Text preprocessor failed on file {input_:p}.")


class SanitizeAbstract(TaskJob):
    def __init__(self, env: Env, input_: TaskPath, output: TaskPath, **kwargs) -> None:
        self.input = input_
        self.output = output
        super().__init__(env=env, **kwargs)

    def _run(self) -> SanitizationResult:
        result = self.prerequisites_results.get("create_source", None)
        if isinstance(result, RunResult) and result.kind != RunResultKind.OK:
            self._copy_file(self.input, self.output)
            return SanitizationResult(SanitizationResultKind.skipped)

        return self._sanitize()

    @abstractmethod
    def _sanitize(self) -> SanitizationResult:
        pass


class Sanitize(SanitizeAbstract, TextPreprocAbstract):
    """Sanitize text file using Text Preprocessor."""

    def __init__(
        self, env: Env, input_: IRawPath, output: ISanitizedPath, **kwargs
    ) -> None:
        super().__init__(
            env, input_, output, name=f"Sanitize {input_:p} -> {output:p}", **kwargs
        )

    def _sanitize(self):
        return self._run_text_preproc(self.input, self.output)


class IsClean(SanitizeAbstract, TextPreprocAbstract):
    """Check that file is same after sanitizing with Text Preprocessor."""

    def __init__(
        self, env: Env, input_: IRawPath, output: ISanitizedPath, **kwargs
    ) -> None:
        super().__init__(
            env, input_, output, name=f"Check {input_:p} is clean", **kwargs
        )

    def _sanitize(self):
        result = self._run_text_preproc(self.input, self.output)
        if result.kind != SanitizationResultKind.ok:
            raise PipelineItemFailure(
                f"File {self.input:p} not normalized. (Check encoding, missing newline at the end or '\\r'.)"
            )


def _sanitize_get_format(env: Env, is_input: bool) -> DataFormat:
    if is_input:
        return env.config.tests.in_format
    else:
        return env.config.tests.out_format


def sanitize_job(env: Env, path: ISanitizedPath, is_input: bool) -> Job | None:
    return sanitize_job_direct(
        env, path.to_raw(_sanitize_get_format(env, is_input)), path, is_input
    )


def sanitize_job_direct(
    env: Env, path_from: IRawPath, path_to: ISanitizedPath, is_input: bool
) -> Job | None:
    format_ = _sanitize_get_format(env, is_input)

    if format_ == DataFormat.binary:
        return None
    elif format_ == DataFormat.strict_text and is_input:
        return IsClean(env, path_from, path_to)
    else:
        return Sanitize(env, path_from, path_to)
