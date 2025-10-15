# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2023        Daniel Skýpala <daniel@honza.info>
# Copyright (c)   2024        Benjamin Swart <benjaminswart@email.cz>
# Copyright (c)   2025        Antonín Maloň <git@tonyl.eu>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from abc import ABC, abstractmethod
import logging
import inspect
import subprocess
import os
import json
import shutil
from typing import Any, IO, Optional, Protocol, TYPE_CHECKING

from pisek.utils.text import tab
from pisek.jobs.jobs import PipelineItemFailure
from pisek.config.config_types import BuildStrategyName

if TYPE_CHECKING:
    from pisek.env.env import Env
    from pisek.config.task_config import BuildSection

logger = logging.getLogger(__name__)

ALL_STRATEGIES: dict[BuildStrategyName, type["BuildStrategy"]] = {}


class FakeChangedCWD:
    def __init__(self, strategy: "BuildStrategy", path: str):
        self._strategy = strategy
        self.new = strategy._path(path)

    def __enter__(self):
        self.old = self._strategy.workdir
        self._strategy.workdir = self.new

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self._strategy.workdir = self.old


class RunPopen(Protocol):
    def __call__(
        self, args: list[str], stdout: int, stderr: int, text: bool, cwd: str | None
    ) -> subprocess.Popen: ...


class BuildStrategy(ABC):
    name: BuildStrategyName
    extra_sources: Optional[str] = None
    extra_nonsources: Optional[str] = None

    def __init__(
        self,
        build_section: "BuildSection",
        env: "Env",
        _run_subprocess: RunPopen,
    ) -> None:
        self._build_section = build_section
        self._env = env
        self.stderr_output = ""
        self._run_popen = _run_subprocess

        self.workdir = "."

    def __init_subclass__(cls):
        if not inspect.isabstract(cls):
            ALL_STRATEGIES[cls.name] = cls
        return super().__init_subclass__()

    def _print_stderr(self, msg) -> None:
        self.stderr_output += msg + "\n"

    @classmethod
    @abstractmethod
    def applicable_on_files(cls, build: "BuildSection", sources: list[str]) -> bool:
        pass

    @classmethod
    @abstractmethod
    def applicable_on_directory(cls, build: "BuildSection", directory: str) -> bool:
        pass

    @classmethod
    def applicable(cls, build: "BuildSection", sources: list[str]) -> bool:
        directories = any(os.path.isdir(s) for s in sources)
        if not directories:
            return cls.applicable_on_files(build, sources)
        elif len(sources) == 1:
            return cls.applicable_on_directory(build, sources[0])
        else:
            return False

    def build(self, directory: str, sources: list[str], extras: list[str]) -> str:
        self.inputs = os.listdir(directory)
        self.sources = sources
        self.extras = extras
        self.target = "_" + os.path.basename(self._build_section.program_name)
        with FakeChangedCWD(self, directory):
            return self._build()

    @abstractmethod
    def _build(self) -> str:
        pass

    @classmethod
    def _ends_with(cls, source: str, suffixes: list[str]) -> bool:
        return any(source.endswith(suffix) for suffix in suffixes)

    @classmethod
    def _all_end_with(cls, sources: list[str], suffixes: list[str]) -> bool:
        return all(cls._ends_with(source, suffixes) for source in sources)

    # ---- fake cwd utils ----

    def _path(self, path: str) -> str:
        return os.path.join(self.workdir, path)

    def _exists(self, path: str) -> bool:
        return os.path.exists(self._path(path))

    def _isdir(self, path: str) -> bool:
        return os.path.isdir(self._path(path))

    def _listdir(self, path: str | None = None) -> list[str]:
        return os.listdir(self.workdir if path is None else self._path(path))

    def _stat(self, path: str) -> os.stat_result:
        return os.stat(self._path(path))

    def _open(self, file: str, mode: str = "r", newline: str | None = None) -> IO[Any]:
        return open(self._path(file), mode=mode, newline=newline)

    def _chmod(self, path: str, mode: int) -> None:
        os.chmod(self._path(path), mode)

    def _copy(self, src: str, dst: str, follow_symlinks: bool = True) -> None:
        shutil.copy(self._path(src), self._path(dst), follow_symlinks=follow_symlinks)

    def _symlink(self, src: str, dst: str) -> None:
        os.symlink(src, self._path(dst))

    def _makedirs(self, name: str, exist_ok: bool = False) -> None:
        os.makedirs(self._path(name), exist_ok=exist_ok)

    # ---- build helpers ----

    def _load_shebang(self, program: str) -> str:
        """Load shebang from program."""
        with self._open(program, "r", newline="\n") as f:
            first_line = f.readline()

        if not first_line.startswith("#!"):
            raise PipelineItemFailure(f"Missing shebang in {program}")
        if first_line.endswith("\r\n"):
            raise PipelineItemFailure(f"First line ends with '\\r\\n' in {program}")

        return first_line.strip().lstrip("#!")

    def _check_tool(self, tool: str) -> None:
        """Checks that a tool exists."""
        try:
            # XXX: We should technically use self._run_popen but that doesn't implement timeout properly
            # But as we set it to zero, it doesn't matter
            #
            # Also tool.split() because some tools have more parts (e.g. '/usr/bin/env python3')
            subprocess.run(
                tool.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=0,
                cwd=self.workdir,
            )
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            raise PipelineItemFailure(f"Missing tool: {tool}")

    def _run_subprocess(self, args: list[str], program: str, **kwargs) -> str:
        self._check_tool(args[0])

        logger.debug("Building '" + " ".join(args) + "'")
        comp = self._run_popen(
            args,
            **kwargs,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=self.workdir,
        )

        assert comp.stderr is not None
        assert comp.stdout is not None

        stderr: str = comp.stderr.read()
        if stderr.strip():
            self._print_stderr(stderr)

        if comp.returncode != 0:
            raise PipelineItemFailure(
                f"Build of {program} failed.\n"
                + tab(self._env.colored("> " + " ".join(args), "magenta"))
                + "\n"
                + tab(self._env.colored(stderr, "yellow"))
            )
        return comp.stdout.read()

    def _get_entrypoint(self, file_extension: str) -> str:
        assert file_extension[0] == "."
        if len(self.sources) == 1:
            return self.sources[0]
        else:
            if self._build_section.entrypoint == "":
                raise PipelineItemFailure(
                    f"For multiple {self.name} files 'entrypoint' must be set (in section [{self._build_section.section_name}])."
                )
            if (
                entrypoint := self._build_section.entrypoint + file_extension
            ) in self.sources:
                return entrypoint
            elif (entrypoint := self._build_section.entrypoint) in self.sources:
                return entrypoint
            else:
                raise PipelineItemFailure(
                    f"Entrypoint '{self._build_section.entrypoint}' not in sources."
                )

    def _check_no_run(self):
        if "run" in self.sources:
            raise PipelineItemFailure(
                "Reserved filename 'run' already exists in sources"
            )
        elif "run" in self.extras:
            raise PipelineItemFailure(
                "Reserved filename 'run' already exists in extras"
            )
        elif "run" in self.inputs:
            raise RuntimeError(
                "'run' is contained in inputs, but not sources or extras"
            )


