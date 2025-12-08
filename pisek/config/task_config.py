# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2019 - 2022 Václav Volhejn <vaclav.volhejn@gmail.com>
# Copyright (c)   2019 - 2022 Jiří Beneš <mail@jiribenes.com>
# Copyright (c)   2020 - 2022 Michal Töpfer <michal.topfer@gmail.com>
# Copyright (c)   2022        Jiří Kalvoda <jirikalvoda@kam.mff.cuni.cz>
# Copyright (c)   2023        Daniel Skýpala <daniel@honza.info>
# Copyright (c)   2024        Benjamin Swart <benjaminswart@email.cz>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import fnmatch
from functools import cached_property
import os
from pydantic_core import PydanticCustomError, ErrorDetails
from pydantic import (
    Field,
    computed_field,
    field_validator,
    BeforeValidator,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    model_validator,
)
import re
from typing import Any, Annotated, ClassVar, Mapping, Optional, TypeVar, Union

from pisek.utils.paths import TaskPath
from pisek.utils.text import tab
from pisek.utils.text import warn
from pisek.env.base_env import BaseEnv
from pisek.config.config_hierarchy import ConfigValue, TaskConfigError, ConfigHierarchy
from pisek.config.config_types import (
    TaskType,
    GenType,
    ValidatorType,
    OutCheck,
    JudgeType,
    ShuffleMode,
    DataFormat,
    TestPoints,
    ProgramRole,
    BuildStrategyName,
    CMSFeedbackLevel,
    CMSScoreMode,
)
from pisek.env.context import init_context
from pisek.task_jobs.solution.solution_result import TEST_SPEC
from pisek.task_jobs.builder.strategies import ALL_STRATEGIES


T = TypeVar("T")
Maybe = Annotated[T | None, BeforeValidator(lambda t: t or None)]


MaybeInt = Annotated[
    Optional[int], BeforeValidator(lambda i: (None if i == "X" else i))
]
ListStr = Annotated[list[str], BeforeValidator(lambda s: s.split())]

TaskPathFromStr = Annotated[TaskPath, BeforeValidator(lambda s: TaskPath(s))]
OptionalTaskPathFromStr = Annotated[
    Optional[TaskPath], BeforeValidator(lambda s: TaskPath(s) if s else None)
]
ListTaskPathFromStr = Annotated[
    list[TaskPath], BeforeValidator(lambda s: [TaskPath(p) for p in s.split()])
]

MISSING_VALIDATION_CONTEXT = "Missing validation context."

ValuesDict = dict[str, Union[str, "ValuesDict", dict[Any, "ValuesDict"]]]
ConfigValuesDict = Mapping[
    str, Union[ConfigValue, "ConfigValuesDict", dict[Any, "ConfigValuesDict"]]
]


def _to_values(config_values_dict: ConfigValuesDict) -> ValuesDict:
    def convert(what: ConfigValue | Mapping) -> str | dict:
        if isinstance(what, ConfigValue):
            return what.value
        else:
            return {key: convert(val) for key, val in what.items()}

    return {key: convert(val) for key, val in config_values_dict.items()}


def _validate_program_name(key: str, value: str) -> str:
    error_key = key.lower().replace(" ", "_")
    for banned_char in "[]":
        if banned_char in value:
            raise PydanticCustomError(
                f"invalid_{error_key}",
                f"{key.capitalize()} must not contain '{banned_char}'",
            )
    if value.startswith("_"):
        raise PydanticCustomError(
            f"invalid_{error_key}",
            f"{key.capitalize()} must not start with '_'",
        )
    return value


