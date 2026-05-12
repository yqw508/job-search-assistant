from pathlib import Path

from boss_job_assistant.config import load_config


def test_load_config_returns_nested_values(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
search:
  keyword: "Java"
  city: "广州"
  max_pages: 1
filters:
  min_salary_k: 22
  min_company_size: 100
  required_location: "广州"
scoring:
  positive_keywords: ["Java"]
  c_side_keywords: ["C端"]
  exclude_keywords: ["外包"]
runtime:
  min_delay_seconds: 1
  max_delay_seconds: 2
  output_dir: "output"
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config["search"]["keyword"] == "Java"
    assert config["search"]["city"] == "广州"
    assert config["filters"]["min_salary_k"] == 22
    assert config["runtime"]["output_dir"] == "output"
