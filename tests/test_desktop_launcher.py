import yaml

from boss_job_assistant.desktop_launcher import prepare_config


def test_prepare_config_creates_user_writable_runtime_config(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    config_path = prepare_config()

    assert config_path == tmp_path / "JobSearchAssistant" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["runtime"]["output_dir"] == str(tmp_path / "JobSearchAssistant" / "output")
    assert config["runtime"]["database_path"] == str(
        tmp_path / "JobSearchAssistant" / "output" / "boss_jobs.sqlite3"
    )


def test_prepare_config_keeps_existing_user_config(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    config_dir = tmp_path / "JobSearchAssistant"
    config_dir.mkdir()
    config_path = config_dir / "config.yaml"
    config_path.write_text("runtime:\n  database_path: custom.sqlite3\n", encoding="utf-8")

    assert prepare_config() == config_path
    assert "custom.sqlite3" in config_path.read_text(encoding="utf-8")