class TaskConfig(BaseEnv):
    """Configuration of task loaded from config file."""

    task: "TaskSection"
    tests: "TestsSection"
    test_sections: dict[int, "TestSection"]

    solutions: dict[str, "SolutionSection"]

    solution_time_limit: float = Field(ge=0)  # Needed for visualization

    limits: "LimitsSection"

    cms: "CMSSection"

    checks: "ChecksSection"

    @computed_field  # type: ignore[misc]
    @cached_property
    def total_points(self) -> int:
        return sum(sub.max_points for sub in self.test_sections.values())

    @computed_field  # type: ignore[misc]
    @property
    def tests_count(self) -> int:
        return len(self.test_sections)

    @computed_field  # type: ignore[misc]
    @cached_property
    def input_globs(self) -> list[str]:
        return sum((sub.all_globs for sub in self.test_sections.values()), start=[])

    @computed_field  # type: ignore[misc]
    @property
    def primary_solution(self) -> str:
        if len(self.solutions) == 0:
            raise RuntimeError("No solutions exist.")
        else:
            return [name for name, sol in self.solutions.items() if sol.primary][0]

    @computed_field  # type: ignore[misc]
    @cached_property
    def max_solution_time_limit(self) -> float:
        return max(
            (solution.run.time_limit for solution in self.solutions.values()), default=0
        )

    def get_solution_by_run(self, run: str) -> Optional[str]:
        sources = (name for name, sol in self.solutions.items() if sol.run.name == run)
        return next(sources, None)

    def __init__(self, **kwargs):
        value = {"test_count": max(kwargs["test_sections"]) + 1}

        with init_context(value):
            super().__init__(**kwargs)

    @staticmethod
    def load_dict(configs: ConfigHierarchy) -> ConfigValuesDict:
        args: dict[str, Any] = {}

        args["task"] = TaskSection.load_dict(configs)
        args["tests"] = TestsSection.load_dict(args["task"]["task_type"].value, configs)

        section_names = configs.sections()

        PROGRAMS = [
            (ProgramRole.gen, "in_gen"),
            (ProgramRole.validator, "validator"),
            (ProgramRole.judge, "out_judge"),
        ]
        for t, program in PROGRAMS:
            if args["tests"][program].value:
                args["tests"][program] = RunSection.load_dict(
                    t, args["tests"][program], configs
                )

        # Load tests
        args["test_sections"] = test_sec = {}
        # Sort so tests.keys() returns tests in sorted order
        for section in sorted(section_names, key=lambda cv: cv.value):
            section_name = section.value
            if m := re.fullmatch(r"test(\d{2})", section_name):
                num = m[1]
                test_sec[int(num)] = TestSection.load_dict(
                    ConfigValue(str(int(num)), section.config, section.section, None),
                    configs,
                )

        args["solutions"] = solutions = {}
        for section in section_names:
            if m := re.fullmatch(r"solution_(.+)", section.value):
                solutions[m[1]] = SolutionSection.load_dict(
                    ConfigValue(m[1], section.config, section.section, None), configs
                )

        args["limits"] = LimitsSection.load_dict(configs)
        args["cms"] = CMSSection.load_dict(configs)
        args["checks"] = ChecksSection.load_dict(configs)

        args["solution_time_limit"] = configs.get_from_candidates(
            [("run_solution", "time_limit"), ("run", "time_limit")]
        )

        return args

    @model_validator(mode="after")
    def validate_model(self):
        if (
            self.task.task_type == TaskType.interactive
            and self.tests.out_check != OutCheck.judge
        ):
            raise PydanticCustomError(
                "interactive_must_have_judge",
                "For interactive task 'out_check' must be 'judge'",
                {"task_type": self.task.task_type, "out_check": self.tests.out_check},
            )

        JUDGE_TYPES = {
            TaskType.batch: [
                None,
                JudgeType.opendata_v1,
                JudgeType.opendata_v2,
                JudgeType.cms_batch,
            ],
            TaskType.interactive: [JudgeType.cms_communication],
        }

        if self.tests.judge_type not in JUDGE_TYPES[self.task.task_type]:
            raise PydanticCustomError(
                "task_judge_type_mismatch",
                f"'{self.tests.judge_type}' judge for '{self.task.task_type}' task is not allowed",
                {"task_type": self.task.task_type, "judge_type": self.tests.judge_type},
            )

        primary = [name for name, sol in self.solutions.items() if sol.primary]
        if len(primary) > 1:
            raise PydanticCustomError(
                "multiple_primary_solutions",
                "Multiple primary solutions",
                {"primary_solutions": primary},
            )
        if len(self.solutions) > 0 and len(primary) == 0:
            raise PydanticCustomError(
                "no_primary_solution",
                "No primary solution set",
                {},
            )

        for i in range(len(self.test_sections)):
            if i not in self.test_sections:
                raise PydanticCustomError(
                    "missing_test",
                    f"Missing section [test{i:02}]",
                    {},
                )

        self._compute_predecessors()
        return self

    def _compute_predecessors(self) -> None:
        visited = set()
        computed = set()

        def compute_test(num: int) -> list[int]:
            test = self.test_sections[num]
            if num in computed:
                return test.all_predecessors
            elif num in visited:
                raise PydanticCustomError(
                    "cyclic_predecessor_tests", "Cyclic predecessor tests", {}
                )

            visited.add(num)
            all_predecessors = sum(
                (compute_test(p) for p in test.direct_predecessors),
                start=test.direct_predecessors,
            )

            def normalize_list(l):
                return list(sorted(set(l)))

            test.all_predecessors = normalize_list(all_predecessors)
            test.prev_globs = normalize_list(
                sum(
                    (self.test_sections[p].in_globs for p in test.all_predecessors),
                    start=[],
                )
            )
            test.all_globs = normalize_list(test.prev_globs + test.in_globs)
            computed.add(num)

            return test.all_predecessors

        for i in range(self.tests_count):
            compute_test(i)


