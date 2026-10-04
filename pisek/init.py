# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2025        Daniel Skýpala <skipy@kam.mff.cuni.cz>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from configparser import ConfigParser
from functools import partial
from importlib.resources import files
import os
from pathlib import Path
import shutil
from typing import Callable, NoReturn, Sequence

from pisek.user_errors import InvalidArgument, InvalidOperation
from pisek.utils.colors import color_settings
from pisek.utils.user_input import input_string, input_choice
from pisek.config.config_types import (
    TaskType,
    GenType,
    ValidatorType,
    OutCheck,
    JudgeType,
)
from pisek.config.task_config import TaskConfigError
from pisek.config.config_hierarchy import (
    DEFAULT_CONFIG_FILENAME,
    CONFIGS_FOLDER,
    ConfigHierarchy,
)
from pisek.task_jobs.program import ProgramRole

EXAMPLE_TASKS_DIR = str(files("pisek").joinpath("../examples"))
EXAMPLE_TASKS = ["cms-batch", "cms-communication", "opendata"]

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


def touch(path: str | Path) -> None:
    open(path, "a").close()


def recommended() -> str:
    return " (" + color_settings.colored("recommended", "green") + ")"


def invalid_config_name(config_filename: str) -> NoReturn:
    raise InvalidArgument(f"Config filename '{config_filename}' already in use.")


def input_program_type(
    p_role: ProgramRole,
    types: Sequence[str],
    recommended_types: Sequence[str],
    no_jumps: bool,
) -> str:
    choices = [
        (t, t + (recommended() if t in recommended_types else "")) for t in types
    ]
    return input_choice(f"Choose {p_role}_type:", choices, no_jumps)


def input_program_filename(p_role: ProgramRole) -> str:
    return input_string(f"Enter {p_role} filename: ")


def _get_key(hierarchy: ConfigHierarchy, section: str, key: str) -> str | None:
    try:
        return hierarchy.get(section, key).value
    except TaskConfigError:
        return None


def _get_key_from_candidates(
    hierarchy: ConfigHierarchy, candidates: list[tuple[str, str | None]]
) -> str | None:
    try:
        return hierarchy.get_from_candidates(candidates).value
    except TaskConfigError:
        return None


def _get_subdir(
    config: ConfigParser,
    hierarchy: ConfigHierarchy,
    run_sections: list[str],
    default: str = ".",
    default_run_section: str | None = None,
) -> Path:
    run_sections.append("run")
    subdir = _get_key_from_candidates(
        hierarchy, [(sec, "subdir") for sec in run_sections]
    )
    if subdir is None:
        subdir = default
        if default != ".":
            assert default_run_section is not None
            config[default_run_section]["subdir"] = default
    if subdir != ".":
        os.makedirs(subdir)
    return Path(subdir)


def _set_task_type(
    config: ConfigParser, hierarchy: ConfigHierarchy, no_jumps: bool
) -> TaskType:
    if (tt := _get_key(hierarchy, "task", "task_type")) is None:
        task_type = input_choice(
            "Choose task_type:", [(t, t) for t in TaskType], no_jumps
        )
        config["task"]["task_type"] = task_type
        print()
    else:
        try:
            task_type = TaskType(tt)
        except ValueError:
            raise TaskConfigError(f"Unknown task_type '{tt}' in organizational config")
    return task_type


def _set_inputs(
    config: ConfigParser, hierarchy: ConfigHierarchy, no_jumps: bool
) -> None:
    print_newline = False
    if _get_key(hierarchy, "tests", "gen_type") is None:
        config["tests"]["gen_type"] = input_program_type(
            ProgramRole.gen, OFFERED_GEN_TYPES, RECOMMENDED_GEN_TYPES, no_jumps
        )
        print_newline = True
    if (gen_name := _get_key(hierarchy, "tests", "in_gen")) is None:
        gen_name = input_program_filename(ProgramRole.gen)
        config["tests"]["in_gen"] = remove_suffix(gen_name)
        print_newline = True

    gen_subdir = _get_subdir(config, hierarchy, ["run_gen"])
    touch(gen_subdir / gen_name)
    touch("sample.in")
    touch("sample.out")

    if print_newline:
        print()


