from pathlib import Path

from boss_job_assistant.import_saved_html import run


def test_import_saved_html_exports_excel(tmp_path: Path):
    input_dir = tmp_path / "input_html"
    input_dir.mkdir()
    config_file = tmp_path / "config.yaml"
    output_dir = tmp_path / "output"

    config_file.write_text(
        f"""
search:
  keyword: "Java Spring Boot"
  city: "广州"
  city_code: "101280100"
  max_pages: 1
  detail_pages: false
  manual_start: true
filters:
  min_salary_k: 22
  min_company_size: 100
  required_location: "广州"
scoring:
  positive_keywords: ["Java", "Spring Boot", "Redis", "MySQL"]
  c_side_keywords: ["C端", "交易"]
  exclude_keywords: ["外包"]
runtime:
  min_delay_seconds: 1
  max_delay_seconds: 1
  output_dir: "{output_dir.as_posix()}"
""",
        encoding="utf-8",
    )

    (input_dir / "boss.html").write_text(
        """
        <div class="job-card-wrapper">
          <a href="/job_detail/abc.html">
            <span class="job-name">Java 后端开发工程师</span>
            <span class="salary">25-35K</span>
            <span class="job-area">广州</span>
          </a>
          <ul class="tag-list"><li>5-10年</li><li>本科</li></ul>
          <div class="company-name">示例公司</div>
          <ul class="company-tag-list"><li>电商</li><li>B轮</li><li>100-499人</li></ul>
          <div>负责 C端 交易系统，技术栈 Java Spring Boot Redis MySQL。</div>
        </div>
        """,
        encoding="utf-8",
    )

    output_file = run(str(input_dir), str(config_file))

    assert output_file is not None
    assert output_file.exists()