class TaskSection(BaseEnv):
    _section: str = "task"
    task_type: TaskType
    score_precision: int = Field(ge=0)

    @classmethod
    def load_dict(cls, configs: ConfigHierarchy) -> ConfigValuesDict:
        args: dict[str, ConfigValue] = {
            key: configs.get("task", key) for key in cls.model_fields
        }
        return {"_section": configs.get("task", None), **args}


class TestsSection(BaseEnv):
    _section: str = "tests"

    static_subdir: TaskPathFromStr
    in_gen: Maybe["RunSection"]
    gen_type: Maybe[GenType]

    validator: Maybe["RunSection"]
    validator_type: Maybe[ValidatorType]

    out_check: OutCheck
    out_judge: Maybe["RunSection"]
    judge_type: Maybe[JudgeType]
    judge_needs_in: bool | None
    judge_needs_out: bool | None
    tokens_ignore_newlines: bool | None
    tokens_ignore_case: bool | None
    tokens_float_rel_error: Maybe[float]
    tokens_float_abs_error: Maybe[float]
    shuffle_mode: Maybe[ShuffleMode]
    shuffle_ignore_case: bool | None

    in_format: DataFormat
    out_format: DataFormat

    @staticmethod
    def load_dict(task_type: str, configs: ConfigHierarchy) -> ConfigValuesDict:
        GLOBAL_KEYS = [
            "in_gen",
            "validator",
            "out_check",
            "in_format",
            "out_format",
            "static_subdir",
        ]
        PROGRAM_TYPES = [
            ("gen_type", "in_gen"),
            ("validator_type", "validator"),
        ]
        OUT_CHECK_SPECIFIC_KEYS = [
            ((None, "judge"), "out_judge", ""),
            ((None, "judge"), "judge_type", ""),
            ((TaskType.batch, "judge"), "judge_needs_in", "0"),
            ((TaskType.batch, "judge"), "judge_needs_out", "1"),
            ((None, "tokens"), "tokens_ignore_newlines", "0"),
            ((None, "tokens"), "tokens_ignore_case", "0"),
            ((None, "tokens"), "tokens_float_rel_error", ""),
            ((None, "tokens"), "tokens_float_abs_error", ""),
            ((None, "shuffle"), "shuffle_mode", ""),
            ((None, "shuffle"), "shuffle_ignore_case", "0"),
        ]
        args: dict[str, ConfigValue] = {
            key: configs.get("tests", key) for key in GLOBAL_KEYS
        }

        for program_type, program in PROGRAM_TYPES:
            if args[program].value:
                args[program_type] = configs.get("tests", program_type)
            else:
                args[program_type] = ConfigValue.make_internal(
                    "", "tests", program_type
                )

        # Load judge specific keys
        for (task_type_cond, out_check), key, default in OUT_CHECK_SPECIFIC_KEYS:
            if (task_type_cond is None or task_type_cond == task_type) and args[
                "out_check"
            ].value == out_check:
                args[key] = configs.get("tests", key)
            else:
                args[key] = ConfigValue.make_internal(default, "tests", key)

        return {"_section": configs.get("tests", None), **args}

    @model_validator(mode="after")
    def validate_model(self):
        if self.in_gen is not None and self.gen_type is None:
            raise PydanticCustomError(
                "no_gen_type",
                "Missing gen_type",
                {"in_gen": self.in_gen.name, "gen_type": ""},
            )

        if self.validator is not None and self.validator_type is None:
            raise PydanticCustomError(
                "no_validator_type",
                "Missing validator_type",
                {"validator": self.validator.name, "validator_type": ""},
            )

        if (self.tokens_float_abs_error is not None) != (
            self.tokens_float_rel_error is not None
        ):
            raise PydanticCustomError(
                "tokens_errors_must_be_set_together",
                "Both types of floating point error must be set together",
                {
                    "tokens_float_abs_error": self.tokens_float_abs_error,
                    "tokens_float_rel_error": self.tokens_float_rel_error,
                },
            )

        return self


