import os
from typing import Optional

from pisek.config.update_config import update_config
from pisek.config.config_hierarchy import new_config_parser
from pisek.config.task_config import load_config


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
