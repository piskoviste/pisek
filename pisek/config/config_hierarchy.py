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

from configparser import (
    ConfigParser,
    DuplicateSectionError,
    DuplicateOptionError,
    MissingSectionHeaderError,
)
from dataclasses import dataclass
from importlib.resources import files
import os
import re
from typing import Optional, Iterable

from pisek.utils.text import tab
from pisek.user_errors import TaskConfigError, TaskConfigParsingError

from .update_config import update_config
from .config_description import ConfigKeysHelper

GLOBAL_DEFAULTS = "global-defaults"
GLOBAL_DEFAULTS_FILE = str(files("pisek").joinpath("config", GLOBAL_DEFAULTS))
V2_DEFAULTS = {
    task_type: str(files("pisek").joinpath(f"config/{task_type}-defaults"))
    for task_type in ["kasiopea", "cms"]
}

DEFAULT_CONFIG_FILENAME = "config"


def new_config_parser() -> ConfigParser:
    config = ConfigParser(interpolation=None)
    config.optionxform = lambda x: x  # type: ignore
    return config


@dataclass(frozen=True)
class ConfigValue:
    value: str
    config: str
    section: str
    key: Optional[str]
    internal: bool = False

    @staticmethod
    def make_internal(value: str, section: str, key: Optional[str] = None):
        return ConfigValue(value, "_internal", section, key, True)

    def location(self) -> str:
        text = f"section [{self.section}]"
        if self.key is not None:
            text += f", key '{self.key}'"

        if self.internal:
            text += " (internal pisek value)"
        else:
            text += f" (in config file {os.path.basename(self.config)})"

        return text

    def split(self, sep: Optional[str] = None) -> list["ConfigValue"]:
        return [
            ConfigValue(part, self.config, self.section, self.key, self.internal)
            for part in self.value.split(sep=sep)
        ]

    def change_value(self, new_value: str) -> "ConfigValue":
        return ConfigValue(
            new_value, self.config, self.section, self.key, self.internal
        )