class TestSection(BaseEnv):
    """Configuration of one test (group of testcases)."""

    _section: str
    num: int
    name: str
    points: TestPoints
    in_globs: ListStr
    prev_globs: list[str] = []
    all_globs: list[str] = []
    direct_predecessors: list[int]
    all_predecessors: list[int] = []
    checks_validate: bool
    checks_different_outputs: bool

    @property
    def max_points(self) -> int:
        return 0 if self.points == "unscored" else self.points

    def in_test(self, filename: str) -> bool:
        return any(fnmatch.fnmatch(filename, g) for g in self.all_globs)

    def new_in_test(self, filename: str) -> bool:
        return not any(
            fnmatch.fnmatch(filename, g) for g in self.prev_globs
        ) and self.in_test(filename)

    @staticmethod
    def load_dict(number: ConfigValue, configs: ConfigHierarchy) -> ConfigValuesDict:
        KEYS = [
            "name",
            "points",
            "in_globs",
            "predecessors",
            "checks.validate",
            "checks.different_outputs",
        ]
        args: dict[str, Any] = {
            key.replace(".", "_"): configs.get_from_candidates(
                [(number.section, key), ("tests", key)]
            )
            for key in KEYS
        }
        args["direct_predecessors"] = args.pop("predecessors")

        return {"_section": configs.get(number.section, None), "num": number, **args}

    @field_validator("in_globs", mode="after")
    @classmethod
    def validate_globs(cls, value: list[str], info: ValidationInfo) -> list[str]:
        globs = []
        for glob in value:
            if glob == "@ith":
                glob = f"{info.data['num']:02}*.in"
            if not glob.endswith(".in"):
                raise PydanticCustomError(
                    "in_globs_end_in", "In_globs must end with '.in'"
                )
            globs.append(glob)

        return globs

    @field_validator("direct_predecessors", mode="before")
    @classmethod
    def expand_predecessors(cls, value: str, info: ValidationInfo) -> list[str]:
        if info.context is None:
            raise RuntimeError(MISSING_VALIDATION_CONTEXT)
        test_cnt = info.context.get("test_count")
        number = info.data["num"]

        predecessors = []
        for pred in value.split():
            if pred == "@previous":
                if number <= 1:
                    continue
                predecessors.append(number - 1)
            else:
                try:
                    num = int(pred)
                except ValueError:
                    raise PydanticCustomError(
                        "predecessors_must_be_int", "Predecessors must be int"
                    )
                if not 0 <= num < test_cnt:
                    raise PydanticCustomError(
                        "predecessors_must_be_in_range",
                        f"Predecessors must be in range 0, {test_cnt-1}",
                    )
                predecessors.append(num)

        return list(sorted(set(predecessors)))

    @model_validator(mode="after")
    def validate_model(self):
        if self.name == "@auto":
            self.name = f"Test {self.num}"

        return self


