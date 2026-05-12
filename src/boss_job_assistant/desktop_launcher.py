import os
import shutil
import sys
import threading
import time
import webbrowser
from pathlib import Path

import yaml

from boss_job_assistant.local_service import HOST, PORT, run_server


APP_DIR_NAME = "JobSearchAssistant"


def bundled_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def user_data_dir() -> Path:
    root = Path.home() / APP_DIR_NAME
    if "LOCALAPPDATA" in os.environ:
        local_app_data = Path(os.environ["LOCALAPPDATA"])
        root = local_app_data / APP_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def prepare_config() -> Path:
    data_dir = user_data_dir()
    config_path = data_dir / "config.yaml"
    if config_path.exists():
        return config_path

    template_path = bundled_base_dir() / "config.yaml"
    config = {}
    if template_path.exists():
        with template_path.open("r", encoding="utf-8") as file:
            config = yaml.safe_load(file) or {}

    output_dir = data_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    config.setdefault("runtime", {})
    config["runtime"]["output_dir"] = str(output_dir)
    config["runtime"]["database_path"] = str(output_dir / "boss_jobs.sqlite3")

    with config_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(config, file, allow_unicode=True, sort_keys=False)
    return config_path


def sync_bundled_assets(base_dir: Path | None = None, data_dir: Path | None = None) -> None:
    source_root = base_dir or bundled_base_dir()
    target_root = data_dir or user_data_dir()

    for directory_name in ("extension", "docs"):
        source_dir = source_root / directory_name
        target_dir = target_root / directory_name
        if source_dir.exists():
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(source_dir, target_dir)

    readme = source_root / "README.md"
    if readme.exists():
        shutil.copy2(readme, target_root / "README.md")


def open_dashboard_later() -> None:
    time.sleep(1.2)
    webbrowser.open(f"http://{HOST}:{PORT}")


def main() -> None:
    sync_bundled_assets()
    config_path = prepare_config()
    threading.Thread(target=open_dashboard_later, daemon=True).start()
    run_server(str(config_path), HOST, PORT)


if __name__ == "__main__":
    main()
