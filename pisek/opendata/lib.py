# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2025        Daniel Skýpala <daniel@honza.info>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# !!! BEWARE: This library is backwards incompatible and it's interface can change. !!!

import os
import shutil
import tempfile

from pisek.user_errors import (
    InvalidArgument,
    InvalidOperation,
    TestingFailed,
    NotSupported,
)
from pisek.utils.paths import (
    BUILD_DIR,
    TESTS_DIR,
    INPUTS_LIST,
    INPUTS_SUBDIR,
    OpendataRawPath,
    OpendataInputPath,
    OpendataOutputPath,
)
from pisek.utils.pipeline_tools import run_pipeline
from pisek.config.config_types import GenType
from pisek.config.config_hierarchy import DEFAULT_CONFIG_FILENAME
from pisek.config.task_config import load_config
from pisek.config.config_tools import export_config
from pisek.env.env import TestingTarget
from pisek.jobs.task_pipeline import TaskPipeline
from pisek.task_jobs.data.testcase_info import TestcaseInfo
from pisek.task_jobs.data.data_manager import TEST_SEED

from pisek.opendata.types import OpendataTestcaseInfo, OpendataVerdict
from pisek.opendata.managers import OpendataPipeline


ENV_ARGS = {
    "no_colors": True,
    "no_jumps": True,
}


class Task:
    def __init__(
        self,
        path: str,
        pisek_dir: str | None = None,
        config_filename: str = DEFAULT_CONFIG_FILENAME,
    ) -> None:
        self._path = path
        self._pisek_dir = pisek_dir or os.environ.get("PISEK_DIRECTORY")
        self._config_filename = config_filename

    def test(self, strict: bool = True, disable_cache: bool = False) -> bool:
        try:
            run_pipeline(
                self._path,
                TaskPipeline,
                pisek_dir=self._pisek_dir,
                config_filename=self._config_filename,
                disable_cache=disable_cache,
                strict=strict,
                **ENV_ARGS,
            )
        except TestingFailed:
            return False
        return True

    def build(self, path: str) -> "BuiltTask":
        config = load_config(
            self._path, self._pisek_dir, self._config_filename, False, True
        )
        if config.tests.gen_type == GenType.cms_old:
            raise NotSupported(
                "For opendata tasks, the cms-old generator is not supported."
            )

        if os.path.exists(path):
            if not os.path.isdir(path):
                raise InvalidArgument(f"{path} should be a directory")
            if os.listdir(path):
                raise InvalidOperation(f"{path} should be an empty directory")

        os.makedirs(path, exist_ok=True)
        run_pipeline(
            self._path,
            TaskPipeline,
            pisek_dir=self._pisek_dir,
            config_filename=self._config_filename,
            target=TestingTarget.build,
            disable_cache=True,
            **ENV_ARGS,
        )

        COPIED_PATHS = [
            BUILD_DIR,
            os.path.join(TESTS_DIR, INPUTS_SUBDIR),
            os.path.join(TESTS_DIR, INPUTS_LIST),
        ]

        for task_path in COPIED_PATHS:
            original_path = os.path.join(self._path, task_path)
            full_path = os.path.join(path, task_path)
            if os.path.isdir(original_path):
                shutil.copytree(original_path, full_path)
            elif os.path.isfile(original_path):
                shutil.copy(original_path, full_path)
            else:
                assert False

        export_config(
            self._path,
            self._pisek_dir,
            self._config_filename,
            os.path.join(path, DEFAULT_CONFIG_FILENAME),
        )

        return BuiltTask(path)