class BuildScript(BuildStrategy):
    @classmethod
    def applicable_on_directory(cls, build: "BuildSection", directory: str) -> bool:
        return False

    def _build(self) -> str:
        assert len(self.sources) == 1
        return self._build_script(self.sources[0])

    def _build_script(self, program: str) -> str:
        interpreter = self._load_shebang(program)
        self._check_tool(interpreter)
        st = self._stat(program)
        self._chmod(program, st.st_mode | 0o111)
        return program


class BuildBinary(BuildStrategy):
    @classmethod
    def applicable_on_directory(cls, build: "BuildSection", directory: str) -> bool:
        return False


class Python(BuildScript):
    name = BuildStrategyName.python
    extra_sources: Optional[str] = "extra_sources_py"

    @classmethod
    def applicable_on_files(cls, build: "BuildSection", sources: list[str]) -> bool:
        if not cls._all_end_with(sources, [".py"]):
            return False
        return True

    def _build(self):
        entrypoint = self._get_entrypoint(".py")
        if len(self.sources) == 1:
            return self._build_script(entrypoint)
        else:
            self._check_no_run()
            self._symlink(self._build_script(entrypoint), "run")
            return "."


class Shell(BuildScript):
    name = BuildStrategyName.shell

    @classmethod
    def applicable_on_files(cls, build: "BuildSection", sources: list[str]) -> bool:
        return len(sources) == 1 and sources[0].endswith(".sh")


class C(BuildBinary):
    name = BuildStrategyName.c
    extra_sources: Optional[str] = "extra_sources_c"
    extra_nonsources: Optional[str] = "headers_c"

    @classmethod
    def applicable_on_files(cls, build: "BuildSection", sources: list[str]) -> bool:
        return cls._all_end_with(sources, [".h", ".c"])

    def _build(self) -> str:
        c_flags = ["-std=c17", "-O2", "-Wall", "-lm", "-Wshadow", "-Wno-sign-compare"]
        c_flags.append(
            "-fdiagnostics-color=" + ("never" if self._env.no_colors else "always")
        )

        self._run_subprocess(
            ["gcc", *self.sources, "-o", self.target, "-I."]
            + c_flags
            + self._build_section.comp_args,
            self._build_section.program_name,
        )
        return self.target


class Cpp(BuildBinary):
    name = BuildStrategyName.cpp
    extra_sources: Optional[str] = "extra_sources_cpp"
    extra_nonsources: Optional[str] = "headers_cpp"

    @classmethod
    def applicable_on_files(cls, build: "BuildSection", sources: list[str]) -> bool:
        return cls._all_end_with(sources, [".h", ".hpp", ".cpp", ".cc"])

    def _build(self) -> str:
        cpp_flags = [
            "-std=c++20",
            "-O2",
            "-Wall",
            "-lm",
            "-Wshadow",
            "-Wno-sign-compare",
        ]
        cpp_flags.append(
            "-fdiagnostics-color=" + ("never" if self._env.no_colors else "always")
        )

        self._run_subprocess(
            ["g++", *self.sources, "-o", self.target, "-I."]
            + cpp_flags
            + self._build_section.comp_args,
            self._build_section.program_name,
        )
        return self.target


