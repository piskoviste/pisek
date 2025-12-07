from abc import ABC, abstractmethod
from difflib import SequenceMatcher
from functools import partial
from importlib.resources import files
import re
from typing import TYPE_CHECKING, Callable, Iterable, Optional

from pisek.utils.text import tab
from pisek.user_errors import TaskConfigError

if TYPE_CHECKING:
    from .config_hierarchy import ConfigHierarchy

CONFIG_DESCRIPTION = str(files("pisek").joinpath("config/config-description"))


def basic_similarity(a: str, b: str) -> float:
    return SequenceMatcher(a=a, b=b).ratio()


def regex_score(regex: str, name: str) -> float:
    if re.match(regex, name):
        return 1.0
    else:
        # XXX: Very incomplete and fragile, but it works
        regex_str = regex.replace(r"(.*)", "\x00").replace(r"\d{2}", "\x00")
        return basic_similarity(regex_str, name)


class ApplicabilityCondition(ABC):
    @abstractmethod
    def check(self, section: str, key: str, config: "ConfigHierarchy") -> str:
        pass


class KeyValueCond(ApplicabilityCondition):
    def __init__(
        self,
        section: "ConfigSectionDescription",
        key: "ConfigKeyDescription",
        value: str,
    ) -> None:
        self.section = section
        self.key = key
        self.value = value
        super().__init__()

    @abstractmethod
    def _op(self, current_value) -> bool:
        pass

    def check(self, section: str, key: str, config: "ConfigHierarchy") -> str:
        section = self.section.transform_name(section)
        key = self.key.transform_name(key)
        current_value = self.key.get(section, key, config)
        if self._op(current_value):
            return ""
        return f"[{section}] {key}={current_value}\n"


class KeyHasValue(KeyValueCond):
    def _op(self, current_value):
        return self.value == current_value


class KeyHasNotValue(KeyValueCond):
    def _op(self, current_value):
        return self.value != current_value


class ConfigSectionDescription:
    def __init__(self, section: str) -> None:
        self.section = section
        self.defaults_to: list[str] = []
        self.dynamic_default: bool = False
        self.similarity_function: Optional[Callable[[str], float]] = None

    def similarity(self, section: str) -> float:
        if self.similarity_function is None:
            return basic_similarity(self.section, section)
        else:
            return self.similarity_function(section)

    def transform_name(self, name: str) -> str:
        return name if self.similarity(name) == 1.0 else self.section


class ConfigKeyDescription:
    def __init__(self, section: ConfigSectionDescription, key: str) -> None:
        self.section = section
        self.key = key
        self.defaults_to: list[tuple[str, str]] = []
        self.dynamic_default: bool = False
        self.applicability_conditions: list[ApplicabilityCondition] = []
        self.similarity_function: Optional[Callable[[str], float]] = None

    def get(self, section: str, key: str, config: "ConfigHierarchy") -> str:
        return config.get_from_candidates(
            [(self.section.transform_name(section), self.transform_name(key))]
            + self.defaults()
        ).value

    def defaults(self) -> list[tuple[str, str]]:
        if self.dynamic_default:
            raise NotImplementedError("Dynamic defaulting not implemented")
        return self.defaults_to + [(d, self.key) for d in self.section.defaults_to]

    def similarity(self, key: str) -> float:
        if self.similarity_function is None:
            return basic_similarity(self.key, key)
        else:
            return self.similarity_function(key)

    def score(self, section: str, key: str) -> float:
        return (9 * self.section.similarity(section) + self.similarity(key)) / 10

    def applicable(self, section: str, key: str, config: "ConfigHierarchy") -> str:
        text = ""
        for cond in self.applicability_conditions:
            text += cond.check(section, key, config)
        return text

    def transform_name(self, name: str) -> str:
        return name if self.similarity(name) == 1.0 else self.key


