from pathlib import Path
from typing import Any

import yaml


REQUIRED_SECTIONS = ("search", "filters", "scoring", "runtime")


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    missing = [section for section in REQUIRED_SECTIONS if section not in data]
    if missing:
        raise ValueError(f"配置缺少必要段落: {', '.join(missing)}")

    return data
