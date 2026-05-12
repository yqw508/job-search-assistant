import html
import json
import re
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import yaml

from boss_job_assistant.config import load_config
from boss_job_assistant.models import JobPosting
from boss_job_assistant.scorer import parse_company_size, parse_salary_upper_bound, score_job
from boss_job_assistant.skills import extract_skill_mentions
from boss_job_assistant.storage import (
    create_interview,
    create_project,
    get_saved_job,
    get_skill_detail,
    get_skill_mentions_for_job,
    interview_skill_stats,
    init_db,
    job_key,
    list_interviews,
    list_projects,
    list_saved_jobs,
    list_skills,
    unsave_job,
    update_tracking,
    update_skill_profile,
    upsert_job_skill_mentions,
    upsert_saved_job,
)


HOST = "127.0.0.1"
PORT = 8765
MAX_BODY_BYTES = 2 * 1024 * 1024
DESCRIPTION_HEADING_PATTERN = (
    r"职位描述|岗位职责|职位职责|任职要求|岗位要求|工作内容|职位福利|知识技能|知识技能要求|专业技能"
)
DESCRIPTION_STOP_SECTION_PATTERN = r"竞争力分析|相似职位|推荐职位|看过该职位的人还看了|公司介绍|工商信息|工作地址|职位发布者|BOSS直聘温馨提示|求职安全提示"
DEFAULT_COMMUTE_MAX_MINUTES = 60

JOB_FIELDS = (
    "title",
    "salary",
    "location",
    "experience",
    "education",
    "company",
    "industry",
    "financing",
    "company_size",
    "source",
    "source_job_id",
    "source_url",
    "url",
    "description",
)


class ClientInputError(ValueError):
    pass


def _safe_str(value: Any) -> str:
    return str(value if value is not None else "")


def _source_label(source: Any) -> str:
    labels = {
        "boss": "Boss",
        "liepin": "猎聘",
        "lagou": "拉勾",
        "zhilian": "智联",
        "51job": "前程无忧",
        "manual": "手动录入",
    }
    return labels.get(_safe_str(source).strip().lower(), "来源")


def _source_url(job: dict[str, Any]) -> str:
    return _safe_str(job.get("source_url") or job.get("url") or "")


def _request_job_key(payload: dict[str, Any]) -> str:
    explicit_key = _safe_str(payload.get("job_key")).strip()
    if explicit_key:
        return explicit_key
    if isinstance(payload.get("job"), dict):
        return job_key(payload["job"])
    url = _safe_str(payload.get("url")).strip()
    if url:
        return job_key({"source": payload.get("source", "boss"), "url": url, "source_url": url})
    return ""


def _job_data_from_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}

    extension_json = item.get("extension_json")
    if isinstance(extension_json, str):
        try:
            extension_json = json.loads(extension_json)
        except json.JSONDecodeError:
            extension_json = {}

    if isinstance(extension_json, dict):
        return {**item, **extension_json}

    return item


def jobs_from_payload(payload: dict[str, Any]) -> list[JobPosting]:
    raw_jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    if "job" in payload and isinstance(payload.get("job"), dict):
        raw_jobs = [payload["job"]]
    if not isinstance(raw_jobs, list):
        return []

    jobs = []
    for item in raw_jobs:
        job_data = _job_data_from_item(item)
        if "source" not in job_data and payload.get("source"):
            job_data["source"] = payload.get("source")
        if "source_url" not in job_data and job_data.get("url"):
            job_data["source_url"] = job_data.get("url")
        jobs.append(
            JobPosting(**{field: _safe_str(job_data.get(field, "")) for field in JOB_FIELDS})
        )

    return jobs


def get_db_path(config: dict[str, Any]) -> Path:
    runtime = config.get("runtime", {})
    configured = runtime.get("database_path")
    if configured:
        return Path(configured)
    return Path(runtime.get("output_dir", "output")) / "boss_jobs.sqlite3"


def _keywords_to_text(keywords: Any) -> str:
    if not isinstance(keywords, list):
        return ""
    return "\n".join(str(item) for item in keywords if str(item).strip())


