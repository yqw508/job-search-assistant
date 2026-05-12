from __future__ import annotations

import sys
from pathlib import Path

from boss_job_assistant.config import load_config
from boss_job_assistant.exporter import export_jobs
from boss_job_assistant.html_parser import parse_jobs_from_html_file
from boss_job_assistant.scorer import score_job


def run(input_dir: str = "input_html", config_path: str = "config.yaml") -> Path | None:
    config = load_config(config_path)
    html_dir = Path(input_dir)
    html_dir.mkdir(parents=True, exist_ok=True)

    html_files = sorted([*html_dir.glob("*.html"), *html_dir.glob("*.htm")])
    if not html_files:
        print(f"没有找到 HTML 文件。请先把 Boss 搜索结果页保存到目录: {html_dir.resolve()}")
        return None

    scored_jobs = []
    for html_file in html_files:
        jobs = parse_jobs_from_html_file(html_file)
        print(f"{html_file.name}: 解析到 {len(jobs)} 个岗位")
        scored_jobs.extend(score_job(job, config) for job in jobs)

    if not scored_jobs:
        print("没有解析到岗位，请确认保存的是 Boss 岗位搜索结果页。")
        return None

    output_file = export_jobs(scored_jobs, config["runtime"]["output_dir"])
    print(f"已导出 {len(scored_jobs)} 个岗位: {output_file}")
    return output_file


if __name__ == "__main__":
    input_dir = sys.argv[1] if len(sys.argv) > 1 else "input_html"
    config_path = sys.argv[2] if len(sys.argv) > 2 else "config.yaml"
    run(input_dir, config_path)
