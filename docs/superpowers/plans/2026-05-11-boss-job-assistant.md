# Boss 岗位助手 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个本地半自动浏览器助手，手动登录 Boss 后低频采集广州 Java/Spring Boot 岗位，按用户画像评分并导出 Excel。

**Architecture:** 使用 Python 包结构拆分配置、数据模型、解析、评分、导出和浏览器采集入口。优先完成可单测的纯逻辑模块，再接入 Playwright 的可见浏览器流程，降低页面变化带来的调试成本。

**Tech Stack:** Python 3.10+、Playwright、PyYAML、openpyxl、pytest。

---

## File Structure

- Create: `requirements.txt`，声明运行和测试依赖。
- Create: `config.yaml`，保存默认搜索画像和采集参数。
- Create: `src/boss_job_assistant/__init__.py`，包初始化。
- Create: `src/boss_job_assistant/models.py`，定义 `JobPosting` 和 `ScoredJob` 数据结构。
- Create: `src/boss_job_assistant/config.py`，加载并校验配置。
- Create: `src/boss_job_assistant/scorer.py`，薪资解析、公司规模解析、外包识别和评分。
- Create: `src/boss_job_assistant/exporter.py`，导出 Excel。
- Create: `src/boss_job_assistant/boss_parser.py`，解析 Playwright 页面中的岗位列表和详情字段。
- Create: `src/boss_job_assistant/boss_job_assistant.py`，命令行主入口和浏览器采集流程。
- Create: `tests/test_scorer.py`，评分和解析单元测试。
- Create: `tests/test_config.py`，配置加载测试。
- Create: `tests/test_exporter.py`，Excel 导出测试。
- Create: `README.md`，运行说明、合规边界和常见问题。

---

### Task 1: Project Skeleton And Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `config.yaml`
- Create: `src/boss_job_assistant/__init__.py`
- Create: `src/boss_job_assistant/models.py`

- [ ] **Step 1: Create dependencies**

Write `requirements.txt`:

```txt
playwright>=1.44.0
PyYAML>=6.0.1
openpyxl>=3.1.2
pytest>=8.0.0
```

- [ ] **Step 2: Create default config**

Write `config.yaml`:

```yaml
search:
  keyword: "Java Spring Boot"
  city: "广州"
  max_pages: 2
  detail_pages: true

filters:
  min_salary_k: 22
  min_company_size: 100
  required_location: "广州"

scoring:
  positive_keywords:
    - "Java"
    - "Spring Boot"
    - "SpringCloud"
    - "Spring Cloud"
    - "微服务"
    - "Redis"
    - "MySQL"
    - "MQ"
    - "高并发"
  c_side_keywords:
    - "C端"
    - "C 端"
    - "App"
    - "小程序"
    - "电商"
    - "交易"
    - "支付"
    - "会员"
    - "用户增长"
    - "内容"
    - "社区"
  exclude_keywords:
    - "外包"
    - "驻场"
    - "派遣"
    - "外派"
    - "银行外包"
    - "项目外包"
    - "短期项目"

runtime:
  min_delay_seconds: 2
  max_delay_seconds: 5
  output_dir: "output"
```

- [ ] **Step 3: Create package marker**

Write `src/boss_job_assistant/__init__.py`:

```python
"""Semi-automated Boss job assistant."""
```

- [ ] **Step 4: Create data models**

Write `src/boss_job_assistant/models.py`:

```python
from dataclasses import dataclass, field


@dataclass(slots=True)
class JobPosting:
    title: str = ""
    salary: str = ""
    location: str = ""
    experience: str = ""
    education: str = ""
    company: str = ""
    industry: str = ""
    financing: str = ""
    company_size: str = ""
    url: str = ""
    description: str = ""


@dataclass(slots=True)
class ScoredJob:
    job: JobPosting
    matched: bool
    score: int
    matched_reasons: list[str] = field(default_factory=list)
    exclusion_reason: str = ""
```

- [ ] **Step 5: Run initial import smoke check**

Run:

```bash
python -c "from src.boss_job_assistant.models import JobPosting; print(JobPosting(title='Java'))"
```