class SolutionSection(BaseEnv):
    """Configuration of one solution."""

    _section: str
    name: str
    primary: bool
    run: "RunSection"
    points: MaybeInt
    points_min: MaybeInt
    points_max: MaybeInt
    tests: str

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    @classmethod
    def load_dict(cls, name: ConfigValue, configs: ConfigHierarchy) -> ConfigValuesDict:
        KEYS = [
            "primary",
            "run",
            "points",
            "points_min",
            "points_max",
            "tests",
        ]
        args = {
            key: configs.get_from_candidates([(name.section, key), ("solutions", key)])
            for key in KEYS
        }

        if args["run"].value == "@auto":
            args["run"] = args["run"].change_value(name.value)

        sol_type = (
            ProgramRole.primary_solution
            if TypeAdapter(bool).validate_strings(args["primary"].value)
            else ProgramRole.secondary_solution
        )

        return {
            "_section": configs.get(name.section, None),
            "name": name,
            **args,
            "run": RunSection.load_dict(sol_type, args["run"], configs),
        }

    @field_validator("name", mode="after")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _validate_program_name("solution name", value)

    @field_validator("tests", mode="after")
    def validate_tests(cls, value, info: ValidationInfo):
        if info.context is None:
            raise RuntimeError(MISSING_VALIDATION_CONTEXT)
        test_cnt = info.context.get("test_count")
        primary = info.data.get("primary")
        if value == "@auto":
            value = ("1" if primary else "X") * test_cnt
        elif value == "@all":
            value = "1" * test_cnt
        elif value == "@any":
            value = "X" * test_cnt

        if len(value) != test_cnt:
            raise PydanticCustomError(
                "tests_str_invalid_len",
                f"There are {test_cnt} tests but test string has {len(value)} characters",
            )

        for char in value:
            if char not in TEST_SPEC:
                raise PydanticCustomError(
                    "tests_str_invalid_char",
                    f"Not allowed char in test string: {char}. Recognized are {''.join(TEST_SPEC.keys())}",
                )

        if primary and value != "1" * test_cnt:
            raise PydanticCustomError(
                "primary_sol_must_succeed",
                f"Primary solution must have: tests={'1'*test_cnt}",
            )

        return value

    @model_validator(mode="after")
    def validate_model(self):
        for points_limit in ["points_min", "points_max"]:
            if self.points is not None and getattr(self, points_limit) is not None:
                raise PydanticCustomError(
                    "points_double_set",
                    f"Both 'points' and '{points_limit}' are set at once",
                    {"points": self.points, points_limit: getattr(self, points_limit)},
                )

        return self


def get_run_defaults(program_role: ProgramRole, program_name: str) -> list[str]:
    if program_role.is_solution():
        return [
            f"run_solution:{program_name}",
            f"run_{program_role}",
            f"run_solution",
            f"run",
        ]
    else:
        return [
            f"run_{program_role}:{program_name}",
            f"run_{program_role}",
            f"run",
        ]


class RunSection(BaseEnv):
    """Configuration of running an program"""

    _section: str

    program_role: ProgramRole
    name: str
    subdir: str
    build: "BuildSection"
    exec: TaskPathFromStr
    time_limit: float = Field(ge=0)  # [seconds]
    clock_mul: float = Field(ge=0)  # [1]
    clock_min: float = Field(ge=0)  # [seconds]
    mem_limit: int = Field(ge=0)  # [KB]
    process_limit: int = Field(ge=0)  # [1]
    # limit=0 means unlimited
    args: ListStr
    env: dict[str, str]

    @property
    def executable(self) -> TaskPath:
        return TaskPath.executable_path(self.build.program_name, self.exec.path)

    def clock_limit(self, override_time_limit: Optional[float] = None) -> float:
        tl = override_time_limit if override_time_limit is not None else self.time_limit
        if tl == 0:
            return 0
        return max(tl * self.clock_mul, self.clock_min)

    @classmethod
    def load_dict(
        cls, program_role: ProgramRole, name: ConfigValue, configs: ConfigHierarchy
    ) -> ConfigValuesDict:
        default_sections = get_run_defaults(program_role, name.value)

        section_name = configs.get_from_candidates(
            [(section, None) for section in default_sections]
        )
        args = {
            key: configs.get_from_candidates(
                [(section, key) for section in default_sections]
            )
            for key in cls.model_fields
            if key not in ("name", "program_role", "env")
        }
        if args["build"].value == "@auto":
            args["build"] = args["build"].change_value(
                f"{program_role.build_name}:{os.path.join(args['subdir'].value, name.value)}"
            )

        envs = configs.get_regex_from_candidates(
            (section, "env_(.*)") for section in default_sections
        )
        envs = {key.removeprefix("env_"): val for key, val in envs.items()}

        return {
            "_section": section_name,
            "program_role": ConfigValue.make_internal(
                program_role.name, "run", "program_role"
            ),
            "name": name,
            **args,
            "build": BuildSection.load_dict(args["build"], configs),
            "env": envs,
        }

    @field_validator("name", mode="after")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _validate_program_name("program name", value)

    @field_validator("env", mode="before")
    def interpolate_env(cls, dictionary: dict[str, str]) -> dict[str, str]:
        def raise_err(error_type: str, message: str, key: str):
            raise PydanticCustomError(
                error_type, message, {"_loc": key, f"env_{key}": dictionary[key]}
            )

        def interpolate(key: str, val: str) -> str:
            state: list[str] = [""]
            i = 0
            while i < len(val):
                char = val[i]
                if char == "\\":
                    if i == len(val) - 1:
                        raise_err("env_wrong_escape", "Unterminated escape", key)
                    i += 1
                    state[-1] += val[i]
                elif val[i : i + 2] == "${":
                    state.append("")
                    i += 1
                elif char == "}" and len(state) > 1:
                    var_name = state.pop()
                    if var_name not in os.environ:
                        raise_err(
                            "unknown_variable",
                            f"No environment variable '{var_name}'",
                            key,
                        )
                    state[-1] += os.environ[var_name]
                elif char in "${}":
                    raise_err("unescaped_char", f"Unescaped character '{char}'", key)
                else:
                    state[-1] += char

                i += 1

            if len(state) > 1:
                raise_err(
                    "env_unterminated_interpolation", "Unterminated interpolation", key
                )

            return state[0]

        for key in dictionary:
            dictionary[key] = interpolate(key, dictionary[key])
        return dictionary