class BuiltTask:
    def __init__(self, path: str) -> None:
        self._path = path
        self._config = load_config(path, None, DEFAULT_CONFIG_FILENAME, True, True)

    def _inputs_list(self) -> dict[str, TestcaseInfo]:
        infos = {}
        with open(os.path.join(self._path, TESTS_DIR, INPUTS_LIST)) as f:
            for line in f:
                ti = TestcaseInfo.from_str(line)
                infos[ti.name] = ti
        return infos

    def inputs_list(self) -> dict[int, list[OpendataTestcaseInfo]]:
        result: dict[int, list[OpendataTestcaseInfo]] = {
            test_num: [] for test_num in range(self._config.tests_count)
        }
        for ti in self._inputs_list().values():
            for test_num in result.keys():
                if self._config.test_sections[test_num].in_test(
                    ti.input_path(TEST_SEED).name
                ):
                    result[test_num].append(OpendataTestcaseInfo.from_testcase_info(ti))

        return result

    def get_testcase(
        self,
        name: str,
        test: int,
        seed: int | None,
        input_path: str,
        output_path: str,
    ) -> "Testcase":
        if not 0 <= test <= self._config.tests_count:
            raise InvalidArgument(f"No test with number {test}")

        testcase_infos = self._inputs_list()
        if name not in testcase_infos:
            raise InvalidArgument(f"There is no testcase named '{name}'")
        testcase_info = testcase_infos[name]

        if not self._config.test_sections[test].in_test(
            testcase_info.input_path(TEST_SEED).name
        ):
            raise InvalidArgument(f"Testcase '{name}' is not in test {test}")

        if seed == None and testcase_info.seeded:
            raise InvalidArgument(f"No seed for seeded testcase")
        elif seed is not None and not testcase_info.seeded:
            raise InvalidArgument(f"Seed for unseeded testcase")

        if input_path == output_path:
            raise InvalidArgument("Input and output path must be different")

        return Testcase(self, testcase_info, test, seed, input_path, output_path)


class Testcase:
    def __init__(
        self,
        built_task: BuiltTask,
        info: TestcaseInfo,
        test: int,
        seed: int | None,
        input_path: str,
        output_path: str,
    ) -> None:
        """Use BuiltTask.get_testcase instead."""
        self._built_task = built_task
        self._info = info
        self._test = test
        self._seed = seed
        self._input_dst = input_path
        self._output_dst = output_path

        self.tmp_dir: str | None = None

    @staticmethod
    def _path_present(path: str | None) -> bool:
        return path is not None and os.path.exists(path)

    def _input_path(self) -> OpendataInputPath:
        assert self.tmp_dir is not None
        return OpendataInputPath(self.tmp_dir, self._input_dst)

    def _output_path(self) -> OpendataOutputPath:
        assert self.tmp_dir is not None
        return OpendataOutputPath(self.tmp_dir, self._output_dst)

    def _make_tmp_dir(self) -> None:
        if self.tmp_dir is None:
            self.tmp_dir = tempfile.mkdtemp(prefix="pisek_opendata_")

    def _clear_tmp_dir(self) -> None:
        assert self.tmp_dir is not None
        shutil.rmtree(self.tmp_dir)
        self.tmp_dir = None

    def _run_pipeline(
        self,
        input_needed: bool = False,
        output_needed: bool = False,
        check: bool = False,
        contestant_output: str | None = None,
        clear: bool = False,
    ) -> OpendataVerdict | None:
        output_needed &= not self._path_present(self._output_dst)
        input_needed |= output_needed
        input_needed &= not self._path_present(self._input_dst)

        if input_needed or output_needed or check:
            self._make_tmp_dir()
            assert self.tmp_dir is not None

            contestant_output_path: OpendataRawPath | None = None
            if contestant_output is not None:
                contestant_output_path = OpendataRawPath(
                    self.tmp_dir, contestant_output
                )

            pipeline = OpendataPipeline(
                input_needed,
                output_needed,
                check,
                self._input_path(),
                self._info,
                self._test,
                self._seed,
                self._output_path(),
                contestant_output_path,
            )
            run_pipeline(
                self._built_task._path,
                lambda _: pipeline,
                disable_cache=True,
                **ENV_ARGS,
            )
            if clear:
                self._clear_tmp_dir()

        if check:
            return pipeline.verdict
        return None

    def gen_input(self, clear: bool = True) -> None:
        self._run_pipeline(input_needed=True, clear=clear)

    def gen_output(self, clear: bool = True) -> None:
        self._run_pipeline(output_needed=True, clear=clear)

    def check(self, contestant_output_path: str, clear: bool = True) -> OpendataVerdict:
        assert self._built_task._config.tests.judge_needs_in is not None
        assert self._built_task._config.tests.judge_needs_out is not None

        res = self._run_pipeline(
            input_needed=self._built_task._config.tests.judge_needs_in,
            output_needed=self._built_task._config.tests.judge_needs_out,
            check=True,
            contestant_output=contestant_output_path,
            clear=clear,
        )
        assert res is not None
        return res