class ConfigHierarchy:
    """Represents hierarchy of config files where last overrides all previous."""

    def __init__(
        self,
        task_path: str,
        info: bool,
        pisek_directory: Optional[str],
        config_filename: str,
    ) -> None:
        self._task_path = task_path
        self._pisek_directory = pisek_directory

        self._config_paths: list[str] = []
        self._configs: list[ConfigParser] = []

        # We want set that stores the order of insertions
        self.loaded_values: dict[ConfigValue, None] = {}

        self._load_config(os.path.join(task_path, config_filename), info)
        self._load_config(GLOBAL_DEFAULTS_FILE, False)

    def _load_config(self, path: str, info: bool = True) -> None:
        self._config_paths.append(path)
        self._configs.append(config := new_config_parser())
        if not self._read_config(config, path):
            raise TaskConfigError(f"Missing config {path}. Is this task folder?")

        update_config(config, self._task_path, info)
        if defaults := config.get("task", "use", fallback=None):
            self._load_config(self._resolve_defaults_config(defaults), False)

    def _read_config(self, config: ConfigParser, path: str) -> bool:
        try:
            res = config.read(path)
        except DuplicateSectionError as e:
            raise TaskConfigParsingError(path, f"Duplicate section [{e.section}]")
        except DuplicateOptionError as e:
            raise TaskConfigParsingError(
                path, f"Duplicate key '{e.option}' in section [{e.section}]"
            )
        except MissingSectionHeaderError as e:
            raise TaskConfigParsingError(path, f"Missing section header")
        return len(res) > 0

    def _resolve_defaults_config(self, name: str):
        def load_from_path(path: str) -> str:
            configs_folder = os.path.join(path, "configs")
            if not os.path.exists(configs_folder):
                raise TaskConfigError(f"'{configs_folder}' does not exist.")
            defaults = os.path.join(configs_folder, name)
            if not os.path.exists(defaults):
                raise TaskConfigError(
                    f"Config '{name}' does not exist in: '{configs_folder}'"
                )
            return defaults

        if name.startswith("@"):
            if (default := V2_DEFAULTS.get(name.removeprefix("@"))) is None:
                raise TaskConfigError(f"Unknown special task_type: '{name}'")
            return default

        if self._pisek_directory is not None:
            return load_from_path(os.path.join(self._task_path, self._pisek_directory))

        current_path = os.path.abspath(self._task_path)
        while current_path:
            if os.path.exists(os.path.join(current_path, ".git")):
                return load_from_path(os.path.join(current_path, "pisek"))
            step_up = os.path.abspath(os.path.join(current_path, ".."))
            if step_up == current_path:
                break  # topmost directory
            if os.stat(step_up).st_uid != os.stat(current_path).st_uid:
                break  # other user's directory
            current_path = step_up

        return name

    def get(self, section: str, key: str | None) -> ConfigValue:
        return self.get_from_candidates([(section, key)])

    def get_from_candidates(
        self, candidates: Iterable[tuple[str, str | None]]
    ) -> ConfigValue:
        unset: bool = False
        for section, key in candidates:
            for config_path, config in zip(self._config_paths, self._configs):
                config_path = os.path.basename(config_path)
                if key is None:
                    value = section if section in config else None
                else:
                    value = config.get(section, key, fallback=None)

                if value == "!unset":
                    unset = True
                    break
                elif value is not None:
                    result = ConfigValue(value, config_path, section, key)
                    self.loaded_values[result] = None
                    return result
            if unset:
                break

        def msg(section_key: tuple[str, str | None]) -> str:
            section, key = section_key
            if key is None:
                return f"Section [{section}]"
            else:
                return f"Key '{key}' in section [{section}]"

        candidates_str = " or\n".join(map(msg, candidates))
        raise TaskConfigError(f"Unset value for:\n{tab(candidates_str)}")

    def get_regex(self, section: str, regex_key: str) -> dict[str, ConfigValue]:
        return self.get_regex_from_candidates([(section, regex_key)])

    def get_regex_from_candidates(
        self, candidates: Iterable[tuple[str, str]]
    ) -> dict[str, ConfigValue]:
        found: dict[str, ConfigValue] = {}
        for section, regex_key in candidates:
            for config_path, config in zip(self._config_paths, self._configs):
                if section not in config:
                    continue

                config_path = os.path.basename(config_path)
                for key, value in config[section].items():
                    if re.fullmatch(regex_key, key) and key not in found:
                        found[key] = ConfigValue(value, config_path, section, key)

        found = {key: val for key, val in found.items() if val != "!unset"}
        self.loaded_values |= {val: None for val in found.values()}
        return found

    def sections(self) -> list[ConfigValue]:
        sections = {
            section: ConfigValue(section, path, section, None)
            for config, path in reversed(list(zip(self._configs, self._config_paths)))
            for section in config.sections()
        }  # We need to use dictionary here because order matters
        return list(sections.values())

    def check_unused(self) -> None:
        """
        Check for unused sections or keys.

        Raises
        ------
        TaskConfigError
            If unused sections or keys are present.
        """
        self._config_helper = ConfigKeysHelper()
        for config_i, config in enumerate(self._configs):
            config_basename = os.path.basename(self._config_paths[config_i])
            for section in config.sections():
                dist, r_section = self._config_helper.find_section(section)
                if dist < 1.0:
                    raise TaskConfigError(
                        f"Unexpected section [{section}] in {config_basename}. "
                        f"(Did you mean [{r_section}]?)"
                    )
                for key in config[section].keys():
                    dist, r_section, r_key = self._config_helper.find_key(
                        section, key, self, config_i > 0
                    )
                    if dist < 1.0:
                        raise TaskConfigError(
                            f"Unexpected key '{key}' in section [{section}] in {config_basename}. "
                            f"(Did you mean '{r_key}'"
                            + (
                                f" in section [{r_section}]"
                                if section != r_section
                                else ""
                            )
                            + "?)"
                        )

    def check_all(self) -> None:
        self.check_unused()

    def check_todos(self) -> bool:
        """Check whether lowest config contains TODO in comments."""
        with open(self._config_paths[0]) as config:
            for line in config:
                if "#" in line and "TODO" in line.split("#")[1]:
                    return True

        return False