class Pascal(BuildBinary):
    name = BuildStrategyName.pascal

    @classmethod
    def applicable_on_files(cls, build: "BuildSection", sources: list[str]) -> bool:
        return cls._all_end_with(sources, [".pas"])

    def _build(self) -> str:
        pas_flags = ["-gl", "-O3", "-Sg", "-o" + self.target, "-FE."]
        self._run_subprocess(
            ["fpc"] + pas_flags + self.sources + self._build_section.comp_args,
            self._build_section.program_name,
        )
        return self.target


class Java(BuildStrategy):
    name = BuildStrategyName.java
    extra_sources: Optional[str] = "extra_sources_java"

    @classmethod
    def applicable_on_files(cls, build: "BuildSection", sources: list[str]) -> bool:
        return cls._all_end_with(sources, [".java"])

    @classmethod
    def applicable_on_directory(cls, build: "BuildSection", directory: str) -> bool:
        return False

    def _build(self):
        self._check_tool("java")
        self._check_tool("javac")
        self._check_tool("/usr/bin/bash")

        entry_class = self._get_entrypoint(".java").rstrip(".java")
        arguments = ["javac", "-d", self.target] + self.sources
        self._run_subprocess(arguments, self._build_section.program_name)
        self._check_no_run()
        run_path = os.path.join(self.target, "run")
        with self._open(run_path, "w") as run_file:
            run_file.write(
                "#!/usr/bin/bash\n"
                + f"exec java --class-path ${{0%/run}} {entry_class} $@\n"
            )
        st = self._stat(run_path)
        self._chmod(run_path, st.st_mode | 0o111)
        return self.target


class Make(BuildStrategy):
    name = BuildStrategyName.make
    _target_subdir: str = "target"

    @classmethod
    def applicable_on_files(cls, build: "BuildSection", sources: list[str]) -> bool:
        return False

    @classmethod
    def applicable_on_directory(cls, build: "BuildSection", directory: str) -> bool:
        return os.path.exists(os.path.join(directory, "Makefile"))

    def _build(self) -> str:
        directory = self._listdir()[0]
        with FakeChangedCWD(self, directory):
            if self._exists(self._target_subdir):
                raise PipelineItemFailure(
                    f"Makefile strategy: '{self._target_subdir}' already exists"
                )
            self._makedirs(self._target_subdir)
            self._run_subprocess(["make"], self._build_section.program_name)
            if not self._isdir(self._target_subdir):
                raise PipelineItemFailure(
                    f"Makefile must create '{self._target_subdir}/' directory"
                )
        return os.path.join(directory, self._target_subdir)


class Cargo(BuildStrategy):
    name = BuildStrategyName.cargo
    _target_subdir: str = "target"
    _artifact_dir: str = ".pisek-executables"

    @classmethod
    def applicable_on_files(cls, build: "BuildSection", sources: list[str]) -> bool:
        return False

    @classmethod
    def applicable_on_directory(cls, build: "BuildSection", directory: str) -> bool:
        return os.path.exists(os.path.join(directory, "Cargo.toml"))

    def _build(self) -> str:
        directory = self._listdir()[0]
        with FakeChangedCWD(self, directory):
            if self._exists(self._target_subdir):
                raise PipelineItemFailure(
                    f"Cargo strategy: '{self._target_subdir}' already exists"
                )

            args = [
                "--release",
                "--workspace",
                "--bins",
                "--quiet",
                "--color",
                ("never" if self._env.no_colors else "always"),
            ]

            self._run_subprocess(
                [
                    "cargo",
                    "check",
                    *args,
                ],
                self._build_section.program_name,
            )

            output = self._run_subprocess(
                [
                    "cargo",
                    "build",
                    *args,
                    "--message-format",
                    "json",
                ],
                self._build_section.program_name,
            )

        self._makedirs(self._artifact_dir)
        exectables = []

        for line in output.splitlines():
            content = json.loads(line)

            if content["reason"] != "compiler-artifact":
                continue
            if "bin" not in content["target"]["kind"]:
                continue
            path = content["executable"]

            name = os.path.basename(path)
            exectables.append(os.path.basename(name))

            self._copy(path, os.path.join(self._artifact_dir, name))

        if len(exectables) == 1 and exectables != ["run"]:
            self._symlink(
                exectables[0],
                os.path.join(self._artifact_dir, "run"),
            )

        return self._artifact_dir


AUTO_STRATEGIES: list[type[BuildStrategy]] = [
    Python,
    Shell,
    C,
    Cpp,
    Pascal,
    Java,
    Make,
    Cargo,
]
