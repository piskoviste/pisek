from configparser import ConfigParser
from functools import partial
from importlib.resources import files
import os
import shutil
from typing import Callable, NoReturn, Sequence

from pisek.user_errors import InvalidArgument, InvalidOperation
from pisek.utils.colors import ColorSettings
from pisek.utils.user_input import input_string, input_choice
from pisek.config.config_types import (
    TaskType,
    GenType,
    ValidatorType,
    OutCheck,
    JudgeType,
)
from pisek.config.config_hierarchy import DEFAULT_CONFIG_FILENAME
from pisek.task_jobs.program import ProgramRole

EXAMPLE_TASKS_DIR = str(files("pisek").joinpath("../examples"))
EXAMPLE_TASKS = ["cms-batch", "opendata"]

OFFERED_GEN_TYPES = [GenType.pisek_v1, GenType.opendata_v1, GenType.cms_old]
RECOMMENDED_GEN_TYPES = [GenType.pisek_v1]

OFFERED_VALIDATOR_TYPES = [ValidatorType.simple_42]
RECOMMENDED_VALIDATOR_TYPES: list[ValidatorType] = (
    []
)  # All offered validator types are reasonable, no need to recommend anything

OFFERED_JUDGE_TYPES = {
    TaskType.batch: [JudgeType.cms_batch, JudgeType.opendata_v2],
    TaskType.interactive: [JudgeType.cms_communication],
}
RECOMMENDED_JUDGE_TYPES: dict[TaskType, list[JudgeType]] = (
    {  # All offered judge types are reasonable, no need to recommend anything
        TaskType.batch: [],
        TaskType.interactive: [],
    }
)

SOLUTION_SUBDIR = "solutions"


def remove_suffix(path: str) -> str:
    return os.path.splitext(path)[0]


def touch(path: str) -> None:
    open(path, "a").close()


def recommended() -> str:
    return " (" + ColorSettings.colored("recommended", "green") + ")"


def invalid_config_name(config_filename: str) -> NoReturn:
    raise InvalidArgument(f"Config filename '{config_filename}' already in use.")


def input_program(
    p_role: ProgramRole,
    types: Sequence[str],
    recommended_types: Sequence[str],
    no_jumps: bool,
) -> tuple[str, str]:

    choices = [
        (t, t + (recommended() if t in recommended_types else "")) for t in types
    ]
    type_ = input_choice(f"Choose {p_role}_type:", choices, no_jumps)
    filename = input_string(f"Enter {p_role} filename: ")
    print()
    return type_, filename


def init_task(config_filename: str, no_jumps: bool) -> None:
    if os.listdir():
        raise InvalidOperation("Current directory is not empty")

    example_tasks: list[tuple[Callable[[str], None], str]] = [
        (
            partial(from_template, os.path.join(EXAMPLE_TASKS_DIR, task)),
            task + " example task",
        )
        for task in EXAMPLE_TASKS
    ]
    _from_scratch: Callable[[str], None] = partial(from_scratch, no_jumps=no_jumps)
    create = input_choice(
        "Create a task", [(_from_scratch, "From scratch")] + example_tasks, no_jumps
    )
    create(config_filename)


def from_scratch(config_filename: str, no_jumps: bool) -> None:
    config = ConfigParser(interpolation=None)
    config.add_section("task")
    config.add_section("tests")
    config["task"]["version"] = "v3"

    # --- task_type ---
    print()
    task_type = input_choice("Choose task_type:", [(t, t) for t in TaskType], no_jumps)
    config["task"]["task_type"] = task_type
    print()

    # --- inputs ---
    gen_type, gen_name = input_program(
        ProgramRole.gen, OFFERED_GEN_TYPES, RECOMMENDED_GEN_TYPES, no_jumps
    )
    touch(gen_name)
    config["tests"]["in_gen"] = remove_suffix(gen_name)
    config["tests"]["gen_type"] = gen_type

    touch("sample.in")
    touch("sample.out")

    # --- validator ---
    val_type, val_name = input_program(
        ProgramRole.validator,
        OFFERED_VALIDATOR_TYPES,
        RECOMMENDED_VALIDATOR_TYPES,
        no_jumps,
    )
    touch(val_name)
    config["tests"]["validator"] = remove_suffix(val_name)
    config["tests"]["validator_type"] = val_type

    # --- out_check ---
    if task_type == TaskType.batch:
        out_check = input_choice(
            "How to check outputs?",
            [
                (OutCheck.tokens, "tokens - output is unique"),
                (OutCheck.shuffle, "shuffle - output is unique up to order"),
                (OutCheck.judge, "judge - output is not unique"),
            ],
            no_jumps,
        )
        print()
    else:
        out_check = OutCheck.judge

    config["tests"]["out_check"] = out_check

    if out_check == OutCheck.judge:
        judge_type, judge_name = input_program(
            ProgramRole.judge,
            OFFERED_JUDGE_TYPES[task_type],
            RECOMMENDED_JUDGE_TYPES[task_type],
            no_jumps,
        )
        touch(judge_name)
        config["tests"]["out_judge"] = remove_suffix(judge_name)
        config["tests"]["judge_type"] = judge_type

    # --- solutions ---
    os.makedirs(SOLUTION_SUBDIR)
    config.add_section("run_solution")
    config["run_solution"]["time_limit"] = "1"
    config["run_solution"]["subdir"] = "solutions"

    sol = input_string("Enter primary solution filename: ")
    touch(os.path.join(SOLUTION_SUBDIR, sol))
    sol_sec = f"solution_{remove_suffix(sol)}"
    config.add_section(sol_sec)
    config[sol_sec]["primary"] = "yes"

    try:
        with open(config_filename, "x") as f:
            config.write(f, space_around_delimiters=False)
    except FileExistsError:
        invalid_config_name(config_filename)

    print()
    print("For more information visit our docs: https://piskoviste.github.io/pisek/")


def from_template(path: str, config_filename: str) -> None:
    if config_filename != DEFAULT_CONFIG_FILENAME and os.path.exists(
        os.path.join(path, config_filename)
    ):
        invalid_config_name(config_filename)

    for item in os.listdir(path):
        s = os.path.join(path, item)
        if os.path.isdir(s):
            shutil.copytree(s, item)
        else:
            shutil.copy(s, item)

    shutil.move(DEFAULT_CONFIG_FILENAME, config_filename)