def _text_to_keywords(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


def settings_from_config(config: dict[str, Any]) -> dict[str, Any]:
    filters = config.get("filters", {})
    scoring = config.get("scoring", {})
    commute = config.get("commute", {})
    return {
        "min_salary_k": int(filters.get("min_salary_k", 0) or 0),
        "min_company_size": int(filters.get("min_company_size", 0) or 0),
        "required_location": str(filters.get("required_location", "") or ""),
        "positive_keywords": list(scoring.get("positive_keywords", []) or []),
        "c_side_keywords": list(scoring.get("c_side_keywords", []) or []),
        "exclude_keywords": list(scoring.get("exclude_keywords", []) or []),
        "home_address": str(commute.get("home_address", "") or ""),
        "max_commute_minutes": int(
            commute.get("max_commute_minutes", DEFAULT_COMMUTE_MAX_MINUTES)
            or DEFAULT_COMMUTE_MAX_MINUTES
        ),
        "map_provider": str(commute.get("map_provider", "amap") or "amap"),
        "map_api_key": str(commute.get("map_api_key", "") or ""),
    }


def update_settings_response(payload: dict[str, Any], config_path: str | Path) -> dict[str, Any]:
    config_file = Path(config_path)
    with config_file.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    config.setdefault("filters", {})
    config.setdefault("scoring", {})
    config.setdefault("commute", {})

    try:
        min_salary_k = int(payload.get("min_salary_k", config["filters"].get("min_salary_k", 0)) or 0)
        min_company_size = int(
            payload.get("min_company_size", config["filters"].get("min_company_size", 0)) or 0
        )
        max_commute_minutes = int(
            payload.get(
                "max_commute_minutes",
                config["commute"].get("max_commute_minutes", DEFAULT_COMMUTE_MAX_MINUTES),
            )
            or DEFAULT_COMMUTE_MAX_MINUTES
        )
    except (TypeError, ValueError) as exc:
        raise ClientInputError("薪资、公司规模和通勤时间必须是数字") from exc

    if min_salary_k < 0 or min_company_size < 0 or max_commute_minutes < 0:
        raise ClientInputError("薪资、公司规模和通勤时间不能小于 0")

    config["filters"]["min_salary_k"] = min_salary_k
    config["filters"]["min_company_size"] = min_company_size
    config["filters"]["required_location"] = _safe_str(
        payload.get("required_location", config["filters"].get("required_location", ""))
    )
    config["scoring"]["positive_keywords"] = _text_to_keywords(
        payload.get("positive_keywords", config["scoring"].get("positive_keywords", []))
    )
    config["scoring"]["c_side_keywords"] = _text_to_keywords(
        payload.get("c_side_keywords", config["scoring"].get("c_side_keywords", []))
    )
    config["scoring"]["exclude_keywords"] = _text_to_keywords(
        payload.get("exclude_keywords", config["scoring"].get("exclude_keywords", []))
    )
    config["commute"]["home_address"] = _safe_str(
        payload.get("home_address", config["commute"].get("home_address", ""))
    )
    config["commute"]["max_commute_minutes"] = max_commute_minutes
    config["commute"]["map_provider"] = _safe_str(
        payload.get("map_provider", config["commute"].get("map_provider", "amap"))
    )
    config["commute"]["map_api_key"] = _safe_str(
        payload.get("map_api_key", config["commute"].get("map_api_key", ""))
    )

    with config_file.open("w", encoding="utf-8") as file:
        yaml.safe_dump(config, file, allow_unicode=True, sort_keys=False)

    return {"ok": True, "settings": settings_from_config(config)}


def _keyword_hits(text: str, keywords: list[str]) -> list[str]:
    hits = []
    for keyword in keywords:
        keyword_text = str(keyword or "").strip()
        if not keyword_text:
            continue
        if re.search(r"[A-Za-z]", keyword_text):
            pattern = (
                rf"(?<![A-Za-z0-9_]){re.escape(keyword_text)}"
                rf"(?![A-Za-z0-9_])"
            )
            matched = re.search(pattern, text, re.IGNORECASE)
        else:
            matched = keyword_text in text
        if matched and keyword_text not in hits:
            hits.append(keyword_text)
    return hits


def _match_items(job: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    settings = settings_from_config(config)
    text = " ".join(
        [
            _safe_str(job.get("title")),
            _safe_str(job.get("salary")),
            _safe_str(job.get("location")),
            _safe_str(job.get("company")),
            _safe_str(job.get("industry")),
            _safe_str(job.get("company_size")),
            _safe_str(job.get("description")),
        ]
    )

    salary_upper = parse_salary_upper_bound(_safe_str(job.get("salary")))
    company_size = parse_company_size(_safe_str(job.get("company_size")))
    required_location = settings["required_location"]
    positive_hits = _keyword_hits(text, settings["positive_keywords"])
    c_side_hits = _keyword_hits(text, settings["c_side_keywords"])
    exclude_hits = _keyword_hits(text, settings["exclude_keywords"])
    max_commute_minutes = settings["max_commute_minutes"]
    home_address = settings["home_address"]

    items = [
        {
            "label": "薪资",
            "status": "match" if salary_upper >= settings["min_salary_k"] else "miss",
            "detail": f"上限 {salary_upper}K / 目标 {settings['min_salary_k']}K+",
            "value": min(100, int(salary_upper / max(settings["min_salary_k"], 1) * 100)),
        },
        {
            "label": "地点",
            "status": "match"
            if required_location and required_location in _safe_str(job.get("location"))
            else "miss",
            "detail": _safe_str(job.get("location")) or "未识别地点",
            "value": 100 if required_location and required_location in _safe_str(job.get("location")) else 25,
        },
        {
            "label": "公司规模",
            "status": "match" if company_size >= settings["min_company_size"] else "miss",
            "detail": f"{_safe_str(job.get('company_size')) or '未识别'} / 目标 {settings['min_company_size']}人+",
            "value": min(100, int(company_size / max(settings["min_company_size"], 1) * 100)),
        },
        {
            "label": "技术关键词",
            "status": "match" if positive_hits else "miss",
            "detail": "、".join(positive_hits) if positive_hits else "未命中正向关键词",
            "value": min(100, len(positive_hits) * 20),
        },
        {
            "label": "C端匹配",
            "status": "match" if c_side_hits else "miss",
            "detail": "、".join(c_side_hits) if c_side_hits else "未命中 C 端关键词",
            "value": min(100, len(c_side_hits) * 30),
        },
        {
            "label": "风险项",
            "status": "risk" if exclude_hits else "match",
            "detail": "、".join(exclude_hits) if exclude_hits else "未命中外包/驻场等排除词",
            "value": 100 if not exclude_hits else 15,
        },
    ]

    if home_address:
        commute_detail = f"家庭地址已配置，地图 API 接入后按 {max_commute_minutes} 分钟阈值计算"
        commute_status = "pending"
        commute_value = 45
    else:
        commute_detail = "未配置家庭地址"
        commute_status = "pending"
        commute_value = 15

    items.append(
        {
            "label": "通勤",
            "status": commute_status,
            "detail": commute_detail,
            "value": commute_value,
        }
    )
    return items


def _status_text(status: str) -> str:
    return {"match": "已匹配", "miss": "未匹配", "risk": "风险", "pending": "待计算"}.get(
        status, "待计算"
    )


def _render_match_chart(items: list[dict[str, Any]], compact: bool = False) -> str:
    item_class = "match-item compact" if compact else "match-item"
    rows = []
    for item in items:
        status = html.escape(_safe_str(item.get("status")))
        value = max(0, min(100, int(item.get("value") or 0)))
        rows.append(
            f"""
            <div class="{item_class} {status}">
              <div class="match-head">
                <span>{html.escape(_safe_str(item.get("label")))}</span>
                <strong>{html.escape(_status_text(_safe_str(item.get("status"))))}</strong>
              </div>
              <div class="match-bar"><span style="width: {value}%"></span></div>
              <div class="match-detail">{html.escape(_safe_str(item.get("detail")))}</div>
            </div>
            """
        )
    return "\n".join(rows)


def _dashboard_stats(jobs: list[dict[str, Any]]) -> dict[str, int]:
    pending = sum(1 for job in jobs if _safe_str(job.get("tracking_status")) in ("", "未投递"))
    stats = {
        "total": len(jobs),
        "strong": sum(1 for job in jobs if int(job.get("score") or 0) >= 80),
        "matched": sum(1 for job in jobs if job.get("matched")),
        "interviewing": sum(1 for job in jobs if "面试" in _safe_str(job.get("tracking_status"))),
        "applied": sum(1 for job in jobs if "投递" in _safe_str(job.get("tracking_status"))),
        "pending": pending,
        "rejected": sum(1 for job in jobs if "淘汰" in _safe_str(job.get("tracking_status"))),
    }
    return stats


def save_job_response(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    jobs = jobs_from_payload(payload)
    if not jobs:
        return {"ok": False, "error": "没有读取到当前岗位，请先在 Boss 手动点开一个岗位详情"}

    db_path = get_db_path(config)
    scored_job = score_job(jobs[0], config)
    saved_job = upsert_saved_job(db_path, scored_job)
    upsert_job_skill_mentions(db_path, saved_job["job_key"], extract_skill_mentions(saved_job))
    return {"ok": True, "job": saved_job, "database": str(db_path.resolve())}


def _allowed_origin(origin: str | None) -> bool:
    if not origin:
        return True
    return origin.startswith(("chrome-extension://", "edge-extension://"))


def _is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def _clean_description_text(value: Any) -> str:
    text = _safe_str(value)
    text = re.sub(
        r"[A-Za-z0-9_-]{2,}\{[^{}]*(?:display|visibility|width|height|font-size|font-style|font-weight|line-height|overflow)[^{}]*\}",
        "",
        text,
    )
    text = re.sub(
        r"\{[^{}]*(?:display|visibility|width|height|font-size|font-style|font-weight|line-height|overflow)[^{}]*\}",
        "",
        text,
    )
    text = re.sub(r"(?:查看更多信息|求职工具|职场指南|热门职位|推荐职位|BOSS直聘).*", "", text)
    text = re.split(rf"(?:^|\n|\s)(?:{DESCRIPTION_STOP_SECTION_PATTERN})(?:\s|[:：]|$)", text, maxsplit=1)[0]
    marker_match = re.search(rf"({DESCRIPTION_HEADING_PATTERN})[:：]?", text)
    if marker_match:
        text = text[marker_match.start() :]
    text = re.sub(
        rf"(?<!\n)({DESCRIPTION_HEADING_PATTERN})[:：]",
        r"\n\n\1：",
        text,
    )
    text = re.sub(r"(?<!\n)(\d+[.、])", r"\n\1", text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _description_sections(description: str) -> list[tuple[str, str]]:
    text = _clean_description_text(description)
    if not text:
        return [("职位描述", "暂无职位描述")]

    parts = re.split(
        rf"\n*({DESCRIPTION_HEADING_PATTERN})[:：]?\n*",
        text,
    )
    sections: list[tuple[str, str]] = []
    prefix = parts[0].strip() if parts else ""
    if prefix:
        sections.append(("职位描述", prefix))

    for index in range(1, len(parts), 2):
        title = parts[index].strip()
        body = parts[index + 1].strip() if index + 1 < len(parts) else ""
        if body:
            sections.append((title, body))

    return sections or [("职位描述", text)]


def _looks_like_tag_section(section_title: str, section_body: str) -> bool:
    if section_title != "职位描述":
        return False

    lines = [line.strip() for line in section_body.splitlines() if line.strip()]
    if not lines or len(lines) > 20:
        return False

    for line in lines:
        if len(line) > 28:
            return False
        if re.search(r"[\d]+[\.\、]|[。；;，,：:]|负责|要求|经验|能力|开发|设计|优化", line):
            return False

    return True


def _render_description_tags(section_body: str) -> str:
    tags = [line.strip() for line in section_body.splitlines() if line.strip()]
    tag_html = "\n".join(f"<span>{html.escape(tag)}</span>" for tag in tags)
    return f'<div class="description-tags">{tag_html}</div>'


def _render_description_body(section_body: str) -> str:
    fragments: list[str] = []
    list_open = False

    for raw_line in section_body.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        numbered = re.match(r"^(?:\d+[\.\、]|[一二三四五六七八九十]+[、.])\s*(.+)$", line)
        if numbered:
            if not list_open:
                fragments.append('<ol class="description-list">')
                list_open = True
            fragments.append(f"<li>{html.escape(numbered.group(1).strip())}</li>")
            continue

        if list_open:
            fragments.append("</ol>")
            list_open = False
        fragments.append(f"<p>{html.escape(line)}</p>")

    if list_open:
        fragments.append("</ol>")

    return "\n".join(fragments) or "<p>暂无职位描述</p>"


def _keyword_chips(job: dict[str, Any]) -> list[str]:
    text = " ".join(
        [
            _safe_str(job.get("title")),
            _safe_str(job.get("description")),
            " ".join(job.get("matched_reasons") or []),
        ]
    )
    candidates = [
        "Java",
        "Spring",
        "Spring Boot",
        "SpringCloud",
        "MySQL",
        "Redis",
        "Kafka",
        "MQ",
        "C端",
        "高并发",
    ]
    chips = []
    for item in candidates:
        if item.lower() in text.lower() and item not in chips:
            chips.append(item)
    return chips[:8]


def _job_detail_href(job: dict[str, Any]) -> str:
    return "/jobs/detail?job_key=" + quote(_safe_str(job.get("job_key", "")), safe="")


def _sidebar_nav(active: str) -> str:
    items = [
        ("dashboard", "/", "总览"),
        ("jobs", "/jobs/page", "岗位列表"),
        ("skills", "/skills/page", "技能库"),
        ("projects", "/projects/page", "项目经验"),
        ("interviews", "/interviews/page", "面试记录"),
        ("settings", "/settings/page", "配置"),
    ]
    links = []
    for key, href, label in items:
        active_class = " active" if key == active else ""
        links.append(f'<a class="side-link{active_class}" href="{href}">{label}</a>')
    return "\n".join(links)


def _layout_styles() -> str:
    return """
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #172033; background: #f3f6f7; }
    .app-shell { min-height: 100vh; display: grid; grid-template-columns: 220px minmax(0, 1fr); }
    .sidebar { background: #ffffff; border-right: 1px solid #e5e7eb; padding: 20px 14px; }
    .brand { margin: 0 0 22px; padding: 0 10px; font-size: 20px; font-weight: 800; color: #111827; }
    .side-nav { display: grid; gap: 6px; }
    .side-link { display: block; padding: 10px 12px; border-radius: 6px; color: #475467; text-decoration: none; font-weight: 600; }
    .side-link:hover { background: #f3f6f8; color: #0f766e; }
    .side-link.active { background: #e6f7f6; color: #007c78; }
    .content { min-width: 0; }
    .page-header { padding: 20px 28px; background: #ffffff; border-bottom: 1px solid #e5e7eb; }
    .page-header h1 { margin: 0; font-size: 22px; }
    main { padding: 20px 28px; }
    a { color: #0f766e; text-decoration: none; }
    @media (max-width: 760px) {
      .app-shell { display: block; }
      .sidebar { position: sticky; top: 0; z-index: 2; border-right: 0; border-bottom: 1px solid #e5e7eb; padding: 12px; }
      .brand { margin: 0 0 10px; padding: 0; font-size: 18px; }
      .side-nav { display: flex; gap: 8px; overflow-x: auto; }
      .side-link { white-space: nowrap; }
      .page-header, main { padding: 12px; }
    }
    """


def _html_settings_page(config: dict[str, Any]) -> str:
    settings = settings_from_config(config)
    required_location = html.escape(settings["required_location"])
    positive_keywords = html.escape(_keywords_to_text(settings["positive_keywords"]))
    c_side_keywords = html.escape(_keywords_to_text(settings["c_side_keywords"]))
    exclude_keywords = html.escape(_keywords_to_text(settings["exclude_keywords"]))
    home_address = html.escape(settings["home_address"])
    map_api_key = html.escape(settings["map_api_key"])
    map_provider = html.escape(settings["map_provider"])
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>匹配规则配置</title>
  <style>
    {_layout_styles()}
    main {{ max-width: 1080px; margin: 0 auto; }}
    .panel {{ background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 18px; }}
    .panel h2 {{ margin: 0 0 14px; font-size: 17px; }}
    .settings-grid {{ display: grid; grid-template-columns: repeat(3, minmax(180px, 1fr)); gap: 14px; }}
    .keyword-grid {{ display: grid; grid-template-columns: repeat(3, minmax(220px, 1fr)); gap: 14px; margin-top: 14px; }}
    label {{ display: grid; gap: 6px; color: #374151; font-size: 13px; }}
    input, textarea {{ box-sizing: border-box; width: 100%; border: 1px solid #d1d5db; border-radius: 6px; padding: 8px; font: inherit; }}
    textarea {{ min-height: 104px; resize: vertical; }}
    .actions {{ margin-top: 14px; display: flex; align-items: center; gap: 12px; }}
    button {{ border: 0; border-radius: 6px; padding: 9px 14px; color: #ffffff; background: #0f766e; cursor: pointer; font: inherit; }}
    #settings-status {{ color: #4b5563; font-size: 13px; }}
    @media (max-width: 860px) {{
      .settings-grid, .keyword-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">Boss 职位助手</div>
      <nav class="side-nav">{_sidebar_nav("settings")}</nav>
    </aside>
    <div class="content">
      <header class="page-header"><h1>匹配规则配置</h1></header>
      <main>
    <section class="panel">
      <h2>基础筛选</h2>
      <form id="settings-form">
        <div class="settings-grid">
          <label>最低薪资 K
            <input name="min_salary_k" type="number" min="0" value="{settings["min_salary_k"]}">
          </label>
          <label>最低公司人数
            <input name="min_company_size" type="number" min="0" value="{settings["min_company_size"]}">
          </label>
          <label>要求地点
            <input name="required_location" value="{required_location}">
          </label>
          <label>家庭地址
            <input name="home_address" value="{home_address}" placeholder="例如：广州天河区...">
          </label>
          <label>最大通勤分钟
            <input name="max_commute_minutes" type="number" min="0" value="{settings["max_commute_minutes"]}">
          </label>
          <label>地图服务
            <input name="map_provider" value="{map_provider}" placeholder="amap">
          </label>
        </div>
        <div class="keyword-grid">
          <label>正向关键词
            <textarea name="positive_keywords">{positive_keywords}</textarea>
          </label>
          <label>C端关键词
            <textarea name="c_side_keywords">{c_side_keywords}</textarea>
          </label>
          <label>排除关键词
            <textarea name="exclude_keywords">{exclude_keywords}</textarea>
          </label>
          <label>地图 API Key
            <textarea name="map_api_key" placeholder="后续用于公共交通时间计算">{map_api_key}</textarea>
          </label>
        </div>
        <div class="actions">
          <button type="submit">保存配置</button>
          <span id="settings-status">每行一个关键词，保存后对新收藏岗位生效。</span>
        </div>
      </form>
    </section>
      </main>
    </div>
  </div>
  <script>
    document.getElementById("settings-form").addEventListener("submit", async function (event) {{
      event.preventDefault();
      const status = document.getElementById("settings-status");
      const formData = new FormData(event.currentTarget);
      const payload = Object.fromEntries(formData.entries());
      status.textContent = "正在保存...";
      try {{
        const response = await fetch("/settings", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload),
        }});
        const result = await response.json();
        if (!response.ok || !result.ok) {{
          throw new Error(result.error || "保存失败");
        }}
        status.textContent = "配置已保存。后续新收藏岗位会使用新规则评分。";
      }} catch (error) {{
        status.textContent = "保存失败：" + (error && error.message ? error.message : String(error));
      }}
    }});
  </script>
</body>
</html>"""


def _html_dashboard_page(jobs: list[dict[str, Any]]) -> str:
    stats = _dashboard_stats(jobs)
    conversion = int(stats["interviewing"] / max(stats["applied"], 1) * 100) if stats["applied"] else 0
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>求职总览</title>
  <style>
    {_layout_styles()}
    main {{ max-width: 1120px; margin: 0 auto; }}
    .stats-table, .panel {{ background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; }}
    .stats-table {{ width: 100%; border-collapse: separate; border-spacing: 0; overflow: hidden; }}
    .stats-table th, .stats-table td {{ padding: 16px; border-bottom: 1px solid #eef1f4; text-align: left; }}
    .stats-table th {{ color: #667085; background: #f8fafc; font-size: 13px; font-weight: 600; }}
    .stats-table td strong {{ display: block; color: #111827; font-size: 28px; }}
    .stats-table tr:last-child td {{ border-bottom: 0; }}
    .panel {{ margin-top: 18px; padding: 18px; }}
    .quick-actions {{ display: flex; flex-wrap: wrap; gap: 12px; }}
    .quick-actions a {{ display: inline-flex; align-items: center; min-height: 36px; padding: 0 14px; border-radius: 6px; background: #0f766e; color: #ffffff; }}
    .quick-actions a.secondary {{ background: #eef6f6; color: #0f766e; }}
    @media (max-width: 720px) {{
      .stats-table, .stats-table tbody, .stats-table tr, .stats-table th, .stats-table td {{ display: block; }}
      .stats-table thead {{ display: none; }}
      .stats-table td {{ border-bottom: 1px solid #eef1f4; }}
    }}
  </style>
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">Boss 职位助手</div>
      <nav class="side-nav">{_sidebar_nav("dashboard")}</nav>
    </aside>
    <div class="content">
      <header class="page-header"><h1>求职总览</h1></header>
      <main>
    <table class="stats-table">
      <thead>
        <tr>
          <th>适合岗位</th>
          <th>强匹配</th>
          <th>待投递</th>
          <th>已投递</th>
          <th>面试中</th>
          <th>淘汰/不合适</th>
          <th>面试转化率</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>{stats["matched"]}</strong>通过当前规则</td>
          <td><strong>{stats["strong"]}</strong>80 分以上</td>
          <td><strong>{stats["pending"]}</strong>尚未投递</td>
          <td><strong>{stats["applied"]}</strong>已进入投递池</td>
          <td><strong>{stats["interviewing"]}</strong>正在推进</td>
          <td><strong>{stats["rejected"]}</strong>已标记淘汰</td>
          <td><strong>{conversion}%</strong>面试 / 投递</td>
        </tr>
      </tbody>
    </table>
    <section class="panel">
      <div class="quick-actions">
        <a href="/jobs/page">查看具体岗位</a>
        <a class="secondary" href="/settings/page">调整匹配配置</a>
      </div>
    </section>
      </main>
    </div>
  </div>
</body>
</html>"""


def _html_jobs_page(jobs: list[dict[str, Any]], config: dict[str, Any]) -> str:
    cards = []
    for job in jobs:
        reasons = html.escape("；".join(job.get("matched_reasons") or []))
        exclusion_reason = html.escape(job.get("exclusion_reason") or "")
        title = html.escape(job.get("title") or "未命名岗位")
        company = html.escape(job.get("company") or "")
        url = html.escape(_source_url(job) or "#")
        source_label = html.escape(_source_label(job.get("source")))
        detail_href = html.escape(_job_detail_href(job))
        match_chart = _render_match_chart(_match_items(job, config), compact=True)
        status_class = "matched" if job.get("matched") else "excluded"
        search_text = html.escape(
            " ".join(
                [
                    _safe_str(job.get("title")),
                    _safe_str(job.get("company")),
                    _safe_str(job.get("location")),
                    _safe_str(job.get("salary")),
                    _safe_str(job.get("company_size")),
                    _safe_str(job.get("tracking_status")),
                    _safe_str(job.get("description")),
                    " ".join(job.get("matched_reasons") or []),
                    _safe_str(job.get("exclusion_reason")),
                ]
            ).lower()
        )
        tracking_status = html.escape(_safe_str(job.get("tracking_status") or "未投递"))
        salary_upper = parse_salary_upper_bound(_safe_str(job.get("salary")))
        cards.append(
            f"""
            <article
              class="job-card {status_class}"
              data-score="{int(job.get("score") or 0)}"
              data-salary-upper="{salary_upper}"
              data-updated="{html.escape(_safe_str(job.get("updated_at")))}"
              data-status="{tracking_status}"
              data-matched="{1 if job.get("matched") else 0}"
              data-text="{search_text}"
            >
              <div class="job-main">
                <div>
                  <a class="job-title" href="{detail_href}">{title}</a>
                  <div class="muted">{company}</div>
                </div>
                <div class="score-badge">{int(job.get("score") or 0)}</div>
              </div>
              <div class="job-meta">
                <span>{html.escape(job.get("salary") or "薪资未知")}</span>
                <span>{html.escape(job.get("location") or "地点未知")}</span>
                <span>{html.escape(job.get("company_size") or "规模未知")}</span>
                <span>{tracking_status}</span>
              </div>
              <div class="match-grid compact-grid">{match_chart}</div>
              <div class="job-foot">
                <span class="muted">{reasons or exclusion_reason or "暂无匹配说明"}</span>
                <span>
                  <a href="{detail_href}">详情分析</a>
                  <a href="{url}" target="_blank" rel="noreferrer">{source_label} 原岗位</a>
                </span>
              </div>
            </article>
            """
        )

    job_cards = "\n".join(cards) or '<div class="empty">还没有收藏岗位。</div>'
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>岗位列表</title>
  <style>
    {_layout_styles()}
    section {{ margin-bottom: 20px; }}
    .metric, .job-card, .filters {{ background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(5, minmax(120px, 1fr)); gap: 12px; }}
    .metric {{ padding: 14px; }}
    .metric strong {{ display: block; margin-top: 6px; font-size: 24px; }}
    a {{ color: #0f766e; text-decoration: none; }}
    .muted {{ margin-top: 4px; color: #6b7280; font-size: 12px; line-height: 1.4; }}
    .empty {{ text-align: center; color: #6b7280; padding: 32px; }}
    .filters {{ padding: 14px; }}
    .filter-grid {{ display: grid; grid-template-columns: minmax(220px, 2fr) repeat(5, minmax(120px, 1fr)); gap: 10px; }}
    label {{ display: grid; gap: 5px; color: #475467; font-size: 12px; }}
    input, select {{ box-sizing: border-box; width: 100%; border: 1px solid #d1d5db; border-radius: 6px; padding: 8px; font: inherit; background: #ffffff; }}
    .filter-actions {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-top: 12px; }}
    button {{ border: 0; border-radius: 6px; padding: 8px 12px; color: #ffffff; background: #0f766e; cursor: pointer; font: inherit; }}
    button:disabled {{ cursor: not-allowed; opacity: 0.45; }}
    #filter-summary {{ color: #667085; font-size: 13px; }}
    .job-list {{ display: grid; gap: 14px; }}
    .pagination {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-top: 14px; padding: 12px 14px; border: 1px solid #e5e7eb; border-radius: 8px; background: #ffffff; }}
    .pagination-actions {{ display: flex; align-items: center; gap: 8px; }}
    #page-info {{ color: #475467; font-size: 13px; min-width: 90px; text-align: center; }}
    .job-card {{ padding: 16px; }}
    .job-main {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }}
    .job-title {{ color: #111827; font-size: 17px; font-weight: 700; }}
    .score-badge {{ display: grid; place-items: center; min-width: 46px; height: 46px; border-radius: 50%; background: #ecfdf5; color: #047857; font-size: 18px; font-weight: 800; }}
    .excluded .score-badge {{ background: #fff1f2; color: #be123c; }}
    .job-meta {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }}
    .job-meta span {{ padding: 5px 9px; border-radius: 4px; background: #f3f6f8; color: #475467; font-size: 13px; }}
    .match-grid {{ display: grid; grid-template-columns: repeat(2, minmax(180px, 1fr)); gap: 10px; }}
    .compact-grid {{ grid-template-columns: repeat(4, minmax(120px, 1fr)); }}
    .match-item {{ padding: 10px; border: 1px solid #e5e7eb; border-radius: 8px; background: #ffffff; }}
    .match-item.compact {{ padding: 8px; }}
    .match-head {{ display: flex; justify-content: space-between; gap: 8px; font-size: 13px; }}
    .match-head strong {{ color: #667085; }}
    .match-bar {{ height: 7px; margin: 8px 0; overflow: hidden; border-radius: 999px; background: #eef2f6; }}
    .match-bar span {{ display: block; height: 100%; border-radius: inherit; background: #00b8b0; }}
    .miss .match-bar span {{ background: #f59e0b; }}
    .risk .match-bar span {{ background: #f43f5e; }}
    .pending .match-bar span {{ background: #94a3b8; }}
    .match-detail {{ color: #667085; font-size: 12px; line-height: 1.4; }}
    .job-foot {{ display: flex; justify-content: space-between; gap: 12px; margin-top: 12px; padding-top: 12px; border-top: 1px solid #eef1f4; }}
    .job-foot span:last-child {{ display: flex; gap: 12px; white-space: nowrap; }}
    @media (max-width: 980px) {{
      .metrics, .compact-grid, .filter-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 640px) {{
      .metrics, .match-grid, .compact-grid, .filter-grid {{ grid-template-columns: 1fr; }}
      .job-main, .job-foot {{ display: block; }}
      .score-badge {{ margin-top: 10px; }}
      .job-foot span:last-child {{ margin-top: 10px; }}
      .pagination {{ display: block; }}
      .pagination-actions {{ margin-top: 10px; justify-content: space-between; }}
    }}
  </style>
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">Boss 职位助手</div>
      <nav class="side-nav">{_sidebar_nav("jobs")}</nav>
    </aside>
    <div class="content">
      <header class="page-header"><h1>岗位列表</h1></header>
      <main>
    <section class="filters">
      <div class="filter-grid">
        <label>关键词
          <input id="filter-keyword" placeholder="岗位、公司、地点、技术关键词">
        </label>
        <label>匹配结果
          <select id="filter-match">
            <option value="all">全部</option>
            <option value="matched">已匹配</option>
            <option value="excluded">未匹配/风险</option>
          </select>
        </label>
        <label>跟进状态
          <select id="filter-status">
            <option value="all">全部</option>
            <option value="未投递">未投递</option>
            <option value="已投递">已投递</option>
            <option value="面试">面试中</option>
            <option value="淘汰">淘汰/不合适</option>
          </select>
        </label>
        <label>最低分
          <input id="filter-score" type="number" min="0" max="100" value="0">
        </label>
        <label>排序
          <select id="sort-jobs">
            <option value="score_desc">匹配分从高到低</option>
            <option value="updated_desc">最近更新优先</option>
            <option value="salary_desc">薪资上限从高到低</option>
            <option value="score_asc">匹配分从低到高</option>
          </select>
        </label>
        <label>每页数量
          <select id="page-size">
            <option value="10">10 条</option>
            <option value="20">20 条</option>
            <option value="50">50 条</option>
            <option value="all">全部</option>
          </select>
        </label>
      </div>
      <div class="filter-actions">
        <span id="filter-summary">显示全部岗位</span>
        <button id="filter-reset" type="button">重置筛选</button>
      </div>
    </section>
    <section class="job-list">
      {job_cards}
    </section>
    <section class="pagination" aria-label="分页">
      <span id="page-summary">共 0 个岗位</span>
      <div class="pagination-actions">
        <button id="page-prev" type="button">上一页</button>
        <span id="page-info">1 / 1</span>
        <button id="page-next" type="button">下一页</button>
      </div>
    </section>
      </main>
    </div>
  </div>
  <script>
    const cards = Array.from(document.querySelectorAll(".job-card"));
    const list = document.querySelector(".job-list");
    const keywordInput = document.getElementById("filter-keyword");
    const matchInput = document.getElementById("filter-match");
    const statusInput = document.getElementById("filter-status");
    const scoreInput = document.getElementById("filter-score");
    const sortInput = document.getElementById("sort-jobs");
    const pageSizeInput = document.getElementById("page-size");
    const summary = document.getElementById("filter-summary");
    const pageSummary = document.getElementById("page-summary");
    const pageInfo = document.getElementById("page-info");
    const pagePrev = document.getElementById("page-prev");
    const pageNext = document.getElementById("page-next");
    const resetButton = document.getElementById("filter-reset");
    let currentPage = 1;

    function numeric(card, key) {{
      return Number(card.dataset[key] || 0);
    }}

    function applyFilters() {{
      const keyword = keywordInput.value.trim().toLowerCase();
      const match = matchInput.value;
      const status = statusInput.value;
      const minScore = Number(scoreInput.value || 0);
      const sort = sortInput.value;
      const pageSizeValue = pageSizeInput.value;

      let visible = cards.filter((card) => {{
        const textOk = !keyword || card.dataset.text.includes(keyword);
        const matchOk =
          match === "all" ||
          (match === "matched" && card.dataset.matched === "1") ||
          (match === "excluded" && card.dataset.matched !== "1");
        const statusOk = status === "all" || card.dataset.status.includes(status);
        const scoreOk = numeric(card, "score") >= minScore;
        return textOk && matchOk && statusOk && scoreOk;
      }});

      visible.sort((a, b) => {{
        if (sort === "score_asc") return numeric(a, "score") - numeric(b, "score");
        if (sort === "salary_desc") return numeric(b, "salaryUpper") - numeric(a, "salaryUpper");
        if (sort === "updated_desc") return String(b.dataset.updated).localeCompare(String(a.dataset.updated));
        return numeric(b, "score") - numeric(a, "score");
      }});

      cards.forEach((card) => {{ card.style.display = "none"; }});
      visible.forEach((card) => {{
        list.appendChild(card);
      }});

      const pageSize = pageSizeValue === "all" ? Math.max(visible.length, 1) : Number(pageSizeValue || 10);
      const totalPages = Math.max(1, Math.ceil(visible.length / pageSize));
      currentPage = Math.min(Math.max(currentPage, 1), totalPages);
      const start = (currentPage - 1) * pageSize;
      const paged = visible.slice(start, start + pageSize);
      paged.forEach((card) => {{ card.style.display = ""; }});

      summary.textContent = `筛选出 ${{visible.length}} / ${{cards.length}} 个岗位`;
      pageSummary.textContent = visible.length
        ? `显示第 ${{start + 1}}-${{start + paged.length}} 个，共 ${{visible.length}} 个岗位`
        : "没有符合条件的岗位";
      pageInfo.textContent = `${{currentPage}} / ${{totalPages}}`;
      pagePrev.disabled = currentPage <= 1;
      pageNext.disabled = currentPage >= totalPages;
    }}

    [keywordInput, matchInput, statusInput, scoreInput, sortInput, pageSizeInput].forEach((input) => {{
      input.addEventListener("input", () => {{
        currentPage = 1;
        applyFilters();
      }});
      input.addEventListener("change", () => {{
        currentPage = 1;
        applyFilters();
      }});
    }});

    pagePrev.addEventListener("click", () => {{
      currentPage -= 1;
      applyFilters();
    }});

    pageNext.addEventListener("click", () => {{
      currentPage += 1;
      applyFilters();
    }});

    resetButton.addEventListener("click", () => {{
      keywordInput.value = "";
      matchInput.value = "all";
      statusInput.value = "all";
      scoreInput.value = "0";
      sortInput.value = "score_desc";
      pageSizeInput.value = "10";
      currentPage = 1;
      applyFilters();
    }});

    applyFilters();
  </script>
</body>
</html>"""


def _html_skills_page(skills: list[dict[str, Any]]) -> str:
    rows = []
    for skill in skills:
        raw_name = _safe_str(skill.get("name"))
        name = html.escape(raw_name)
        category = html.escape(_safe_str(skill.get("category")))
        mastery_level = _safe_str(skill.get("mastery_level") or "未评估")
        detail_href = "/skills/detail?name=" + quote(raw_name, safe="")
        rows.append(
            f"""
            <article class="skill-card">
              <div class="skill-head">
                <div>
                  <h2>{name}</h2>
                  <div class="muted">{category or "未分类"}</div>
                </div>
                <div class="skill-score">{int(skill.get("mastery_score") or 0)}</div>
              </div>
              <div class="skill-metrics">
                <span>岗位出现 {int(skill.get("mention_count") or 0)} 次</span>
                <span>最高权重 {int(skill.get("max_importance") or 0)}</span>
                <span>关联岗位 {int(skill.get("job_count") or 0)} 个</span>
                <span>项目支撑 {int(skill.get("project_count") or 0)} 个</span>
              </div>
              <div class="skill-summary">
                <span class="level">{html.escape(mastery_level)}</span>
                <span>{html.escape(_safe_str(skill.get("notes")) or "还没有能力说明")}</span>
              </div>
              <div class="actions">
                <a class="primary" href="{detail_href}">查看详情</a>
              </div>
            </article>
            """
        )

    skill_cards = "\n".join(rows) or '<div class="empty">还没有技能点。先收藏几个岗位后，系统会从职位描述里提炼技能。</div>'
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>技能库</title>
  <style>
    {_layout_styles()}
    main {{ max-width: 1180px; margin: 0 auto; }}
    .toolbar {{ display: flex; justify-content: space-between; gap: 12px; margin-bottom: 14px; }}
    .toolbar input {{ width: min(420px, 100%); border: 1px solid #d1d5db; border-radius: 6px; padding: 8px; font: inherit; }}
    .skill-list {{ display: grid; grid-template-columns: repeat(2, minmax(280px, 1fr)); gap: 14px; }}
    .skill-card {{ background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; }}
    .skill-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }}
    .skill-head h2 {{ margin: 0; font-size: 18px; }}
    .skill-score {{ display: grid; place-items: center; min-width: 44px; height: 44px; border-radius: 50%; background: #ecfdf5; color: #047857; font-weight: 800; }}
    .muted {{ color: #667085; font-size: 13px; }}
    .skill-metrics {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }}
    .skill-metrics span {{ padding: 5px 8px; border-radius: 4px; background: #f3f6f8; color: #475467; font-size: 12px; }}
    .skill-summary {{ display: grid; gap: 8px; color: #475467; font-size: 13px; line-height: 1.5; }}
    .level {{ width: fit-content; padding: 5px 8px; border-radius: 4px; background: #e6f7f6; color: #007c78; font-weight: 700; }}
    .actions {{ display: flex; justify-content: flex-end; margin-top: 14px; }}
    .primary {{ display: inline-flex; align-items: center; min-height: 34px; padding: 0 12px; border-radius: 6px; background: #0f766e; color: #ffffff; }}
    .empty {{ padding: 32px; text-align: center; color: #667085; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; }}
    @media (max-width: 860px) {{ .skill-list {{ grid-template-columns: 1fr; }} .toolbar {{ display: block; }} }}
  </style>
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">Boss 职位助手</div>
      <nav class="side-nav">{_sidebar_nav("skills")}</nav>
    </aside>
    <div class="content">
      <header class="page-header"><h1>技能库</h1></header>
      <main>
        <section class="toolbar">
          <input id="skill-search" placeholder="搜索技能、分类、说明">
          <a href="/projects/page">管理项目经验</a>
        </section>
        <section class="skill-list">{skill_cards}</section>
      </main>
    </div>
  </div>
  <script>
    const searchInput = document.getElementById("skill-search");
    const cards = Array.from(document.querySelectorAll(".skill-card"));
    searchInput.addEventListener("input", () => {{
      const keyword = searchInput.value.trim().toLowerCase();
      cards.forEach((card) => {{
        card.style.display = !keyword || card.textContent.toLowerCase().includes(keyword) ? "" : "none";
      }});
    }});
  </script>
</body>
</html>"""


def _html_skill_detail_page(skill: dict[str, Any] | None) -> str:
    if not skill:
        return """<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>技能不存在</title></head>
<body><p>技能不存在。</p><p><a href="/skills/page">返回技能库</a></p></body>
</html>"""

    name = html.escape(_safe_str(skill.get("name")))
    raw_name = _safe_str(skill.get("name"))
    category = html.escape(_safe_str(skill.get("category")))
    mastery_level = _safe_str(skill.get("mastery_level") or "未评估")
    level_options = ["未评估", "了解", "熟悉", "熟练", "项目实战", "可面试输出"]
    options = "".join(
        f'<option value="{html.escape(level)}"{" selected" if level == mastery_level else ""}>{html.escape(level)}</option>'
        for level in level_options
    )
    job_items = []
    for job in skill.get("jobs", []):
        contexts = "".join(
            f"<li>{html.escape(_safe_str(context))}</li>" for context in job.get("contexts", [])[:3]
        )
        detail_href = "/jobs/detail?job_key=" + quote(_safe_str(job.get("job_key")), safe="")
        job_items.append(
            f"""
            <article class="related-card">
              <div class="related-head">
                <a href="{detail_href}">{html.escape(_safe_str(job.get("title")))}</a>
                <strong>{int(job.get("importance") or 0)}</strong>
              </div>
              <div class="muted">{html.escape(_safe_str(job.get("company")))} · {html.escape(_safe_str(job.get("salary")))} · {html.escape(_safe_str(job.get("location")))}</div>
              <ul>{contexts or "<li>暂无上下文</li>"}</ul>
            </article>
            """
        )
    project_items = []
    for project in skill.get("projects", []):
        project_items.append(
            f"""
            <article class="related-card">
              <div class="related-head">
                <strong>{html.escape(_safe_str(project.get("name")))}</strong>
                <span>{html.escape(_safe_str(project.get("period")))}</span>
              </div>
              <div class="muted">{html.escape(_safe_str(project.get("role")))}</div>
              <p>{html.escape(_safe_str(project.get("evidence")) or "已关联该技能，暂无证据说明。")}</p>
            </article>
            """
        )
    jobs_html = "\n".join(job_items) or '<div class="empty">还没有岗位上下文。</div>'
    projects_html = "\n".join(project_items) or '<div class="empty">还没有项目经验支撑。</div>'
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{name}</title>
  <style>
    {_layout_styles()}
    main {{ max-width: 1180px; margin: 0 auto; }}
    .detail-grid {{ display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 16px; align-items: start; }}
    .panel, .related-card, .empty {{ background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; }}
    .panel h2, .related h2 {{ margin: 0 0 12px; font-size: 18px; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin: 14px 0; }}
    .metric {{ padding: 12px; border-radius: 8px; background: #f8fafc; }}
    .metric strong {{ display: block; font-size: 22px; color: #111827; }}
    .muted {{ color: #667085; font-size: 13px; }}
    form {{ display: grid; gap: 10px; }}
    label {{ display: grid; gap: 5px; color: #475467; font-size: 12px; }}
    input, select, textarea {{ box-sizing: border-box; width: 100%; border: 1px solid #d1d5db; border-radius: 6px; padding: 8px; font: inherit; background: #ffffff; }}
    textarea {{ min-height: 86px; resize: vertical; }}
    button {{ border: 0; border-radius: 6px; padding: 9px 12px; color: #ffffff; background: #0f766e; cursor: pointer; font: inherit; }}
    .related {{ display: grid; gap: 16px; }}
    .related-list {{ display: grid; gap: 12px; }}
    .related-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; }}
    .related-head a, .related-head strong {{ color: #111827; font-weight: 700; }}
    .related-card ul {{ margin: 10px 0 0; padding-left: 20px; color: #374151; line-height: 1.6; }}
    .related-card p {{ color: #374151; line-height: 1.6; white-space: pre-wrap; }}
    .topbar {{ margin-bottom: 14px; }}
    #skill-status {{ color: #667085; font-size: 13px; }}
    @media (max-width: 900px) {{ .detail-grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">Boss 职位助手</div>
      <nav class="side-nav">{_sidebar_nav("skills")}</nav>
    </aside>
    <div class="content">
      <header class="page-header"><h1>{name}</h1></header>
      <main>
        <div class="topbar"><a href="/skills/page">返回技能库</a></div>
        <div class="detail-grid">
          <section class="panel">
            <h2>技能画像</h2>
            <div class="muted">{category or "未分类"}</div>
            <div class="metric-grid">
              <div class="metric"><strong>{int(skill.get("mention_count") or 0)}</strong>岗位出现</div>
              <div class="metric"><strong>{int(skill.get("max_importance") or 0)}</strong>最高权重</div>
              <div class="metric"><strong>{int(skill.get("job_count") or 0)}</strong>关联岗位</div>
              <div class="metric"><strong>{int(skill.get("project_count") or 0)}</strong>项目支撑</div>
            </div>
            <form id="skill-form">
              <input type="hidden" name="name" value="{name}">
              <input type="hidden" name="category" value="{category}">
              <label>掌握程度<select name="mastery_level">{options}</select></label>
              <label>掌握分<input name="mastery_score" type="number" min="0" max="100" value="{int(skill.get("mastery_score") or 0)}"></label>
              <label>能力说明<textarea name="notes">{html.escape(_safe_str(skill.get("notes")))}</textarea></label>
              <label>学习补充<textarea name="learning_notes">{html.escape(_safe_str(skill.get("learning_notes")))}</textarea></label>
              <button type="submit">保存技能画像</button>
              <span id="skill-status"></span>
            </form>
          </section>
          <section class="related">
            <div>
              <h2>关联岗位上下文</h2>
              <div class="related-list">{jobs_html}</div>
            </div>
            <div>
              <h2>项目经验支撑</h2>
              <div class="related-list">{projects_html}</div>
            </div>
          </section>
        </div>
      </main>
    </div>
  </div>
  <script>
    document.getElementById("skill-form").addEventListener("submit", async (event) => {{
      event.preventDefault();
      const status = document.getElementById("skill-status");
      const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
      status.textContent = "保存中...";
      try {{
        const response = await fetch("/skills/profile", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload),
        }});
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.error || "保存失败");
        status.textContent = "已保存";
      }} catch (error) {{
        status.textContent = "保存失败：" + (error && error.message ? error.message : String(error));
      }}
    }});
  </script>
</body>
</html>"""


def _html_projects_page(projects: list[dict[str, Any]], skills: list[dict[str, Any]]) -> str:
    skill_suggestions = "\n".join(
        f'<option value="{html.escape(_safe_str(skill.get("name")))}"></option>' for skill in skills
    )
    project_cards = []
    for project in projects:
        chips = "".join(
            f'<span>{html.escape(_safe_str(skill.get("skill_name")))}</span>'
            for skill in project.get("skills", [])
        )
        project_cards.append(
            f"""
            <article class="project-card">
              <div class="project-head">
                <h2>{html.escape(_safe_str(project.get("name")))}</h2>
                <span>{html.escape(_safe_str(project.get("period")))}</span>
              </div>
              <div class="muted">{html.escape(_safe_str(project.get("role")))}</div>
              <p>{html.escape(_safe_str(project.get("description")))}</p>
              <p class="outcome">{html.escape(_safe_str(project.get("outcome")))}</p>
              <div class="chips">{chips or "<span>未关联技能</span>"}</div>
            </article>
            """
        )
    projects_html = "\n".join(project_cards) or '<div class="empty">还没有项目经验。先添加一个能代表你能力的项目。</div>'
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>项目经验</title>
  <style>
    {_layout_styles()}
    main {{ max-width: 1180px; margin: 0 auto; }}
    .grid {{ display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 16px; align-items: start; }}
    .panel, .project-card, .empty {{ background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; }}
    .panel h2, .project-card h2 {{ margin: 0 0 12px; font-size: 18px; }}
    form {{ display: grid; gap: 10px; }}
    label {{ display: grid; gap: 5px; color: #475467; font-size: 12px; }}
    input, textarea {{ box-sizing: border-box; width: 100%; border: 1px solid #d1d5db; border-radius: 6px; padding: 8px; font: inherit; }}
    textarea {{ min-height: 86px; resize: vertical; }}
    button {{ border: 0; border-radius: 6px; padding: 9px 12px; color: #ffffff; background: #0f766e; cursor: pointer; font: inherit; }}
    .project-list {{ display: grid; gap: 14px; }}
    .project-head {{ display: flex; justify-content: space-between; gap: 12px; }}
    .project-head span, .muted {{ color: #667085; font-size: 13px; }}
    .project-card p {{ color: #374151; line-height: 1.6; white-space: pre-wrap; }}
    .outcome {{ border-top: 1px solid #eef1f4; padding-top: 10px; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .chips span {{ padding: 5px 8px; border-radius: 4px; background: #f3f6f8; color: #475467; font-size: 12px; }}
    #project-status {{ color: #667085; font-size: 13px; }}
    .empty {{ color: #667085; text-align: center; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">Boss 职位助手</div>
      <nav class="side-nav">{_sidebar_nav("projects")}</nav>
    </aside>
    <div class="content">
      <header class="page-header"><h1>项目经验</h1></header>
      <main>
        <div class="grid">
          <section class="panel">
            <h2>新增项目</h2>
            <form id="project-form">
              <label>项目名称<input name="name" required></label>
              <label>你的角色<input name="role" placeholder="例如：核心后端开发"></label>
              <label>项目周期<input name="period" placeholder="例如：2024.03-2025.01"></label>
              <label>项目描述<textarea name="description" placeholder="背景、职责、核心模块"></textarea></label>
              <label>结果和亮点<textarea name="outcome" placeholder="性能提升、业务结果、复杂问题处理"></textarea></label>
              <label>关联技能点<textarea name="skills" list="skill-options" placeholder="每行或逗号分隔：Java, Redis, 高并发"></textarea></label>
              <datalist id="skill-options">{skill_suggestions}</datalist>
              <button type="submit">保存项目</button>
              <span id="project-status"></span>
            </form>
          </section>
          <section class="project-list">{projects_html}</section>
        </div>
      </main>
    </div>
  </div>
  <script>
    document.getElementById("project-form").addEventListener("submit", async (event) => {{
      event.preventDefault();
      const status = document.getElementById("project-status");
      const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
      status.textContent = "保存中...";
      try {{
        const response = await fetch("/projects", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload),
        }});
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.error || "保存失败");
        status.textContent = "已保存，正在刷新...";
        location.reload();
      }} catch (error) {{
        status.textContent = "保存失败：" + (error && error.message ? error.message : String(error));
      }}
    }});
  </script>
</body>
</html>"""


def _skill_datalist(skills: list[dict[str, Any]]) -> str:
    return "\n".join(
        f'<option value="{html.escape(_safe_str(skill.get("name")))}"></option>' for skill in skills
    )


def _tracking_status_options(selected: str = "面试中") -> str:
    statuses = ["未投递", "已投递", "面试中", "已面试", "已淘汰", "已 offer"]
    return "".join(
        f'<option value="{html.escape(status)}"{" selected" if status == selected else ""}>{html.escape(status)}</option>'
        for status in statuses
    )


def _select_options(options: list[str], selected: str = "") -> str:
    return "".join(
        f'<option value="{html.escape(option)}"{" selected" if option == selected else ""}>{html.escape(option)}</option>'
        for option in options
    )


def _html_interview_form(
    form_id: str,
    skills: list[dict[str, Any]],
    jobs: list[dict[str, Any]] | None = None,
    job: dict[str, Any] | None = None,
) -> str:
    selected_key = _safe_str(job.get("job_key")) if job else ""
    if job:
        job_fields = f"""
          <input type="hidden" name="job_key" value="{html.escape(selected_key)}">
          <input type="hidden" name="company" value="{html.escape(_safe_str(job.get("company")))}">
          <input type="hidden" name="title" value="{html.escape(_safe_str(job.get("title")))}">
          <div class="form-hint">{html.escape(_safe_str(job.get("company")))} · {html.escape(_safe_str(job.get("title")))}</div>
        """
    else:
        options = ['<option value="">不关联岗位</option>']
        for item in jobs or []:
            key = _safe_str(item.get("job_key"))
            label = f"{_safe_str(item.get('company'))} · {_safe_str(item.get('title'))}"
            options.append(
                f'<option value="{html.escape(key)}"{" selected" if key == selected_key else ""}>'
                f"{html.escape(label)}</option>"
            )
        job_fields = f"""
          <label>关联岗位<select name="job_key">{"".join(options)}</select></label>
          <label>公司<input name="company" placeholder="不关联岗位时可手动填写"></label>
          <label>岗位<input name="title" placeholder="不关联岗位时可手动填写"></label>
        """

    return f"""
      <form id="{form_id}" class="interview-form">
        {job_fields}
        <div class="form-grid">
          <label>面试轮次
            <select name="round_name">
              {_select_options(["一面", "二面", "三面", "技术面", "技术终面", "HR 面", "主管面", "交叉面", "复盘"])}
            </select>
          </label>
          <label>面试时间<input name="interview_time" type="datetime-local"></label>
          <label>面试形式
            <select name="interview_type">
              {_select_options(["视频", "电话", "现场", "在线笔试", "线下笔试", "HR 沟通", "其他"])}
            </select>
          </label>
          <label>面试结果
            <select name="result">
              {_select_options(["待反馈", "通过", "未通过", "已淘汰", "Offer", "待定", "放弃"])}
            </select>
          </label>
          <label>整体表现分<input name="performance_score" type="number" min="0" max="100" value="60"></label>
          <label>同步岗位状态<select name="tracking_status">{_tracking_status_options()}</select></label>
        </div>
        <label>面试复盘<textarea name="summary" placeholder="整体表现、卡住的问题、后续准备方向"></textarea></label>
        <div class="question-editor">
          <div class="question-toolbar">
            <strong>面试问题</strong>
            <button class="secondary add-question" type="button">新增问题</button>
          </div>
          <div class="question-list">
            <div class="question-row">
              <label>问题<textarea data-field="question" placeholder="例如：Spring 事务失效有哪些场景？"></textarea></label>
              <label>关联技能点<input data-field="skills" list="interview-skill-options" placeholder="Java, Spring, MySQL"></label>
              <label>回答表现分<input data-field="performance_score" type="number" min="0" max="100" value="60"></label>
              <label>回答复盘<textarea data-field="answer_summary" placeholder="哪里答得好，哪里需要补"></textarea></label>
            </div>
          </div>
        </div>
        <datalist id="interview-skill-options">{_skill_datalist(skills)}</datalist>
        <div class="form-actions">
          <button type="submit">保存面试记录</button>
          <span class="form-status"></span>
        </div>
      </form>
      <script>
        (() => {{
          const form = document.getElementById("{form_id}");
          const list = form.querySelector(".question-list");
          const status = form.querySelector(".form-status");
          form.querySelector(".add-question").addEventListener("click", () => {{
            const row = list.querySelector(".question-row").cloneNode(true);
            row.querySelectorAll("input, textarea").forEach((input) => {{
              if (input.dataset.field === "performance_score") input.value = "60";
              else input.value = "";
            }});
            list.appendChild(row);
          }});
          form.addEventListener("submit", async (event) => {{
            event.preventDefault();
            const payload = Object.fromEntries(new FormData(form).entries());
            payload.questions = Array.from(form.querySelectorAll(".question-row")).map((row) => ({{
              question: row.querySelector('[data-field="question"]').value,
              skills: row.querySelector('[data-field="skills"]').value,
              performance_score: row.querySelector('[data-field="performance_score"]').value,
              answer_summary: row.querySelector('[data-field="answer_summary"]').value,
            }})).filter((item) => item.question.trim());
            status.textContent = "保存中...";
            try {{
              const response = await fetch("/interviews", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify(payload),
              }});
              const result = await response.json();
              if (!response.ok || !result.ok) throw new Error(result.error || "保存失败");
              status.textContent = "已保存，正在刷新...";
              location.reload();
            }} catch (error) {{
              status.textContent = "保存失败：" + (error && error.message ? error.message : String(error));
            }}
          }});
        }})();
      </script>
    """


def _html_interview_cards(interviews: list[dict[str, Any]]) -> str:
    cards = []
    for interview in interviews:
        detail = " · ".join(
            item
            for item in [
                _safe_str(interview.get("company")),
                _safe_str(interview.get("title")),
                _safe_str(interview.get("round_name")),
                _safe_str(interview.get("interview_time")),
            ]
            if item
        )
        question_items = [
            item.strip()
            for item in _safe_str(interview.get("question_texts")).split(",")
            if item.strip()
        ][:3]
        skill_items = [
            item.strip()
            for item in _safe_str(interview.get("skill_names")).split(",")
            if item.strip()
        ][:6]
        questions_html = "".join(
            f"<li>{html.escape(question)}</li>" for question in question_items
        )
        skills_html = "".join(
            f"<span>{html.escape(skill)}</span>" for skill in skill_items
        )
        cards.append(
            f"""
            <article class="interview-card">
              <div class="interview-head">
                <div>
                  <h2>{html.escape(detail or "未命名面试")}</h2>
                  <div class="muted">{html.escape(_safe_str(interview.get("interview_type")))} · {html.escape(_safe_str(interview.get("result")) or "待记录结果")}</div>
                </div>
                <div class="interview-score">{int(interview.get("performance_score") or 0)}</div>
              </div>
              <p>{html.escape(_safe_str(interview.get("summary")) or "还没有填写复盘。")}</p>
              <ul class="interview-questions">{questions_html or "<li>还没有记录面试问题。</li>"}</ul>
              <div class="interview-meta">
                <span>问题 {int(interview.get("question_count") or 0)}</span>
                <span>技能 {int(interview.get("skill_count") or 0)}</span>
                {skills_html}
              </div>
            </article>
            """
        )
    return "\n".join(cards) or '<div class="empty">还没有面试记录。可以从岗位详情或本页新增。</div>'


def _html_interviews_page(
    interviews: list[dict[str, Any]],
    stats: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    skills: list[dict[str, Any]],
) -> str:
    stat_rows = []
    for item in stats[:12]:
        average = item.get("average_score")
        stat_rows.append(
            f"""
            <tr>
              <td>{html.escape(_safe_str(item.get("skill_name")))}</td>
              <td>{int(item.get("asked_count") or 0)}</td>
              <td>{int(item.get("weak_count") or 0)}</td>
              <td>{html.escape(_safe_str(average if average is not None else 0))}</td>
            </tr>
            """
        )
    stats_html = "\n".join(stat_rows) or '<tr><td colspan="4">还没有可统计的面试技能数据。</td></tr>'
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>面试记录</title>
  <style>
    {_layout_styles()}
    main {{ max-width: 1180px; margin: 0 auto; }}
    .grid {{ display: grid; grid-template-columns: 420px minmax(0, 1fr); gap: 16px; align-items: start; }}
    .panel, .interview-card, .empty {{ background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; }}
    .panel h2, .interview-card h2 {{ margin: 0 0 8px; font-size: 18px; }}
    .form-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
    label {{ display: grid; gap: 5px; color: #475467; font-size: 12px; }}
    input, select, textarea {{ box-sizing: border-box; width: 100%; border: 1px solid #d1d5db; border-radius: 6px; padding: 8px; font: inherit; background: #ffffff; }}
    textarea {{ min-height: 70px; resize: vertical; }}
    button {{ border: 0; border-radius: 6px; padding: 9px 12px; color: #ffffff; background: #0f766e; cursor: pointer; font: inherit; }}
    button.secondary {{ color: #0f766e; background: #e6f7f6; }}
    .interview-form {{ display: grid; gap: 10px; }}
    .question-editor {{ display: grid; gap: 10px; }}
    .question-toolbar, .form-actions, .interview-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; }}
    .question-list {{ display: grid; gap: 10px; }}
    .question-row {{ display: grid; gap: 8px; padding: 10px; border: 1px solid #eef1f4; border-radius: 8px; background: #fbfcfd; }}
    .interview-list {{ display: grid; gap: 14px; }}
    .interview-score {{ display: grid; place-items: center; min-width: 44px; height: 44px; border-radius: 50%; background: #ecfdf5; color: #047857; font-weight: 800; }}
    .interview-card p {{ color: #374151; line-height: 1.6; white-space: pre-wrap; }}
    .interview-questions {{ margin: 0 0 10px; padding-left: 20px; color: #374151; line-height: 1.6; }}
    .interview-meta {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .interview-meta span {{ padding: 5px 8px; border-radius: 4px; background: #f3f6f8; color: #475467; font-size: 12px; }}
    .stats {{ width: 100%; border-collapse: collapse; margin-bottom: 14px; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; }}
    .stats th, .stats td {{ padding: 10px; border-bottom: 1px solid #eef1f4; text-align: left; }}
    .stats th {{ color: #667085; background: #f8fafc; font-size: 13px; }}
    .muted, .form-status, .form-hint {{ color: #667085; font-size: 13px; }}
    @media (max-width: 980px) {{ .grid, .form-grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">Boss 岗位助手</div>
      <nav class="side-nav">{_sidebar_nav("interviews")}</nav>
    </aside>
    <div class="content">
      <header class="page-header"><h1>面试记录</h1></header>
      <main>
        <div class="grid">
          <section class="panel">
            <h2>新增面试记录</h2>
            {_html_interview_form("interview-page-form", skills, jobs=jobs)}
          </section>
          <section>
            <table class="stats">
              <thead><tr><th>技能点</th><th>被问次数</th><th>低分次数</th><th>平均表现</th></tr></thead>
              <tbody>{stats_html}</tbody>
            </table>
            <div class="interview-list">{_html_interview_cards(interviews)}</div>
          </section>
        </div>
      </main>
    </div>
  </div>
</body>
</html>"""


def _html_job_detail_page(
    job: dict[str, Any] | None,
    config: dict[str, Any] | None = None,
    interviews: list[dict[str, Any]] | None = None,
    skills: list[dict[str, Any]] | None = None,
) -> str:
    if not job:
        return """<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>岗位不存在</title></head>
<body><p>岗位不存在或已经取消收藏。</p><p><a href="/">返回职位库</a></p></body>
</html>"""

    title = html.escape(job.get("title") or "未命名岗位")
    company = html.escape(job.get("company") or "")
    url = html.escape(_source_url(job) or "#")
    source_label = html.escape(_source_label(job.get("source")))
    chips = "".join(f"<span>{html.escape(chip)}</span>" for chip in _keyword_chips(job))
    sections = []
    for section_title, section_body in _description_sections(job.get("description") or "暂无职位描述"):
        tag_section = _looks_like_tag_section(section_title, section_body)
        body_html = (
            _render_description_tags(section_body)
            if tag_section
            else _render_description_body(section_body)
        )
        section_class = "description-section tag-section" if tag_section else "description-section"
        sections.append(
            f"""
            <section class="{section_class}">
              <h3>{html.escape(section_title)}</h3>
              <div class="description-body">{body_html}</div>
            </section>
            """
        )
    description_sections = "\n".join(sections)
    match_chart = _render_match_chart(_match_items(job, config or {}))
    reasons = html.escape("；".join(job.get("matched_reasons") or []))
    exclusion_reason = html.escape(job.get("exclusion_reason") or "")
    interview_list = _html_interview_cards(interviews or [])
    interview_form = _html_interview_form("job-detail-interview-form", skills or [], job=job)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    {_layout_styles()}
    main {{ max-width: 920px; margin: 0 auto; }}
    .job-card {{ background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 26px; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05); }}
    .topbar {{ margin-bottom: 16px; }}
    .title-row {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }}
    h1 {{ margin: 0; font-size: 24px; line-height: 1.25; }}
    .salary {{ color: #ff4d4f; font-size: 22px; font-weight: 700; white-space: nowrap; }}
    .muted {{ color: #6b7280; font-size: 13px; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 14px; margin: 14px 0 0; color: #5f6368; font-size: 14px; }}
    .meta span {{ display: inline-flex; align-items: center; gap: 4px; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 20px 0 24px; }}
    .chips span {{ padding: 7px 12px; border-radius: 4px; background: #f5f7f9; color: #374151; font-size: 13px; }}
    .score {{ margin-bottom: 22px; padding: 12px 14px; background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 8px; line-height: 1.6; }}
    .match-analysis {{ margin: 0 0 24px; padding: 18px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fbfcfd; }}
    .match-analysis h2 {{ margin: 0 0 14px; font-size: 18px; }}
    .match-grid {{ display: grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap: 12px; }}
    .match-item {{ padding: 12px; border: 1px solid #e5e7eb; border-radius: 8px; background: #ffffff; }}
    .match-head {{ display: flex; justify-content: space-between; gap: 8px; font-size: 14px; }}
    .match-head strong {{ color: #667085; }}
    .match-bar {{ height: 8px; margin: 9px 0; overflow: hidden; border-radius: 999px; background: #eef2f6; }}
    .match-bar span {{ display: block; height: 100%; border-radius: inherit; background: #00b8b0; }}
    .miss .match-bar span {{ background: #f59e0b; }}
    .risk .match-bar span {{ background: #f43f5e; }}
    .pending .match-bar span {{ background: #94a3b8; }}
    .match-detail {{ color: #667085; font-size: 13px; line-height: 1.45; }}
    .description {{ border-top: 1px solid #eef1f4; padding-top: 22px; }}
    .description h2 {{ margin: 0 0 18px; font-size: 20px; }}
    .description-section {{ margin: 0 0 24px; padding: 0 0 0 16px; border-left: 3px solid #00b8b0; }}
    .description-section h3 {{ margin: 0 0 12px; font-size: 17px; font-weight: 700; color: #111827; }}
    .tag-section {{ padding-left: 0; border-left: 0; }}
    .description-body {{ color: #2f3437; font-size: 15px; line-height: 1.85; }}
    .description-body p {{ margin: 0 0 10px; white-space: pre-wrap; word-break: break-word; }}
    .description-tags {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 2px 0 18px; }}
    .description-tags span {{ display: inline-flex; align-items: center; min-height: 30px; padding: 0 12px; border-radius: 4px; background: #f3f6f8; color: #344054; font-size: 14px; line-height: 1; }}
    .description-list {{ margin: 0 0 10px 0; padding-left: 22px; }}
    .description-list li {{ margin: 0 0 8px; padding-left: 4px; word-break: break-word; }}
    .description-list li::marker {{ color: #00a19a; font-weight: 700; }}
    .interview-panel {{ margin-top: 24px; padding-top: 22px; border-top: 1px solid #eef1f4; }}
    .interview-panel h2 {{ margin: 0 0 14px; font-size: 20px; }}
    .interview-form {{ display: grid; gap: 10px; margin-bottom: 18px; padding: 16px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fbfcfd; }}
    .form-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
    .interview-form label {{ display: grid; gap: 5px; color: #475467; font-size: 12px; }}
    .interview-form input, .interview-form select, .interview-form textarea {{ box-sizing: border-box; width: 100%; border: 1px solid #d1d5db; border-radius: 6px; padding: 8px; font: inherit; background: #ffffff; }}
    .interview-form textarea {{ min-height: 70px; resize: vertical; }}
    .question-toolbar, .form-actions, .interview-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; }}
    .question-list {{ display: grid; gap: 10px; }}
    .question-row {{ display: grid; gap: 8px; padding: 10px; border: 1px solid #eef1f4; border-radius: 8px; background: #ffffff; }}
    button {{ border: 0; border-radius: 6px; padding: 9px 12px; color: #ffffff; background: #0f766e; cursor: pointer; font: inherit; }}
    button.secondary {{ color: #0f766e; background: #e6f7f6; }}
    .interview-list {{ display: grid; gap: 12px; }}
    .interview-card, .empty {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px; background: #ffffff; }}
    .interview-card h2 {{ margin: 0 0 6px; font-size: 16px; }}
    .interview-card p {{ color: #374151; line-height: 1.6; white-space: pre-wrap; }}
    .interview-questions {{ margin: 0 0 10px; padding-left: 20px; color: #374151; line-height: 1.6; }}
    .interview-score {{ display: grid; place-items: center; min-width: 42px; height: 42px; border-radius: 50%; background: #ecfdf5; color: #047857; font-weight: 800; }}
    .interview-meta {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .interview-meta span {{ padding: 5px 8px; border-radius: 4px; background: #f3f6f8; color: #475467; font-size: 12px; }}
    .form-status, .form-hint {{ color: #667085; font-size: 13px; }}
    .actions {{ display: flex; justify-content: space-between; align-items: center; margin-top: 24px; padding-top: 18px; border-top: 1px solid #e5e7eb; }}
    .primary {{ padding: 8px 14px; border-radius: 6px; background: #00b8b0; color: #ffffff; }}
    @media (max-width: 720px) {{
      .job-card {{ padding: 18px; }}
      .title-row {{ display: block; }}
      .match-grid {{ grid-template-columns: 1fr; }}
      .form-grid {{ grid-template-columns: 1fr; }}
      .salary {{ margin-top: 10px; }}
      .actions {{ align-items: stretch; flex-direction: column; gap: 12px; }}
      .primary {{ text-align: center; }}
    }}
  </style>
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">Boss 职位助手</div>
      <nav class="side-nav">{_sidebar_nav("jobs")}</nav>
    </aside>
    <div class="content">
      <header class="page-header"><h1>岗位详情</h1></header>
      <main>
    <section class="job-card">
      <div class="topbar"><a href="/jobs/page">返回岗位列表</a></div>
      <div class="title-row">
        <div>
          <h1>{title}</h1>
          <div class="muted">{company}</div>
        </div>
        <div class="salary">{html.escape(job.get("salary") or "")}</div>
      </div>
      <div class="meta">
        <span>地点：{html.escape(job.get("location") or "")}</span>
        <span>经验：{html.escape(job.get("experience") or "")}</span>
        <span>学历：{html.escape(job.get("education") or "")}</span>
        <span>规模：{html.escape(job.get("company_size") or "")}</span>
        <span>状态：{html.escape(job.get("tracking_status") or "")}</span>
      </div>
      <div class="chips">{chips}</div>
      <section class="match-analysis">
        <h2>匹配分析</h2>
        <div class="match-grid">{match_chart}</div>
      </section>
      <section class="description">
        <h2>职位描述</h2>
        {description_sections}
      </section>
      <section class="score">
        <strong>匹配度：{int(job.get("score") or 0)}</strong>
        <div class="muted">{reasons or exclusion_reason}</div>
      </section>
      <section class="interview-panel">
        <h2>面试记录</h2>
        {interview_form}
        <div class="interview-list">{interview_list}</div>
      </section>
      <div class="actions">
        <a href="/jobs/page">返回岗位列表</a>
        <a class="primary" href="{url}" target="_blank" rel="noreferrer">打开 {source_label} 原岗位</a>
      </div>
    </section>
      </main>
    </div>
  </div>
</body>
</html>"""


class LocalServiceHandler(BaseHTTPRequestHandler):
    config_path = "config.yaml"

    def _set_headers(self, status_code: int = 200, content_type: str = "application/json; charset=utf-8") -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        origin = self.headers.get("Origin")
        if origin and _allowed_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _write_json(self, data: dict[str, Any], status_code: int = 200) -> None:
        self._set_headers(status_code)
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _write_html(self, data: str, status_code: int = 200) -> None:
        self._set_headers(status_code, "text/html; charset=utf-8")
        self.wfile.write(data.encode("utf-8"))

    def _read_json_payload(self) -> dict[str, Any]:
        content_length_text = self.headers.get("Content-Length", "0") or "0"
        try:
            content_length = int(content_length_text)
        except ValueError as exc:
            raise ClientInputError("请求头 Content-Length 不合法") from exc

        if content_length < 0 or content_length > MAX_BODY_BYTES:
            raise ClientInputError("请求体过大")

        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ClientInputError("请求 JSON 格式不合法") from exc

        if not isinstance(payload, dict):
            raise ClientInputError("请求 JSON 必须是对象")

        return payload

    def _load_config(self) -> dict[str, Any]:
        config = load_config(self.config_path)
        init_db(get_db_path(config))
        return config

    def do_OPTIONS(self) -> None:
        self._set_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._write_json({"ok": True, "service": "job-search-assistant"})
            return

        try:
            config = self._load_config()
            db_path = get_db_path(config)
            if parsed.path == "/jobs":
                query = parse_qs(parsed.query)
                include_unfavorited = query.get("include_unfavorited", ["0"])[0] == "1"
                self._write_json({"ok": True, "jobs": list_saved_jobs(db_path, include_unfavorited)})
                return

            if parsed.path == "/jobs/page":
                self._write_html(_html_jobs_page(list_saved_jobs(db_path), config))
                return

            if parsed.path == "/settings/page":
                self._write_html(_html_settings_page(config))
                return

            if parsed.path == "/skills/page":
                self._write_html(_html_skills_page(list_skills(db_path)))
                return

            if parsed.path == "/skills/detail":
                query = parse_qs(parsed.query)
                name = query.get("name", [""])[0]
                skill = get_skill_detail(db_path, name) if name else None
                self._write_html(_html_skill_detail_page(skill), 200 if skill else 404)
                return

            if parsed.path == "/skills":
                self._write_json({"ok": True, "skills": list_skills(db_path)})
                return

            if parsed.path == "/projects/page":
                self._write_html(_html_projects_page(list_projects(db_path), list_skills(db_path)))
                return

            if parsed.path == "/projects":
                self._write_json({"ok": True, "projects": list_projects(db_path)})
                return

            if parsed.path == "/interviews/page":
                self._write_html(
                    _html_interviews_page(
                        list_interviews(db_path),
                        interview_skill_stats(db_path),
                        list_saved_jobs(db_path),
                        list_skills(db_path),
                    )
                )
                return

            if parsed.path == "/interviews":
                self._write_json(
                    {
                        "ok": True,
                        "interviews": list_interviews(db_path),
                        "skill_stats": interview_skill_stats(db_path),
                    }
                )
                return

            if parsed.path == "/settings":
                self._write_json({"ok": True, "settings": settings_from_config(config)})
                return

            if parsed.path == "/jobs/detail":
                query = parse_qs(parsed.query)
                key = query.get("job_key", [""])[0]
                job = get_saved_job(db_path, key) if key else None
                self._write_html(
                    _html_job_detail_page(
                        job,
                        config,
                        list_interviews(db_path, key) if key else [],
                        list_skills(db_path),
                    ),
                    200 if job else 404,
                )
                return

            if parsed.path == "/":
                self._write_html(_html_dashboard_page(list_saved_jobs(db_path)))
                return
        except Exception as exc:  # noqa: BLE001
            print(f"本地服务处理 GET 失败: {exc}")
            traceback.print_exc()
            self._write_json({"ok": False, "error": "本地服务处理失败"}, 500)
            return

        self._write_json({"ok": False, "error": "Not Found"}, 404)

    def do_POST(self) -> None:
        try:
            payload = self._read_json_payload()
            config = self._load_config()
            db_path = get_db_path(config)

            if self.path == "/settings":
                response = update_settings_response(payload, self.config_path)
                self._write_json(response, 200)
                return

            if self.path == "/skills/profile":
                try:
                    mastery_score = int(payload.get("mastery_score") or 0)
                except (TypeError, ValueError) as exc:
                    raise ClientInputError("掌握分必须是数字") from exc
                response = update_skill_profile(
                    db_path,
                    _safe_str(payload.get("name")),
                    _safe_str(payload.get("mastery_level") or "未评估"),
                    mastery_score,
                    _safe_str(payload.get("notes")),
                    _safe_str(payload.get("learning_notes")),
                    _safe_str(payload.get("category")),
                )
                self._write_json({"ok": True, "skill": response})
                return

            if self.path == "/projects":
                if not _safe_str(payload.get("name")).strip():
                    raise ClientInputError("项目名称不能为空")
                response = create_project(db_path, payload)
                self._write_json({"ok": True, "project": response})
                return

            if self.path == "/interviews":
                if not _safe_str(payload.get("company")).strip() and not _safe_str(payload.get("job_key")).strip():
                    raise ClientInputError("面试记录需要关联岗位或填写公司")
                response = create_interview(db_path, payload)
                self._write_json({"ok": True, "interview": response})
                return

            if self.path == "/jobs/save":
                response = save_job_response(payload, config)
                self._write_json(response, 200 if response.get("ok") else 400)
                return

            if self.path == "/jobs/unsave":
                key = _request_job_key(payload)
                if not key:
                    raise ClientInputError("缺少 job_key 或 url")
                self._write_json({"ok": unsave_job(db_path, key), "job_key": key})
                return

            if self.path == "/jobs/status":
                key = _request_job_key(payload)
                status = _safe_str(payload.get("tracking_status") or payload.get("status"))
                notes = payload.get("notes")
                if not key or not status:
                    raise ClientInputError("缺少 job_key/status")
                job = update_tracking(db_path, key, status, _safe_str(notes) if notes is not None else None)
                self._write_json({"ok": bool(job), "job": job})
                return

            self._write_json({"ok": False, "error": "Not Found"}, 404)
        except ClientInputError as exc:
            self._write_json({"ok": False, "error": str(exc)}, 400)
        except Exception as exc:  # noqa: BLE001 - local service should report JSON errors.
            print(f"本地服务处理 POST 失败: {exc}")
            traceback.print_exc()
            self._write_json({"ok": False, "error": "本地服务处理失败"}, 500)


def run_server(config_path: str = "config.yaml", host: str = HOST, port: int = PORT) -> None:
    if not _is_loopback_host(host):
        raise ValueError("本地服务只能绑定 127.0.0.1、localhost 或 loopback 地址")

    LocalServiceHandler.config_path = config_path
    config = load_config(config_path)
    init_db(get_db_path(config))
    server = ThreadingHTTPServer((host, port), LocalServiceHandler)
    print(f"求职助手本地服务已启动: http://{host}:{port}")
    print("插件接口: GET /health, GET /jobs, POST /jobs/save, POST /jobs/unsave")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