class ConfigKeysHelper:
    def __init__(self) -> None:
        self.sections: dict[str, ConfigSectionDescription] = {}
        self.keys: dict[tuple[str, str], ConfigKeyDescription] = {}
        self.key_index: dict[str, list[ConfigKeyDescription]] = {}
        add_applicability_conditions: list[
            tuple[ConfigKeyDescription, Callable[[], ApplicabilityCondition]]
        ] = []
        with open(CONFIG_DESCRIPTION) as f:
            section: Optional[ConfigSectionDescription] = None
            last_key: Optional[ConfigKeyDescription] = None
            for line in f:
                line = line.strip()

                if len(line) == 0:
                    pass

                elif line.startswith("#!"):
                    assert section is not None
                    [fun, *args] = line.removeprefix("#!").split()
                    if fun == "regex":
                        if last_key is None:
                            section.similarity_function = partial(regex_score, args[0])
                        else:
                            last_key.similarity_function = partial(regex_score, args[0])
                    elif fun == "if":
                        assert section is not None
                        assert last_key is not None

                        if len(args) == 2 and args[1].count("==") == 1:
                            key_name, value = args[1].split("==")
                            add_applicability_conditions.append(
                                (
                                    last_key,
                                    self._gen_key_has_value(args[0], key_name, value),
                                )
                            )
                        elif len(args) == 2 and args[1].count("!=") == 1:
                            key_name, value = args[1].split("!=")
                            add_applicability_conditions.append(
                                (
                                    last_key,
                                    self._gen_key_has_not_value(
                                        args[0], key_name, value
                                    ),
                                )
                            )
                        else:
                            self._invalid_function_args(fun, args)
                    elif fun == "default":
                        if last_key is None:
                            if len(args) != 1:
                                self._invalid_function_args(fun, args)
                            section.defaults_to.append(args[0])
                        else:
                            if len(args) != 2:
                                self._invalid_function_args(fun, args)
                            last_key.defaults_to.append((args[0], args[1]))
                    elif fun == "dynamic_default":
                        if last_key is None:
                            if len(args) != 0:
                                self._invalid_function_args(fun, args)
                            section.dynamic_default = True
                        else:
                            if len(args) != 0:
                                self._invalid_function_args(fun, args)
                            last_key.dynamic_default = True
                    else:
                        raise ValueError(
                            f"invalid config-description function: '{fun}'"
                        )

                elif line.count("=") == 1 and line[-1] == "=":
                    assert section is not None
                    last_key = ConfigKeyDescription(section, line.removesuffix("="))
                    self.keys[(section.section, last_key.key)] = last_key
                    self.key_index.setdefault(last_key.key, []).append(last_key)

                elif line[0] == "[" and line[-1] == "]":
                    last_key = None
                    section = ConfigSectionDescription(
                        line.removeprefix("[").removesuffix("]")
                    )
                    self.sections[section.section] = section

                elif line.startswith("#"):
                    pass
                else:
                    raise ValueError(f"invalid config-description line: '{line}'")

        for key, lambda_cond in add_applicability_conditions:
            key.applicability_conditions.append(lambda_cond())

    def _gen_key_has_value(
        self, section: str, key: str, value: str
    ) -> Callable[[], KeyValueCond]:
        return lambda: KeyHasValue(
            self.sections[section], self.keys[(section, key)], value
        )

    def _gen_key_has_not_value(
        self, section: str, key: str, value: str
    ) -> Callable[[], KeyValueCond]:
        return lambda: KeyHasNotValue(
            self.sections[section], self.keys[(section, key)], value
        )

    def _invalid_function_args(self, fun_name: str, args: list[str]) -> None:
        raise ValueError(
            f"invalid config-description function {fun_name} arguments: '{' '.join(args)}'"
        )

    def find_section(self, section: str) -> tuple[float, str]:
        return max((s.similarity(section), s.section) for s in self.sections.values())

    def find_key(
        self,
        section: str,
        key: str,
        config: "ConfigHierarchy",
        allow_unapplicable: bool,
    ) -> tuple[float, str, str]:
        keys: Iterable[ConfigKeyDescription]
        if (
            key in self.key_index
            and max(k.score(section, key) for k in self.key_index[key]) == 1.0
        ):
            keys = self.key_index[key]
        else:
            keys = self.keys.values()

        for candidate in keys:
            if candidate.score(section, key) == 1.0:
                if not allow_unapplicable and (
                    text := candidate.applicable(section, key, config)
                ):
                    raise TaskConfigError(
                        f"Key '{key}' not allowed in this context:\n{tab(text).rstrip()}"
                    )
                else:
                    return (1.0, section, candidate.key)

        recommendation = max(
            (
                k.score(section, key),
                k.section.transform_name(section),
                k.transform_name(key),
            )
            for k in self.keys.values()
        )
        assert 0.0 <= recommendation[0] < 1.0
        return recommendation