class BuildSection(BaseEnv):
    program_names: ClassVar[dict[str, str]] = {}

    _section: str
    section_name: str
    build_type: str
    program_name: str

    sources: ListTaskPathFromStr
    comp_args: ListStr
    extras: ListTaskPathFromStr
    strategy: BuildStrategyName
    entrypoint: str

    headers_c: ListTaskPathFromStr
    extra_sources_c: ListTaskPathFromStr
    headers_cpp: ListTaskPathFromStr
    extra_sources_cpp: ListTaskPathFromStr
    extra_sources_py: ListTaskPathFromStr
    extra_sources_java: ListTaskPathFromStr

    @classmethod
    def load_dict(cls, name: ConfigValue, configs: ConfigHierarchy) -> ConfigValuesDict:
        program = name
        program_role = ConfigValue("", name.config, name.section, name.key)
        default_sections = [f"build:{program.value}", "build"]
        for pt in ProgramRole:
            prefix = f"{pt.build_name}:"
            if name.value.startswith(prefix):
                program_role, program = name.split(":")
                default_sections = [
                    f"build_{pt.build_name}:{program.value}",
                    f"build_{pt.build_name}",
                    f"build",
                ]
                break

        if (
            program.value in cls.program_names
            and cls.program_names[program.value] != default_sections[0]
        ):
            raise TaskConfigError(
                "Colliding suffixes of build sections not allowed: "
                f"[{default_sections[0]}] and [{cls.program_names[program.value]}]."
            )
        cls.program_names[program.value] = default_sections[0]

        section_name = configs.get_from_candidates(
            [(section, None) for section in default_sections]
        )
        args = {
            key: configs.get_from_candidates(
                [(section, key) for section in default_sections]
            )
            for key in cls.model_fields
            if key not in ("section_name", "build_type", "program_name")
        }

        return {
            "_section": section_name,
            "section_name": ConfigValue.make_internal(
                default_sections[0], default_sections[0], None
            ),
            "build_type": program_role,
            "program_name": program,
            **args,
        }

    @field_validator("program_name", mode="after")
    @classmethod
    def validate_program_name(cls, value: str) -> str:
        return _validate_program_name("program name", value)

    @field_validator("sources", mode="before")
    @classmethod
    def convert_sources(cls, value: str, info: ValidationInfo) -> str:
        if value == "@auto":
            return str(info.data.get("program_name"))
        else:
            return value


class LimitsSection(BaseEnv):
    """Configuration of input and output size limits."""

    _section: str = "limits"

    input_max_size: int
    output_max_size: int

    @classmethod
    def load_dict(cls, configs: ConfigHierarchy) -> ConfigValuesDict:
        args: dict[str, ConfigValue] = {
            key: configs.get("limits", key) for key in cls.model_fields
        }
        return {"_section": configs.get("limits", None), **args}