def _set_validator(
    config: ConfigParser, hierarchy: ConfigHierarchy, no_jumps: bool
) -> None:
    print_newline = False
    if _get_key(hierarchy, "tests", "validator_type") is None:
        config["tests"]["validator_type"] = input_program_type(
            ProgramRole.validator,
            OFFERED_VALIDATOR_TYPES,
            RECOMMENDED_VALIDATOR_TYPES,
            no_jumps,
        )
        print_newline = True
    if (val_name := _get_key(hierarchy, "tests", "validator")) is None:
        val_name = input_program_filename(ProgramRole.validator)
        config["tests"]["validator"] = remove_suffix(val_name)
        print_newline = True

    val_subdir = _get_subdir(config, hierarchy, ["run_validator"])
    touch(val_subdir / val_name)

    if print_newline:
        print()


def _set_out_check(
    task_type: TaskType,
    config: ConfigParser,
    hierarchy: ConfigHierarchy,
    no_jumps: bool,
) -> None:
    if task_type == TaskType.batch:
        if (oc := _get_key(hierarchy, "tests", "out_check")) is None:
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
            config["tests"]["out_check"] = out_check
        else:
            try:
                out_check = OutCheck(oc)
            except ValueError:
                raise TaskConfigError(
                    f"Unknown out_check '{oc}' in organizational config"
                )
    else:
        out_check = OutCheck.judge
        if _get_key(hierarchy, "tests", "out_check") is None:
            config["tests"]["out_check"] = out_check

    if out_check == OutCheck.judge:
        print_newline = False
        if _get_key(hierarchy, "tests", "judge_type") is None:
            config["tests"]["judge_type"] = input_program_type(
                ProgramRole.judge,
                OFFERED_JUDGE_TYPES[task_type],
                RECOMMENDED_JUDGE_TYPES[task_type],
                no_jumps,
            )
            print_newline = True
        if (judge_name := _get_key(hierarchy, "tests", "out_judge")) is None:
            judge_name = input_program_filename(ProgramRole.judge)
            config["tests"]["out_judge"] = remove_suffix(judge_name)
            print_newline = True

        judge_subdir = _get_subdir(config, hierarchy, ["run_judge"])
        touch(judge_subdir / judge_name)

        if print_newline:
            print()


def _set_solutions(
    config: ConfigParser, hierarchy: ConfigHierarchy, no_jumps: bool
) -> None:
    config.add_section("run_solution")
    if _get_key(hierarchy, "run_solution", "time_limit") is None:
        config["run_solution"]["time_limit"] = "1"

    sol_subdir = _get_subdir(
        config,
        hierarchy,
        ["run_primary_solution", "run_solution"],
        "solutions",
        "run_solution",
    )
    sol = input_string("Enter primary solution filename: ")
    touch(sol_subdir / sol)
    sol_sec = f"solution_{remove_suffix(sol)}"
    config.add_section(sol_sec)
    config[sol_sec]["primary"] = "yes"
    print()


def from_scratch(config_filename: str, no_jumps: bool, pisek_dir: Path | None) -> None:
    config = ConfigParser(interpolation=None)
    config.add_section("task")
    config.add_section("tests")
    config["task"]["version"] = "v3"

    if pisek_dir is None:
        org_configs = []
    else:
        org_configs = sorted(
            (c, c) for c in os.listdir(os.path.join(pisek_dir, CONFIGS_FOLDER))
        )

    if org_configs:
        assert pisek_dir is not None
        print()
        org_config = input_choice("Choose organization config:", org_configs, no_jumps)
        hierarchy = ConfigHierarchy.org_hierarchy_without_defaults(
            ".", True, pisek_dir, org_config
        )
        config["task"]["use"] = org_config
    else:
        hierarchy = ConfigHierarchy.empty_hierarchy(".", pisek_dir)

    print()
    task_type = _set_task_type(config, hierarchy, no_jumps)
    _set_inputs(config, hierarchy, no_jumps)
    _set_validator(config, hierarchy, no_jumps)
    _set_out_check(task_type, config, hierarchy, no_jumps)
    _set_solutions(config, hierarchy, no_jumps)

    try:
        with open(config_filename, "x") as f:
            config.write(f, space_around_delimiters=False)
    except FileExistsError:
        invalid_config_name(config_filename)

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


def init_task(config_filename: str, no_jumps: bool, pisek_dir: Path | None) -> None:
    if os.listdir():
        raise InvalidOperation("Current directory is not empty")

    example_tasks: list[tuple[Callable[[str], None], str]] = [
        (
            partial(from_template, os.path.join(EXAMPLE_TASKS_DIR, task)),
            task + " example task",
        )
        for task in EXAMPLE_TASKS
    ]
    _from_scratch: Callable[[str], None] = partial(
        from_scratch, no_jumps=no_jumps, pisek_dir=pisek_dir
    )
    create = input_choice(
        "Create a task", [(_from_scratch, "From scratch")] + example_tasks, no_jumps
    )
    create(config_filename)
