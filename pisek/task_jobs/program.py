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

from dataclasses import dataclass, field
import logging
import os
import tempfile
from typing import Optional, Any, Union, Callable
import signal
import subprocess

from pisek.config.task_config import ProgramRole, RunSection
from pisek.env.env import Env
from pisek.utils.paths import TaskPath, LogPath
from pisek.jobs.jobs import PipelineItemFailure
from pisek.utils.text import tab
from pisek.task_jobs.run_result import RunResultKind, RunResult
from pisek.task_jobs.task_job import TaskJob

logger = logging.getLogger(__name__)


@dataclass
class ProgramPoolItem:
    executable: TaskPath
    args: list[str]
    time_limit: float
    clock_limit: float
    mem_limit: int
    process_limit: int
    stdin: Optional[Union[TaskPath, int]]
    stdout: Optional[Union[TaskPath, int]]
    stderr: Optional[TaskPath]
    env: dict[str, str] = field(default_factory=lambda: {})

    def to_popen(self, minibox: str, meta_file: str) -> dict[str, Any]:
        """Returns subprocess.Popen args for executing this PoolItem."""
        result: dict[str, Any] = {}

        minibox_args = []
        minibox_args.append(f"--time={self.time_limit}")
        minibox_args.append(f"--wall-time={self.clock_limit}")
        minibox_args.append(f"--mem={self.mem_limit*1024}")
        minibox_args.append(f"--processes={self.process_limit}")

        for std in ("stdin", "stdout", "stderr"):
            attr = getattr(self, std)
            if isinstance(attr, TaskPath):
                minibox_args.append(f"--{std}={attr.abspath}")
            elif getattr(self, std) is None:
                minibox_args.append(f"--{std}=/dev/null")

            if isinstance(attr, int):
                result[std] = attr
            else:
                result[std] = subprocess.PIPE

        for key, val in self.env.items():
            minibox_args.append(f"--env={key}={val}")

        minibox_args.append("--silent")
        minibox_args.append(f"--meta={meta_file}")

        result["args"] = (
            [minibox]
            + minibox_args
            + ["--run", "--", self.executable.abspath]
            + self.args
        )
        return result


