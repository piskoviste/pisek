# pisek cms - Tool for importing tasks from Pisek into CMS.
#
# Copyright (c)   2024        Benjamin Swart <benjaminswart@email.cz>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from typing import Iterator, Any, Optional
from cms.db.task import Task, Dataset, Manager
from cms.db.filecacher import FileCacher
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound
from os import path, listdir
import re
import datetime
from typing import Callable, TypeVar, assert_never

from pisek.user_errors import NotSupported
from pisek.cms.testcase import create_testcase
from pisek.env.env import Env
from pisek.config.task_config import TaskConfig
from pisek.config.config_types import JudgeType, OutCheck, TaskType, DataFormat
from pisek.utils.paths import TaskPath, InputPath, BUILD_DIR

T = TypeVar("T")


def check_key(name: str, value: T, condition: Callable[[T], bool]):
    if not condition(value):
        raise NotSupported(f"Cannot import task with {name}={value}")


def create_dataset(
    session: Session,
    env: Env,
    task: Task,
    testcases: list[InputPath],
    description: Optional[str],
    time_limit: Optional[float],
    autojudge: bool = True,
) -> Dataset:
    if description is None:
        description = create_description()

    config = env.config

    check_key(
        "out_check",
        config.tests.out_check,
        lambda v: v in (OutCheck.diff, OutCheck.judge, OutCheck.tokens),
    )
    if config.tests.out_check == OutCheck.tokens:
        check_key(
            "tokens_ignore_case", config.tests.tokens_ignore_case, lambda v: not v
        )
        check_key(
            "tokens_ignore_newlines",
            config.tests.tokens_ignore_newlines,
            lambda v: not v,
        )
        check_key(
            "tokens_float_abs_error",
            config.tests.tokens_float_abs_error,
            lambda v: v is None,
        )
        check_key(
            "tokens_float_rel_error",
            config.tests.tokens_float_rel_error,
            lambda v: v is None,
        )
    if (
        config.tests.out_check == OutCheck.judge
        and config.task.task_type == TaskType.batch
    ):
        check_key(
            "judge_type", config.tests.judge_type, lambda t: t == JudgeType.cms_batch
        )
    if (
        config.tests.out_check == OutCheck.judge
        and config.task.task_type == TaskType.interactive
    ):
        check_key(
            "judge_type",
            config.tests.judge_type,
            lambda t: t == JudgeType.cms_communication,
        )

    if config.task.task_type == TaskType.batch:
        check_key(
            "out_format",
            config.tests.out_format,
            lambda t: t in (DataFormat.strict_text, DataFormat.binary),
        )

    score_params = get_group_score_parameters(config)

    task_type: str
    task_params: Any

    if config.task.task_type == TaskType.batch:
        task_type = "Batch"
        task_params = (
            "grader" if config.cms.stubs else "alone",
            ("", ""),
            "comparator" if config.tests.out_check == OutCheck.judge else "diff",
        )
    elif config.task.task_type == TaskType.interactive:
        task_type = "Communication"
        task_params = (1, "stub" if config.cms.stubs else "alone", "std_io")
    else:
        assert_never(config.task.task_type)

    dataset = Dataset(
        description=description,
        autojudge=autojudge,
        task_type=task_type,
        task_type_parameters=task_params,
        score_type="GroupMin",
        score_type_parameters=score_params,
        time_limit=time_limit if time_limit is not None else config.cms.time_limit,
        memory_limit=config.cms.mem_limit * 1024 * 1024,
        task=task,
    )

    session.add(dataset)

    files = FileCacher()

    outputs_needed = (
        config.task.task_type == TaskType.batch and config.tests.judge_needs_out
    )

    for input_ in testcases:
        name = input_.name.removesuffix(".in")
        output: TaskPath | None = None

        if outputs_needed:
            output = input_.to_output()

            if not path.exists(output.path):
                output = TaskPath.data_path(config.primary_solution, output.name)

        create_testcase(session, files, dataset, name, input_, output)

    add_judge(session, files, env, dataset)
    add_stubs(session, files, env, dataset)
    add_headers(session, files, env, dataset)

    return dataset


def get_group_score_parameters(config: TaskConfig) -> list[tuple[int, str]]:
    params = []

    for subtask in config.test_sections.values():
        globs = map(strip_input_extention, subtask.all_globs)
        # CMS supports only relative points therefore we convert 'unscored' to 0
        params.append((subtask.max_points, globs_to_regex(globs)))

    return params


def strip_input_extention(file: str) -> str:
    if not file.endswith(".in"):
        raise RuntimeError(f"Input file {file} does not have a .in extention")

    return file[:-3]