Expected: prints a `JobPosting` instance without errors.

---

### Task 2: Config Loader

**Files:**
- Create: `src/boss_job_assistant/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Write `tests/test_config.py`:

```python
from pathlib import Path

from src.boss_job_assistant.config import load_config


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
    assert config["filters"]["min_salary_k"] == 22
    assert config["runtime"]["output_dir"] == "output"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: FAIL because `src.boss_job_assistant.config` does not exist.

- [ ] **Step 3: Implement config loader**

Write `src/boss_job_assistant/config.py`:

```python
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
```

- [ ] **Step 4: Run config tests**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: PASS.

---

### Task 3: Scoring Rules

**Files:**
- Create: `src/boss_job_assistant/scorer.py`
- Create: `tests/test_scorer.py`

- [ ] **Step 1: Write failing scoring tests**

Write `tests/test_scorer.py`:

```python
from src.boss_job_assistant.models import JobPosting
from src.boss_job_assistant.scorer import parse_company_size, parse_salary_lower_bound, score_job


CONFIG = {
    "filters": {
        "min_salary_k": 22,
        "min_company_size": 100,
        "required_location": "广州",
    },
    "scoring": {
        "positive_keywords": ["Java", "Spring Boot", "Redis", "MySQL", "高并发"],
        "c_side_keywords": ["C端", "电商", "交易", "支付", "会员"],
        "exclude_keywords": ["外包", "驻场", "派遣", "外派"],
    },
}


def test_parse_salary_lower_bound():
    assert parse_salary_lower_bound("22-35K·14薪") == 22
    assert parse_salary_lower_bound("30-45K") == 30
    assert parse_salary_lower_bound("薪资面议") == 0


def test_parse_company_size():
    assert parse_company_size("100-499人") == 100
    assert parse_company_size("1000-9999人") == 1000
    assert parse_company_size("少于15人") == 0


def test_score_job_accepts_strong_c_side_match():
    job = JobPosting(
        title="Java 后端开发工程师",
        salary="25-35K",
        location="广州",
        company_size="100-499人",
        description="负责 C端 电商 交易系统，技术栈 Java Spring Boot Redis MySQL 高并发。",
    )

    result = score_job(job, CONFIG)

    assert result.matched is True
    assert result.score >= 80
    assert "薪资满足 22K+" in result.matched_reasons
    assert result.exclusion_reason == ""


def test_score_job_rejects_outsourcing():
    job = JobPosting(
        title="Java 外包开发",
        salary="30-40K",
        location="广州",
        company_size="500-999人",
        description="银行外包项目，长期驻场。",
    )

    result = score_job(job, CONFIG)

    assert result.matched is False
    assert "外包" in result.exclusion_reason
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_scorer.py -v
```

Expected: FAIL because `scorer.py` does not exist.

- [ ] **Step 3: Implement scorer**

Write `src/boss_job_assistant/scorer.py`:

