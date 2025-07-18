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

from abc import ABC, abstractmethod
import logging
import inspect
import subprocess
import os
import json
import shutil
from typing import Optional, TYPE_CHECKING

from pisek.utils.util import ChangedCWD
from pisek.utils.text import tab
from pisek.jobs.jobs import PipelineItemFailure
from pisek.config.config_types import BuildStrategyName

if TYPE_CHECKING:
    from pisek.env.env import Env
    from pisek.config.task_config import BuildSection

logger = logging.getLogger(__name__)

ALL_STRATEGIES: dict[BuildStrategyName, type["BuildStrategy"]] = {}


class BuildStrategy(ABC):
    name: BuildStrategyName
    extra_sources: Optional[str] = None
    extra_nonsources: Optional[str] = None

    def __init__(self, build_section: "BuildSection", env: "Env", _print) -> None:
        self._build_section = build_section
        self._env = env
        self._print = _print

    def __init_subclass__(cls):
        if not inspect.isabstract(cls):
            ALL_STRATEGIES[cls.name] = cls
        return super().__init_subclass__()

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
        self.target = os.path.basename(self._build_section.program_name)
        with ChangedCWD(directory):
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

    def _load_shebang(self, program: str) -> str:
        """Load shebang from program."""
        with open(program, "r", newline="\n") as f:
            first_line = f.readline()

        if not first_line.startswith("#!"):
            raise PipelineItemFailure(f"Missing shebang in {program}")
        if first_line.endswith("\r\n"):
            raise PipelineItemFailure(f"First line ends with '\\r\\n' in {program}")

        return first_line.strip().lstrip("#!")

    def _check_tool(self, tool: str) -> None:
        """Checks that a tool exists."""
        try:
            # tool.split() because some tools have more parts (e.g. '/usr/bin/env python3')
            subprocess.run(
                tool.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=0
            )
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            raise PipelineItemFailure(f"Missing tool: {tool}")

    def _run_subprocess(self, args: list[str], program: str, **kwargs) -> str:
        self._check_tool(args[0])

        logger.debug("Building '" + " ".join(args) + "'")
        comp = subprocess.Popen(
            args, **kwargs, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        assert comp.stderr is not None
        assert comp.stdout is not None

        while True:
            line = comp.stderr.readline()
            if not line:
                break
            self._print(line, end="", stderr=True)

        comp.wait()
        if comp.returncode != 0:
            raise PipelineItemFailure(
                f"Build of {program} failed.\n"
                + tab(self._env.colored(" ".join(args), "yellow"))
            )
        return comp.stdout.read()


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
        st = os.stat(program)
        os.chmod(program, st.st_mode | 0o111)
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
        if len(self.sources) == 1:
            return self._build_script(self.sources[0])
        else:
            if self._build_section.entrypoint == "":
                raise PipelineItemFailure(
                    f"For multiple python files 'entrypoint' must be set (in section [{self._build_section.section_name}])."
                )
            assert "run" not in self.sources
            if (entrypoint := self._build_section.entrypoint + ".py") in self.sources:
                pass
            elif (entrypoint := self._build_section.entrypoint) in self.sources:
                pass
            else:
                raise PipelineItemFailure(
                    f"Entrypoint '{self._build_section.entrypoint}' not in sources."
                )

            os.symlink(self._build_script(entrypoint), "run")
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
        c_flags = ["-std=c17", "-O2", "-Wall", "-lm", "-Wshadow"]
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
        cpp_flags = ["-std=c++20", "-O2", "-Wall", "-lm", "-Wshadow"]
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
        directory = os.listdir()[0]
        with ChangedCWD(directory):
            if os.path.exists(self._target_subdir):
                raise PipelineItemFailure(
                    f"Makefile strategy: '{self._target_subdir}' already exists"
                )
            os.makedirs(self._target_subdir)
            self._run_subprocess(["make"], self._build_section.program_name)
            if not os.path.isdir(self._target_subdir):
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
        directory = os.listdir()[0]

        with ChangedCWD(directory):
            if os.path.exists(self._target_subdir):
                raise PipelineItemFailure(
                    f"Cargo strategy: '{self._target_subdir}' already exists"
                )

            output = self._run_subprocess(
                [
                    "cargo",
                    "build",
                    "--release",
                    "--workspace",
                    "--bins",
                    "--message-format",
                    "json",
                    "--quiet",
                    "--color",
                    ("never" if self._env.no_colors else "always"),
                ],
                self._build_section.program_name,
            )

        os.mkdir(self._artifact_dir)
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

            shutil.copy(path, os.path.join(self._artifact_dir, name))

        if len(exectables) == 1 and exectables != ["run"]:
            os.symlink(
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
    Make,
    Cargo,
]