def glob_char_to_regex(c: str) -> str:
    if c == "?":
        return "."
    elif c == "*":
        return ".*"
    else:
        return re.escape(c)


def globs_to_regex(globs: Iterator[str]) -> str:
    patterns = []

    for glob in globs:
        pattern = "".join(map(glob_char_to_regex, glob))
        patterns.append(f"({pattern})")

    return f"^{'|'.join(patterns)}$"


def add_judge(session: Session, files: FileCacher, env: Env, dataset: Dataset):
    config: TaskConfig = env.config

    if config.tests.out_check != OutCheck.judge:
        return

    assert config.tests.out_judge is not None

    run_section = config.tests.out_judge
    judge_path = TaskPath(BUILD_DIR, run_section.exec.path).path

    if path.isdir(judge_path):
        run_path = path.join(judge_path, "run")

        for file in listdir(judge_path):
            file = path.join(judge_path, file)
            assert path.realpath(file) == path.realpath(
                run_path
            ), f"{judge_path} contains {file}, which is not run. Multi-file judges are not supported."

        judge_path = run_path

    if config.task.task_type == TaskType.batch:
        judge_name = "checker"
    elif config.task.task_type == TaskType.interactive:
        judge_name = "manager"
    else:
        assert_never(config.task.task_type)

    judge = files.put_file_from_path(judge_path, f"{judge_name} for {config.cms.name}")
    session.add(Manager(dataset=dataset, filename=judge_name, digest=judge))


MISSING_STUB_ERROR = "Language not supported"
ERROR_STUBS = {
    ".c": f"#error {MISSING_STUB_ERROR}",
    ".cpp": f"#error {MISSING_STUB_ERROR}",
    ".cs": f"#error {MISSING_STUB_ERROR}",
    ".hs": f'{{-# LANGUAGE DataKinds #-}} import GHC.TypeLits; type Error = TypeError (Text "{MISSING_STUB_ERROR}")',
    ".java": MISSING_STUB_ERROR,
    ".pas": f"{{$Message Fatal '{MISSING_STUB_ERROR}'}}",
    ".php": f"<?php throw new Exception('{MISSING_STUB_ERROR}'); ?>",
    ".py": MISSING_STUB_ERROR,
    ".rs": f'compile_error!("{MISSING_STUB_ERROR}");',
}


def add_stubs(session: Session, files: FileCacher, env: Env, dataset: Dataset):
    config = env.config

    if not config.cms.stubs:
        return

    if config.task.task_type == TaskType.batch:
        stub_basename = "grader"
    elif config.task.task_type == TaskType.interactive:
        stub_basename = "stub"
    else:
        assert_never(config.task.task_type)

    exts = set()
    for stub in config.cms.stubs:
        directory, target_name = path.split(stub.path)
        directory = path.normpath(directory)

        for filename in listdir(directory):
            basename, ext = path.splitext(filename)

            if basename != target_name and filename != target_name:
                continue

            stub = files.put_file_from_path(
                path.join(directory, filename),
                f"{stub_basename}{ext} for {config.cms.name}",
            )
            session.add(
                Manager(dataset=dataset, filename=f"{stub_basename}{ext}", digest=stub)
            )

            if ext in exts:
                raise RuntimeError(f"Multiple stubs with extension '{ext}'")
            exts.add(ext)

    for ext, content in ERROR_STUBS.items():
        if ext in exts:
            continue

        stub = files.put_file_content(
            content.encode(), f"{stub_basename}{ext} for {config.cms.name}"
        )
        session.add(
            Manager(dataset=dataset, filename=f"{stub_basename}{ext}", digest=stub)
        )


def add_headers(session: Session, files: FileCacher, env: Env, dataset: Dataset):
    config = env.config

    for header in config.cms.headers:
        name = header.name
        header = files.put_file_from_path(
            header.path, f"Header {name} for {config.cms.name}"
        )
        session.add(Manager(dataset=dataset, filename=name, digest=header))


def get_only_dataset(session: Session, task: Task) -> Dataset:
    datasets = session.query(Dataset).filter(Dataset.task == task).all()

    if len(datasets) >= 2:
        raise RuntimeError(
            f"The task has multiple datasets: {', '.join(sorted(d.description for d in datasets))}"
        )
    else:
        return datasets[0]


def get_dataset_by_description(
    session: Session, task: Task, description: str
) -> Dataset:
    try:
        return (
            session.query(Dataset)
            .filter(Dataset.task == task)
            .filter(Dataset.description == description)
            .one()
        )
    except NoResultFound as e:
        raise RuntimeError(
            f'The task has no dataset with the description "{description}"'
        ) from e


def create_description() -> str:
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return date