```python
import re
from typing import Any

from .models import JobPosting, ScoredJob


def parse_salary_lower_bound(salary: str) -> int:
    match = re.search(r"(\d+)\s*-\s*\d+\s*K", salary, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)\s*K", salary, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0


def parse_company_size(company_size: str) -> int:
    if "少于" in company_size:
        return 0
    match = re.search(r"(\d+)", company_size)
    if match:
        return int(match.group(1))
    return 0


def _contains_any(text: str, keywords: list[str]) -> list[str]:
    lowered = text.lower()
    return [keyword for keyword in keywords if keyword.lower() in lowered]


def score_job(job: JobPosting, config: dict[str, Any]) -> ScoredJob:
    filters = config["filters"]
    scoring = config["scoring"]
    combined_text = " ".join(
        [
            job.title,
            job.salary,
            job.location,
            job.company,
            job.industry,
            job.company_size,
            job.description,
        ]
    )

    exclusion_hits = _contains_any(combined_text, scoring["exclude_keywords"])
    if exclusion_hits:
        return ScoredJob(job=job, matched=False, score=0, exclusion_reason=f"命中排除关键词: {', '.join(exclusion_hits)}")

    if filters["required_location"] not in job.location:
        return ScoredJob(job=job, matched=False, score=0, exclusion_reason=f"工作地不匹配: {job.location}")

    salary_lower = parse_salary_lower_bound(job.salary)
    if salary_lower < filters["min_salary_k"]:
        return ScoredJob(job=job, matched=False, score=0, exclusion_reason=f"薪资低于 {filters['min_salary_k']}K: {job.salary}")

    company_size_lower = parse_company_size(job.company_size)
    if company_size_lower < filters["min_company_size"]:
        return ScoredJob(job=job, matched=False, score=0, exclusion_reason=f"公司规模低于 {filters['min_company_size']}人: {job.company_size}")

    score = 50
    reasons = [f"薪资满足 {filters['min_salary_k']}K+", f"公司规模满足 {filters['min_company_size']}人+"]

    positive_hits = _contains_any(combined_text, scoring["positive_keywords"])
    if positive_hits:
        score += min(len(positive_hits) * 6, 30)
        reasons.append(f"技术关键词: {', '.join(positive_hits)}")

    c_side_hits = _contains_any(combined_text, scoring["c_side_keywords"])
    if c_side_hits:
        score += min(len(c_side_hits) * 5, 20)
        reasons.append(f"C端关键词: {', '.join(c_side_hits)}")

    return ScoredJob(job=job, matched=True, score=min(score, 100), matched_reasons=reasons)
```

- [ ] **Step 4: Run scoring tests**

Run:

```bash
pytest tests/test_scorer.py -v
```

Expected: PASS.

---

### Task 4: Excel Export

**Files:**
- Create: `src/boss_job_assistant/exporter.py`
- Create: `tests/test_exporter.py`

- [ ] **Step 1: Write failing exporter test**

Write `tests/test_exporter.py`:

```python
from pathlib import Path

from openpyxl import load_workbook

from src.boss_job_assistant.exporter import export_jobs
from src.boss_job_assistant.models import JobPosting, ScoredJob


def test_export_jobs_writes_excel(tmp_path: Path):
    job = JobPosting(
        title="Java 后端",
        salary="25-35K",
        location="广州",
        experience="5-10年",
        education="本科",
        company="示例公司",
        industry="电商",
        financing="B轮",
        company_size="100-499人",
        url="https://www.zhipin.com/job_detail/example.html",
        description="Java Spring Boot C端交易系统",
    )
    scored = ScoredJob(job=job, matched=True, score=90, matched_reasons=["技术关键词: Java"])

    output_file = export_jobs([scored], tmp_path)

    assert output_file.exists()
    workbook = load_workbook(output_file)
    sheet = workbook.active
    assert sheet["A1"].value == "匹配状态"
    assert sheet["C2"].value == "Java 后端"
    assert sheet["M2"].value == "技术关键词: Java"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_exporter.py -v
```

Expected: FAIL because `exporter.py` does not exist.

- [ ] **Step 3: Implement exporter**

Write `src/boss_job_assistant/exporter.py`:

```python
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from .models import ScoredJob


HEADERS = [
    "匹配状态",
    "匹配分",
    "岗位名称",
    "薪资",
    "地点",
    "经验",
    "学历",
    "公司",
    "行业",
    "融资阶段",
    "公司规模",
    "岗位链接",
    "命中原因",
    "排除原因",
    "岗位描述摘要",
]


def _format_sheet(sheet: Worksheet) -> None:
    sheet.auto_filter.ref = sheet.dimensions
    widths = [12, 10, 24, 14, 12, 12, 10, 22, 16, 12, 16, 48, 40, 32, 60]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + index)].width = width


def export_jobs(jobs: list[ScoredJob], output_dir: str | Path) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    file_path = output_path / f"boss_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Boss岗位"
    sheet.append(HEADERS)

    for scored in sorted(jobs, key=lambda item: item.score, reverse=True):
        job = scored.job
        sheet.append(
            [
                "匹配" if scored.matched else "排除",
                scored.score,
                job.title,
                job.salary,
                job.location,
                job.experience,
                job.education,
                job.company,
                job.industry,
                job.financing,
                job.company_size,
                job.url,
                "；".join(scored.matched_reasons),
                scored.exclusion_reason,
                job.description[:300],
            ]
        )

    _format_sheet(sheet)
    workbook.save(file_path)
    return file_path
```