class CMSSection(BaseEnv):
    _section: str = "cms"

    name: Maybe[str]
    title: str
    submission_format: ListStr

    time_limit: float = Field(gt=0)  # [seconds]
    mem_limit: int = Field(gt=0)  # [KB]

    max_submissions: MaybeInt = Field(gt=0)
    min_submission_interval: int = Field(ge=0)  # [seconds]

    score_mode: CMSScoreMode
    feedback_level: CMSFeedbackLevel

    stubs: ListTaskPathFromStr
    headers: ListTaskPathFromStr

    @classmethod
    def load_dict(cls, configs: ConfigHierarchy) -> ConfigValuesDict:
        args = {key: configs.get("cms", key) for key in cls.model_fields}

        def get_strategy_union(key: str) -> str:
            all_items = {
                configs.get_from_candidates(
                    [
                        ("build_solution", getattr(strat, key)),
                        ("build", getattr(strat, key)),
                    ]
                ).value
                for strat in ALL_STRATEGIES.values()
                if getattr(strat, key) is not None
            }
            return " ".join(sorted(all_items))

        if args["stubs"].value == "@auto":
            args["stubs"] = args["stubs"].change_value(
                get_strategy_union("extra_sources")
            )
        if args["headers"].value == "@auto":
            args["headers"] = args["headers"].change_value(
                get_strategy_union("extra_nonsources")
            )

        return {"_section": configs.get("cms", None), **args}

    @field_validator("title", mode="before")
    @classmethod
    def convert_title(cls, value: str, info: ValidationInfo) -> str:
        if value == "@name":
            name = info.data.get("name")
            name = "unnamed-task" if name is None else name

            return name
        else:
            return value

    @field_validator("submission_format", mode="after")
    @classmethod
    def convert_format(cls, value: list[str], info: ValidationInfo) -> list[str]:
        name = info.data.get("name")
        name = "unnamed-task" if name is None else name

        return [
            (CMSSection.get_default_file_name(name) if n == "@name" else n)
            for n in value
        ]

    @classmethod
    def get_default_file_name(cls, name: str):
        name = re.sub(r"[^a-zA-Z0-9]+", "_", name)
        return f"{name}.%l"


class ChecksSection(BaseEnv):
    """Configuration of checks for pisek to run."""

    _section: str = "checks"

    solution_for_each_test: bool
    no_unused_inputs: bool
    all_inputs_in_last_test: bool
    generator_respects_seed: bool
    one_input_in_each_nonsample_test: bool
    fuzzing_thoroughness: int
    judge_rejects_trailing_string: bool

    @classmethod
    def load_dict(cls, configs: ConfigHierarchy) -> ConfigValuesDict:
        args: dict[str, ConfigValue] = {
            key: configs.get("checks", key) for key in cls.model_fields
        }
        return {"_section": configs.get("checks", None), **args}


def _format_message(err: ErrorDetails) -> str:
    inp = err["input"]
    ctx = err["ctx"] if "ctx" in err else None
    if isinstance(inp, dict) and ctx is not None:
        if ctx == {}:
            return f"{err['msg']}."
        return f"{err['msg']}:\n" + tab(
            "\n".join(
                f"{key}={val}" for key, val in ctx.items() if not key.startswith("_")
            )
        )
    return f"{err['msg']}: '{inp}'"


def _convert_errors(e: ValidationError, config_values: ConfigValuesDict) -> list[str]:
    error_msgs: list[str] = []
    for error in e.errors():
        value: Any = config_values
        for loc in error["loc"]:
            value = value[loc]

        if isinstance(value, ConfigValue):
            location = value.location()
        elif "_section" in value:
            location = value["_section"].location()
        else:
            location = value[error["ctx"]["_loc"]].location()

        error_msgs.append(f"In {location}:\n" + tab(_format_message(error)))
    return error_msgs


def load_config(
    path: str,
    pisek_directory: Optional[str],
    config_filename: str,
    strict: bool = False,
    suppress_warnings: bool = False,
) -> TaskConfig:
    """Loads config from given path."""
    try:
        config_hierarchy = ConfigHierarchy(
            path, not suppress_warnings, pisek_directory, config_filename
        )
        config_values = TaskConfig.load_dict(config_hierarchy)
        config = TaskConfig(**_to_values(config_values))
        config_hierarchy.check_all()
        if config_hierarchy.check_todos() and not suppress_warnings:
            warn("Unsolved TODOs in config.", TaskConfigError, strict)
        return config
    except ValidationError as err:
        raise TaskConfigError(
            "Invalid config:\n\n" + "\n\n".join(_convert_errors(err, config_values))
        )