class ProgramsJob(TaskJob):
    """Job that deals with a program."""

    def __init__(self, env: Env, name: str, **kwargs) -> None:
        super().__init__(env=env, name=name, **kwargs)
        self._program_pool: list[ProgramPoolItem] = []
        self._callback: Optional[Callable[[subprocess.Popen], None]] = None

    @staticmethod
    def _env_disjoint_union(
        env1: dict[str, str], env2: dict[str, str]
    ) -> dict[str, str]:
        union = env1 | env2
        if len(union) != len(env1) + len(env2):
            duplicates = list(set(env1.keys()) & set(env2.keys()))
            raise PipelineItemFailure(
                f"Environment variable '{duplicates[0]}' is used by the protocol and cannot be overwritten."
            )
        return union

    def _load_executable(
        self,
        executable: TaskPath,
        args: list[str],
        time_limit: float,
        clock_limit: float,
        mem_limit: int,
        process_limit: int,
        stdin: Optional[Union[TaskPath, int]] = None,
        stdout: Optional[Union[TaskPath, int]] = None,
        stderr: Optional[LogPath] = None,
        env: dict[str, str] = {},
    ):
        if self._is_file(executable):
            self._access_file(executable)
        elif self._is_dir(executable):
            self._access_dir(executable)
            executable = executable.join("run")

        if self._is_dir(executable):
            raise PipelineItemFailure(
                f"Cannot execute '{executable:p}': Is a directory.."
            )
        elif not self._exists(executable):
            raise PipelineItemFailure(f"Cannot execute '{executable:p}': File missing.")

        if isinstance(stdin, TaskPath):
            self._access_file(stdin)
        if isinstance(stdout, TaskPath):
            self.make_filedirs(stdout)
            self._access_file(stdout)
        if isinstance(stderr, TaskPath):
            self.make_filedirs(stderr)
            self._access_file(stderr)

        self._program_pool.append(
            ProgramPoolItem(
                executable=executable,
                args=args,
                time_limit=time_limit,
                clock_limit=clock_limit,
                mem_limit=mem_limit,
                process_limit=process_limit,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                env=env,
            )
        )

    def _load_program(
        self,
        program_role: ProgramRole,
        program: RunSection,
        args: list[str] = [],
        stdin: Optional[Union[TaskPath, int]] = None,
        stdout: Optional[Union[TaskPath, int]] = None,
        stderr: Optional[LogPath] = None,
        env={},
    ) -> None:
        """Adds program to execution pool."""
        time_limit: Optional[float] = None
        if program_role.is_solution():
            time_limit = self._env.time_limit

        self._load_executable(
            executable=program.executable,
            args=program.args + args,
            time_limit=program.time_limit if time_limit is None else time_limit,
            clock_limit=program.clock_limit(time_limit),
            mem_limit=program.mem_limit,
            process_limit=program.process_limit,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            env=self._env_disjoint_union(env, program.env),
        )

    def _load_callback(self, callback: Callable[[subprocess.Popen], None]) -> None:
        if self._callback is not None:
            raise RuntimeError("Callback already loaded.")
        self._callback = callback

    def _run_programs(self) -> list[RunResult]:
        """Runs all programs in execution pool."""
        running_pool: list[subprocess.Popen] = []
        meta_files: list[str] = []
        tmp_dirs: list[str] = []
        minibox = TaskPath.executable_path("_minibox").abspath
        for pool_item in self._program_pool:
            fd, meta_file = tempfile.mkstemp()
            os.close(fd)
            meta_files.append(meta_file)

            popen = pool_item.to_popen(minibox, meta_file)
            logger.debug("Executing '" + " ".join(popen["args"]) + "'")

            tmp_dir = tempfile.mkdtemp(prefix="pisek_")
            tmp_dirs.append(tmp_dir)
            running_pool.append(subprocess.Popen(**popen, cwd=tmp_dir))

        if self._callback is not None:
            callback_exec = False
            while True:
                states = [process.poll() is not None for process in running_pool]
                if not callback_exec and any(states):
                    callback_exec = True
                    self._callback(running_pool[states.index(True)])

                if all(states):
                    break

        run_results = []
        for pool_item, process, tmp_dir, meta_file in zip(
            self._program_pool, running_pool, tmp_dirs, meta_files
        ):
            self._wait_for_subprocess(process)
            assert process.stderr is not None  # To make mypy happy

            with open(meta_file) as f:
                meta_raw = f.read().strip().split("\n")

            assert meta_file.startswith("/tmp")  # Better safe then sorry
            assert tmp_dir.startswith("/tmp")
            os.remove(meta_file)
            os.removedirs(tmp_dir)

            meta = {key: val for key, val in map(lambda x: x.split(":", 1), meta_raw)}
            if process.returncode == 0:
                t, wt = float(meta["time"]), float(meta["time-wall"])
                run_results.append(
                    RunResult(
                        RunResultKind.OK,
                        0,
                        t,
                        wt,
                        pool_item.stdin,
                        pool_item.stdout,
                        pool_item.stderr,
                        "Exited with return code 0",
                    )
                )
            elif process.returncode == 1:
                t, wt = float(meta["time"]), float(meta["time-wall"])
                if meta["status"] in ("RE", "SG"):
                    if meta["status"] == "RE":
                        return_code = int(meta["exitcode"])
                    elif meta["status"] == "SG":
                        return_code = int(meta["exitsig"])
                        meta["message"] += f" ({signal.Signals(return_code).name})"

                    run_results.append(
                        RunResult(
                            RunResultKind.RUNTIME_ERROR,
                            return_code,
                            t,
                            wt,
                            pool_item.stdin,
                            pool_item.stdout,
                            pool_item.stderr,
                            meta["message"],
                        )
                    )
                elif meta["status"] == "TO":
                    time_limit = (
                        f"{pool_item.time_limit}s"
                        if t > pool_item.time_limit
                        else f"{pool_item.clock_limit}ws"
                    )
                    run_results.append(
                        RunResult(
                            RunResultKind.TIMEOUT,
                            -1,
                            t,
                            wt,
                            pool_item.stdin,
                            pool_item.stdout,
                            pool_item.stderr,
                            f"Timeout after {time_limit}",
                        )
                    )
                else:
                    raise RuntimeError(f"Unknown minibox status {meta['message']}.")
            else:
                raise PipelineItemFailure(
                    f"Minibox error:\n{tab(process.stderr.read().decode())}"
                )

        return run_results

    def _run_program(
        self,
        program_role: ProgramRole,
        program: RunSection,
        **kwargs,
    ) -> RunResult:
        """Loads one program and runs it."""
        self._load_program(program_role, program, **kwargs)
        return self._run_programs()[0]

    def _run_tool(
        self,
        program: str,
        args: list[str] = [],
        stdin: Optional[Union[TaskPath, int]] = None,
        stdout: Optional[Union[TaskPath, int]] = None,
        stderr: Optional[LogPath] = None,
        env={},
    ) -> RunResult:
        """Loads one program and runs it."""
        self._load_executable(
            TaskPath.executable_path(program),
            args=args,
            time_limit=300,
            clock_limit=300,
            mem_limit=0,
            process_limit=1,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            env=env,
        )
        return self._run_programs()[0]

    def _create_program_failure(self, msg: str, res: RunResult, **kwargs):
        """Create PipelineItemFailure that nicely formats RunResult"""
        return PipelineItemFailure(
            f"{msg}\n{tab(self._format_run_result(res, **kwargs))}"
        )

    def _format_run_result(
        self,
        res: RunResult,
        status: bool = True,
        stdin: bool = True,
        stdin_force_content: bool = False,
        stdout: bool = True,
        stdout_force_content: bool = False,
        stderr: bool = True,
        stderr_force_content: bool = False,
        time: bool = False,
    ):
        """Formats RunResult."""
        program_msg = ""
        if status:
            program_msg += f"status: {res.status}\n"

        if stdin and isinstance(res.stdin_file, TaskPath):
            program_msg += f"stdin: {self._quote_file_with_name(res.stdin_file, force_content=stdin_force_content)}"
        if stdout and isinstance(res.stdout_file, TaskPath):
            program_msg += f"stdout: {self._quote_file_with_name(res.stdout_file, force_content=stdout_force_content)}"
        if stderr and isinstance(res.stderr_file, TaskPath):
            program_msg += f"stderr: {self._quote_file_with_name(res.stderr_file, force_content=stderr_force_content, style='ht')}"
        if time:
            program_msg += f"time: {res.time}\n"

        return program_msg.removesuffix("\n")
