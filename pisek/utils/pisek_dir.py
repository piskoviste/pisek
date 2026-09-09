import os
from pathlib import Path

CONFIGS_FOLDER = "configs"


def pisek_dir_configs(pisek_dir: Path) -> list[str]:
    return os.listdir(os.path.join(pisek_dir, CONFIGS_FOLDER))