- [ ] **Step 4: Run exporter test**

Run:

```bash
pytest tests/test_exporter.py -v
```

Expected: PASS.

---

### Task 5: Browser Parser

**Files:**
- Create: `src/boss_job_assistant/boss_parser.py`

- [ ] **Step 1: Implement parser helper functions**

Write `src/boss_job_assistant/boss_parser.py`:

```python
from playwright.sync_api import Page

from .models import JobPosting


def _safe_inner_text(page: Page, selector: str) -> str:
    locator = page.locator(selector)
    if locator.count() == 0:
        return ""
    return locator.first.inner_text().strip()


def _absolute_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("http"):
        return url
    return f"https://www.zhipin.com{url}"


def parse_job_cards(page: Page) -> list[JobPosting]:
    cards = page.locator(".job-card-wrapper, .job-card-box")
    jobs: list[JobPosting] = []

    for index in range(cards.count()):
        card = cards.nth(index)
        link = card.locator("a").first
        href = link.get_attribute("href") if link.count() else ""
        tags = card.locator(".tag-list li, .job-card-footer li").all_inner_texts()
        company_info = card.locator(".company-tag-list li, .company-info li").all_inner_texts()

        jobs.append(
            JobPosting(
                title=_first_text(card, ".job-name, .job-title"),
                salary=_first_text(card, ".salary"),
                location=_first_text(card, ".job-area, .job-location"),
                experience=tags[0].strip() if len(tags) > 0 else "",
                education=tags[1].strip() if len(tags) > 1 else "",
                company=_first_text(card, ".company-name"),
                industry=company_info[0].strip() if len(company_info) > 0 else "",
                financing=company_info[1].strip() if len(company_info) > 1 else "",
                company_size=company_info[2].strip() if len(company_info) > 2 else "",
                url=_absolute_url(href or ""),
            )
        )

    return jobs


def _first_text(locator, selector: str) -> str:
    child = locator.locator(selector)
    if child.count() == 0:
        return ""
    return child.first.inner_text().strip()


def fill_detail(page: Page, job: JobPosting) -> JobPosting:
    if not job.url:
        return job

    page.goto(job.url, wait_until="domcontentloaded")
    page.wait_for_timeout(1000)

    description = _safe_inner_text(page, ".job-sec-text, .job-detail-section")
    if description:
        job.description = description

    if not job.company_size:
        job.company_size = _safe_inner_text(page, ".sider-company p:has-text('人')")

    return job
```

- [ ] **Step 2: Note parser verification**

Run parser verification during Task 6 with a real visible browser because Boss page selectors may change. Expected behavior: missing selectors produce empty fields instead of crashing.

---

### Task 6: Main Browser Assistant

**Files:**
- Create: `src/boss_job_assistant/boss_job_assistant.py`

- [ ] **Step 1: Implement main entry point**

Write `src/boss_job_assistant/boss_job_assistant.py`:

```python
import random
import sys
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .boss_parser import fill_detail, parse_job_cards
from .config import load_config
from .exporter import export_jobs
from .scorer import score_job


def _search_url(keyword: str, city: str) -> str:
    return f"https://www.zhipin.com/web/geek/job?query={quote(keyword)}&city={quote(city)}"


def _sleep(page, config: dict) -> None:
    runtime = config["runtime"]
    delay = random.uniform(runtime["min_delay_seconds"], runtime["max_delay_seconds"])
    page.wait_for_timeout(int(delay * 1000))


def wait_for_login(page) -> None:
    print("请在打开的浏览器中手动登录 Boss。登录完成后回到终端按 Enter 继续。")
    input()
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except PlaywrightTimeoutError:
        pass


def run(config_path: str = "config.yaml") -> Path | None:
    config = load_config(config_path)
    collected = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False, slow_mo=200)
        page = browser.new_page()
        page.goto("https://www.zhipin.com/", wait_until="domcontentloaded")
        wait_for_login(page)

        search = config["search"]
        page.goto(_search_url(search["keyword"], search["city"]), wait_until="domcontentloaded")

        for page_number in range(1, search["max_pages"] + 1):
            print(f"正在采集第 {page_number} 页...")
            _sleep(page, config)
            jobs = parse_job_cards(page)

            for job in jobs:
                if search.get("detail_pages", True):
                    try:
                        detail_page = browser.new_page()
                        fill_detail(detail_page, job)
                        detail_page.close()
                        _sleep(page, config)
                    except Exception as exc:
                        print(f"详情页读取失败，保留列表数据: {job.title} - {exc}")
                collected.append(score_job(job, config))

            next_button = page.locator(".options-pages a:has-text('下一页'), a:has-text('下一页')")
            if page_number >= search["max_pages"] or next_button.count() == 0:
                break
            next_button.first.click()
            page.wait_for_load_state("domcontentloaded")

        browser.close()

    if not collected:
        print("没有采集到岗位，请确认已登录、搜索条件有效，或页面结构未发生较大变化。")
        return None

    output_file = export_jobs(collected, config["runtime"]["output_dir"])
    print(f"已导出 {len(collected)} 条岗位: {output_file}")
    return output_file


if __name__ == "__main__":
    config = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    run(config)
```

- [ ] **Step 2: Run import smoke check**

Run:

```bash
python -c "from src.boss_job_assistant.boss_job_assistant import _search_url; print(_search_url('Java Spring Boot', '广州'))"
```

Expected: prints a Boss search URL without import errors.

---

### Task 7: README And Manual Verification

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README**

Write `README.md`:

```markdown
# Boss 岗位助手

这是一个本地半自动浏览器助手，用于个人求职时整理 Boss 直聘上可见的岗位信息。

## 边界

- 不保存账号密码。
- 不绕过验证码或平台验证。
- 不自动投递。
- 不高频并发采集。
- 只整理用户登录后正常可见的信息。

## 安装

```bash
pip install -r requirements.txt
playwright install chromium
```

## 运行

```bash
python -m src.boss_job_assistant.boss_job_assistant config.yaml
```

运行后会打开浏览器。请手动登录 Boss，登录完成后回到终端按 Enter，程序会开始采集并导出 Excel 到 `output/`。

## 配置

编辑 `config.yaml` 可以调整关键词、城市、薪资、公司规模、最大页数和关键词规则。首次建议将 `max_pages` 设为 `1`，确认结果正常后再增加。
```

- [ ] **Step 2: Run full unit test suite**

Run:

```bash
pytest -v
```

Expected: all unit tests PASS.

- [ ] **Step 3: Install browser runtime if needed**

Run:

```bash
playwright install chromium
```

Expected: Chromium browser runtime is installed. If network is blocked, rerun with approval for network access.

- [ ] **Step 4: Manual end-to-end smoke test**

Run:

```bash
python -m src.boss_job_assistant.boss_job_assistant config.yaml
```

Expected:

- Visible browser opens.
- User can manually log in.
- After pressing Enter, script visits search results.
- With `max_pages: 1`, script either exports `output/boss_jobs_*.xlsx` or prints a clear message explaining no jobs were collected.
- If Boss shows verification, script pauses for user handling instead of bypassing it.

---

## Self-Review

- Spec coverage: the plan covers configuration, visible browser login, low-frequency collection, detail parsing, rule scoring, Excel export, README, unit tests, and manual smoke test.
- Placeholder scan: no implementation steps use placeholder wording such as TBD/TODO.
- Type consistency: `JobPosting`, `ScoredJob`, `load_config`, `score_job`, `export_jobs`, `parse_job_cards`, `fill_detail`, and `run` signatures are consistent across tasks.
- Known risk: Boss page selectors may change. The parser is intentionally defensive, and Task 7 includes a real-browser verification step.
