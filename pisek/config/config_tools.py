import os
from typing import Optional

from pisek.config.update_config import update_config
from pisek.config.config_hierarchy import (
    ConfigHierarchy,
    GLOBAL_DEFAULTS,
    new_config_parser,
)
from pisek.config.task_config import load_config, TaskConfig


def update_and_replace_config(
    task_path: str,
    pisek_directory: Optional[str],
    config_filename: str,
) -> None:
    load_config(task_path, pisek_directory, config_filename, suppress_warnings=True)

    config_path = os.path.join(task_path, config_filename)
    config = new_config_parser()
    config.read(config_path)
    update_config(config, task_path=task_path, infos=False)
    with open(config_path, "w") as f:
        config.write(f, space_around_delimiters=False)


def export_config(
    task_path: str,
    pisek_directory: str | None,
    config_filename: str,
    exported_config_path: str,
) -> None:
    config_hierarchy = ConfigHierarchy(
        task_path, False, pisek_directory, config_filename
    )
    TaskConfig.load_dict(config_hierarchy)

    config = new_config_parser()
    config.add_section("task")
    config["task"]["version"] = "v3"

    for config_val in config_hierarchy.loaded_values:
        if not config_val.internal and config_val.config != GLOBAL_DEFAULTS:
            if not config.has_section(config_val.section):
                config.add_section(config_val.section)
            if config_val.key is not None:
                config[config_val.section][config_val.key] = config_val.value

    with open(exported_config_path, "w") as f:
        config.write(f, space_around_delimiters=False)
