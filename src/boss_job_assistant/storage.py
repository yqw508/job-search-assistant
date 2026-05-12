import hashlib
import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from boss_job_assistant.models import JobPosting, ScoredJob


JOB_COLUMNS = (
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


SCHEMA_COMMENTS: tuple[tuple[str, str, str, str], ...] = (
    ("column", "saved_jobs", "source", "招聘来源标识，例如 boss、liepin、lagou、manual。"),
    ("column", "saved_jobs", "source_job_id", "来源站点内的稳定岗位标识；Boss 当前使用标准化后的岗位详情 URL。"),
    ("column", "saved_jobs", "source_url", "来源站点原始岗位链接，用于回跳原页面和排查采集差异。"),
    ("table", "saved_jobs", "", "收藏岗位主表，保存从 Boss 页面采集并评分后的岗位信息和跟进状态。"),
    ("column", "saved_jobs", "job_key", "岗位唯一键，优先使用岗位 URL，没有 URL 时使用岗位核心信息生成。"),
    ("column", "saved_jobs", "title", "岗位名称。"),
    ("column", "saved_jobs", "salary", "薪资范围原始文本，例如 12-24K。"),
    ("column", "saved_jobs", "location", "工作地点原始文本。"),
    ("column", "saved_jobs", "experience", "经验要求。"),
    ("column", "saved_jobs", "education", "学历要求。"),
    ("column", "saved_jobs", "company", "公司名称。"),
    ("column", "saved_jobs", "industry", "所属行业。"),
    ("column", "saved_jobs", "financing", "融资阶段。"),
    ("column", "saved_jobs", "company_size", "公司规模。"),
    ("column", "saved_jobs", "url", "岗位详情页地址。"),
    ("column", "saved_jobs", "description", "岗位描述正文，已尽量剔除竞争力分析等无关区域。"),
    ("column", "saved_jobs", "matched", "是否符合当前匹配配置，1 表示符合，0 表示不符合。"),
    ("column", "saved_jobs", "score", "岗位匹配分数，分数越高越适合。"),
    ("column", "saved_jobs", "matched_reasons", "匹配命中的原因列表，JSON 数组。"),
    ("column", "saved_jobs", "exclusion_reason", "不符合条件时的主要原因。"),
    ("column", "saved_jobs", "tracking_status", "求职跟进状态，例如未投递、已投递、面试中等。"),
    ("column", "saved_jobs", "notes", "用户维护的岗位备注。"),
    ("column", "saved_jobs", "is_favorite", "是否仍在收藏列表中，1 表示收藏，0 表示取消收藏。"),
    ("column", "saved_jobs", "created_at", "首次入库时间，UTC ISO 格式。"),
    ("column", "saved_jobs", "updated_at", "最近更新时间，UTC ISO 格式。"),
    ("column", "saved_jobs", "last_seen_at", "最近一次在 Boss 页面采集到该岗位的时间。"),
    ("column", "saved_jobs", "unfavorited_at", "取消收藏时间，未取消时为空字符串。"),
    ("table", "skills", "", "技能库主表，维护从岗位描述提炼出的技能点及个人掌握情况。"),
    ("column", "skills", "name", "技能点名称，作为技能唯一标识。"),
    ("column", "skills", "category", "技能分类，例如后端、架构、数据库、业务领域等。"),
    ("column", "skills", "mastery_level", "个人掌握程度文本描述。"),
    ("column", "skills", "mastery_score", "个人掌握程度分数，0 到 100。"),
    ("column", "skills", "notes", "技能掌握情况备注。"),
    ("column", "skills", "learning_notes", "学习渠道、学习计划或资料备注。"),
    ("column", "skills", "created_at", "技能首次创建时间，UTC ISO 格式。"),
    ("column", "skills", "updated_at", "技能最近更新时间，UTC ISO 格式。"),
    ("table", "job_skill_mentions", "", "岗位与技能点的关联表，记录某个岗位描述中提到的技能及上下文。"),
    ("column", "job_skill_mentions", "job_key", "关联的岗位唯一键，对应 saved_jobs.job_key。"),
    ("column", "job_skill_mentions", "skill_name", "关联的技能名称，对应 skills.name。"),
    ("column", "job_skill_mentions", "mention_count", "技能在该岗位描述中被提到的次数。"),
    ("column", "job_skill_mentions", "contexts", "技能出现的上下文片段，JSON 数组。"),
    ("column", "job_skill_mentions", "importance", "技能在该岗位中的重要程度，数值越高越重要。"),
    ("column", "job_skill_mentions", "created_at", "关联记录创建时间，UTC ISO 格式。"),
    ("column", "job_skill_mentions", "updated_at", "关联记录更新时间，UTC ISO 格式。"),
    ("table", "projects", "", "项目经验表，用于维护个人项目经历及其对技能点的支撑。"),
    ("column", "projects", "project_id", "项目自增主键。"),
    ("column", "projects", "name", "项目名称。"),
    ("column", "projects", "role", "项目中的角色或职责。"),
    ("column", "projects", "period", "项目周期。"),
    ("column", "projects", "description", "项目背景、核心工作和技术方案描述。"),
    ("column", "projects", "outcome", "项目结果、业务收益或可量化产出。"),
    ("column", "projects", "created_at", "项目记录创建时间，UTC ISO 格式。"),
    ("column", "projects", "updated_at", "项目记录更新时间，UTC ISO 格式。"),
    ("table", "project_skill_links", "", "项目与技能点的关联表，记录项目如何证明某项技能。"),
    ("column", "project_skill_links", "project_id", "关联的项目 ID，对应 projects.project_id。"),
    ("column", "project_skill_links", "skill_name", "关联的技能名称，对应 skills.name。"),
    ("column", "project_skill_links", "evidence", "项目中体现该技能的证据或说明。"),
    ("column", "project_skill_links", "created_at", "关联记录创建时间，UTC ISO 格式。"),
    ("column", "project_skill_links", "updated_at", "关联记录更新时间，UTC ISO 格式。"),
    ("table", "interviews", "", "面试记录主表，记录每次面试的岗位、轮次、结果和整体表现。"),
    ("column", "interviews", "interview_id", "面试记录自增主键。"),
    ("column", "interviews", "job_key", "关联的岗位唯一键，对应 saved_jobs.job_key；非岗位来源时可为空。"),
    ("column", "interviews", "company", "面试公司名称。"),
    ("column", "interviews", "title", "面试岗位名称。"),
    ("column", "interviews", "round_name", "面试轮次，例如一面、二面、HR 面。"),
    ("column", "interviews", "interview_time", "面试时间，用户输入的本地时间文本。"),
    ("column", "interviews", "interview_type", "面试形式，例如电话、视频、现场。"),
    ("column", "interviews", "result", "面试结果，例如待反馈、通过、淘汰、Offer。"),
    ("column", "interviews", "performance_score", "本轮整体表现分数，0 到 100。"),
    ("column", "interviews", "summary", "本轮面试复盘摘要。"),
    ("column", "interviews", "created_at", "面试记录创建时间，UTC ISO 格式。"),
    ("column", "interviews", "updated_at", "面试记录更新时间，UTC ISO 格式。"),
    ("table", "interview_questions", "", "面试问题表，记录每次面试中被问到的问题、回答情况和表现分。"),
    ("column", "interview_questions", "question_id", "面试问题自增主键。"),
    ("column", "interview_questions", "interview_id", "所属面试记录 ID，对应 interviews.interview_id。"),
    ("column", "interview_questions", "question", "面试问题内容。"),
    ("column", "interview_questions", "answer_summary", "回答情况、复盘或改进说明。"),
    ("column", "interview_questions", "performance_score", "该问题回答表现分数，0 到 100。"),
    ("column", "interview_questions", "created_at", "问题记录创建时间，UTC ISO 格式。"),
    ("column", "interview_questions", "updated_at", "问题记录更新时间，UTC ISO 格式。"),
    ("table", "interview_question_skills", "", "面试问题与技能点关联表，用于统计高频被问和薄弱技能。"),
    ("column", "interview_question_skills", "question_id", "关联的问题 ID，对应 interview_questions.question_id。"),
    ("column", "interview_question_skills", "skill_name", "关联的技能名称，对应 skills.name。"),
    ("column", "interview_question_skills", "created_at", "关联记录创建时间，UTC ISO 格式。"),
    ("table", "schema_comments", "", "SQLite 表结构注释元数据表，用于替代 MySQL 原生 COMMENT。"),
    ("column", "schema_comments", "object_type", "注释对象类型，table 表示表注释，column 表示字段注释。"),
    ("column", "schema_comments", "table_name", "被注释的表名。"),
    ("column", "schema_comments", "column_name", "被注释的字段名；表注释固定为空字符串。"),
    ("column", "schema_comments", "comment", "中文注释内容。"),
    ("column", "schema_comments", "updated_at", "注释最近更新时间，UTC ISO 格式。"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_job_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    parsed = urlparse(text)
    path = parsed.path.rstrip("/")
    if "/job_detail/" in path:
        return "https://www.zhipin.com" + path

    if parsed.scheme and parsed.netloc:
        return urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                path or "/",
                "",
                parsed.query,
                "",
            )
        )
    return text


def normalize_source(value: str) -> str:
    source = str(value or "").strip().lower().replace("_", "-")
    aliases = {
        "": "boss",
        "boss-extension": "boss",
        "zhipin": "boss",
        "boss直聘": "boss",
    }
    return aliases.get(source, source)


def _job_value(job: JobPosting | dict[str, Any], field: str) -> str:
    if isinstance(job, JobPosting):
        return str(getattr(job, field, "") or "")
    return str(job.get(field, "") or "")


def _manual_source_job_id(job: JobPosting | dict[str, Any]) -> str:
    raw = "|".join(
        [
            _job_value(job, "title").strip().lower(),
            _job_value(job, "company").strip().lower(),
            _job_value(job, "salary").strip().lower(),
            _job_value(job, "location").strip().lower(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalized_generic_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme and parsed.netloc:
        return urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/") or "/",
                "",
                parsed.query,
                "",
            )
        )
    return text


def job_identity(job: JobPosting | dict[str, Any]) -> dict[str, str]:
    raw_url = _job_value(job, "source_url") or _job_value(job, "url")
    explicit_id = _job_value(job, "source_job_id")
    source = normalize_source(_job_value(job, "source"))

    if source == "manual" or (not raw_url and not explicit_id):
        source = "manual"
        source_job_id = explicit_id.removeprefix("manual:") or _manual_source_job_id(job)
    elif source == "boss":
        source_job_id = normalize_job_url(explicit_id or raw_url)
    else:
        source_job_id = _normalized_generic_url(explicit_id or raw_url)

    if not source_job_id:
        source = "manual"
        source_job_id = _manual_source_job_id(job)

    source_url = raw_url or (source_job_id if source != "manual" else "")
    return {
        "source": source,
        "source_job_id": source_job_id,
        "source_url": source_url,
        "job_key": f"{source}:{source_job_id}",
    }


def job_key(job: JobPosting | dict[str, Any]) -> str:
    return job_identity(job)["job_key"]


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: str | Path) -> None:
    with connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_jobs (
                job_key TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                salary TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                experience TEXT NOT NULL DEFAULT '',
                education TEXT NOT NULL DEFAULT '',
                company TEXT NOT NULL DEFAULT '',
                industry TEXT NOT NULL DEFAULT '',
                financing TEXT NOT NULL DEFAULT '',
                company_size TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'boss',
                source_job_id TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                matched INTEGER NOT NULL DEFAULT 0,
                score INTEGER NOT NULL DEFAULT 0,
                matched_reasons TEXT NOT NULL DEFAULT '[]',
                exclusion_reason TEXT NOT NULL DEFAULT '',
                tracking_status TEXT NOT NULL DEFAULT '未投递',
                notes TEXT NOT NULL DEFAULT '',
                is_favorite INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                unfavorited_at TEXT NOT NULL DEFAULT ''
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_saved_jobs_favorite_score "
            "ON saved_jobs (is_favorite, score DESC, updated_at DESC)"
        )
        _ensure_saved_job_source_columns(connection)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_saved_jobs_source_identity "
            "ON saved_jobs (source, source_job_id)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS skills (
                name TEXT PRIMARY KEY,
                category TEXT NOT NULL DEFAULT '',
                mastery_level TEXT NOT NULL DEFAULT '未评估',
                mastery_score INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                learning_notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS job_skill_mentions (
                job_key TEXT NOT NULL,
                skill_name TEXT NOT NULL,
                mention_count INTEGER NOT NULL DEFAULT 0,
                contexts TEXT NOT NULL DEFAULT '[]',
                importance INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (job_key, skill_name)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_job_skill_mentions_skill "
            "ON job_skill_mentions (skill_name, importance DESC)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                project_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT '',
                period TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                outcome TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_skill_links (
                project_id INTEGER NOT NULL,
                skill_name TEXT NOT NULL,
                evidence TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (project_id, skill_name)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS interviews (
                interview_id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_key TEXT NOT NULL DEFAULT '',
                company TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                round_name TEXT NOT NULL DEFAULT '',
                interview_time TEXT NOT NULL DEFAULT '',
                interview_type TEXT NOT NULL DEFAULT '',
                result TEXT NOT NULL DEFAULT '',
                performance_score INTEGER NOT NULL DEFAULT 0,
                summary TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_interviews_job_time "
            "ON interviews (job_key, updated_at DESC)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id INTEGER NOT NULL,
                question TEXT NOT NULL DEFAULT '',
                answer_summary TEXT NOT NULL DEFAULT '',
                performance_score INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_interview_questions_interview "
            "ON interview_questions (interview_id, question_id)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_question_skills (
                question_id INTEGER NOT NULL,
                skill_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (question_id, skill_name)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_interview_question_skills_skill "
            "ON interview_question_skills (skill_name)"
        )
        _normalize_existing_saved_job_keys(connection)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_comments (
                object_type TEXT NOT NULL,
                table_name TEXT NOT NULL,
                column_name TEXT NOT NULL DEFAULT '',
                comment TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (object_type, table_name, column_name)
            )
            """
        )
        _seed_schema_comments(connection)


def _seed_schema_comments(connection: sqlite3.Connection) -> None:
    now = utc_now()
    connection.executemany(
        """
        INSERT INTO schema_comments (object_type, table_name, column_name, comment, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(object_type, table_name, column_name) DO UPDATE SET
            comment = excluded.comment,
            updated_at = excluded.updated_at
        """,
        [(*comment, now) for comment in SCHEMA_COMMENTS],
    )


def _ensure_saved_job_source_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(saved_jobs)").fetchall()
    }
    additions = {
        "source": "TEXT NOT NULL DEFAULT 'boss'",
        "source_job_id": "TEXT NOT NULL DEFAULT ''",
        "source_url": "TEXT NOT NULL DEFAULT ''",
    }
    for column, definition in additions.items():
        if column not in columns:
            connection.execute(f"ALTER TABLE saved_jobs ADD COLUMN {column} {definition}")


def _normalize_existing_saved_job_keys(connection: sqlite3.Connection) -> None:
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    if "saved_jobs" not in tables:
        return

    rows = connection.execute("SELECT * FROM saved_jobs").fetchall()
    for row in rows:
        old_key = row["job_key"]
        row_data = dict(row)
        if not row_data.get("source_url"):
            row_data["source_url"] = row_data.get("url", "")
        if old_key.startswith("manual:") and not row_data.get("url"):
            row_data["source"] = "manual"
            row_data["source_job_id"] = old_key.removeprefix("manual:")
        elif not str(old_key).startswith(("boss:", "manual:")):
            row_data["source"] = "boss"

        identity = job_identity(row_data)
        new_key = identity["job_key"]
        connection.execute(
            """
            UPDATE saved_jobs
            SET source = ?, source_job_id = ?, source_url = ?
            WHERE job_key = ?
            """,
            (
                identity["source"],
                identity["source_job_id"],
                identity["source_url"],
                old_key,
            ),
        )
        if not new_key or new_key == old_key:
            continue

        existing = connection.execute(
            "SELECT * FROM saved_jobs WHERE job_key = ?",
            (new_key,),
        ).fetchone()
        if existing:
            _merge_saved_job_rows(connection, dict(existing), dict(row), new_key)
            _move_job_references(connection, old_key, new_key)
            connection.execute("DELETE FROM saved_jobs WHERE job_key = ?", (old_key,))
        else:
            connection.execute(
                "UPDATE saved_jobs SET job_key = ? WHERE job_key = ?",
                (new_key, old_key),
            )
            _move_job_references(connection, old_key, new_key)


def _move_job_references(connection: sqlite3.Connection, old_key: str, new_key: str) -> None:
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    if "job_skill_mentions" in tables:
        connection.execute(
            """
            INSERT OR REPLACE INTO job_skill_mentions (
                job_key, skill_name, mention_count, contexts, importance, created_at, updated_at
            )
            SELECT ?, skill_name, mention_count, contexts, importance, created_at, updated_at
            FROM job_skill_mentions
            WHERE job_key = ?
            """,
            (new_key, old_key),
        )
        connection.execute("DELETE FROM job_skill_mentions WHERE job_key = ?", (old_key,))
    if "interviews" in tables:
        connection.execute(
            "UPDATE interviews SET job_key = ? WHERE job_key = ?",
            (new_key, old_key),
        )


def _merge_saved_job_rows(
    connection: sqlite3.Connection,
    target: dict[str, Any],
    source: dict[str, Any],
    key: str,
) -> None:
    def prefer_longer(field: str) -> str:
        target_value = str(target.get(field, "") or "")
        source_value = str(source.get(field, "") or "")
        return source_value if len(source_value) > len(target_value) else target_value

    def prefer_non_empty(field: str) -> str:
        return str(target.get(field, "") or source.get(field, "") or "")

    tracking_status = str(target.get("tracking_status", "") or "")
    source_status = str(source.get("tracking_status", "") or "")
    if tracking_status in ("", "未投递") and source_status:
        tracking_status = source_status

    merged = {
        "title": prefer_non_empty("title"),
        "salary": prefer_non_empty("salary"),
        "location": prefer_non_empty("location"),
        "experience": prefer_non_empty("experience"),
        "education": prefer_non_empty("education"),
        "company": prefer_non_empty("company"),
        "industry": prefer_non_empty("industry"),
        "financing": prefer_non_empty("financing"),
        "company_size": prefer_non_empty("company_size"),
        "source": prefer_non_empty("source"),
        "source_job_id": prefer_non_empty("source_job_id"),
        "source_url": prefer_non_empty("source_url"),
        "url": prefer_non_empty("url"),
        "description": prefer_longer("description"),
        "matched": max(int(target.get("matched") or 0), int(source.get("matched") or 0)),
        "score": max(int(target.get("score") or 0), int(source.get("score") or 0)),
        "matched_reasons": prefer_longer("matched_reasons"),
        "exclusion_reason": prefer_non_empty("exclusion_reason"),
        "tracking_status": tracking_status,
        "notes": prefer_longer("notes"),
        "is_favorite": max(int(target.get("is_favorite") or 0), int(source.get("is_favorite") or 0)),
        "created_at": min(str(target.get("created_at") or ""), str(source.get("created_at") or "")),
        "updated_at": max(str(target.get("updated_at") or ""), str(source.get("updated_at") or "")),
        "last_seen_at": max(str(target.get("last_seen_at") or ""), str(source.get("last_seen_at") or "")),
        "unfavorited_at": str(target.get("unfavorited_at", "") or source.get("unfavorited_at", "") or ""),
    }
    connection.execute(
        """
        UPDATE saved_jobs
        SET title = ?, salary = ?, location = ?, experience = ?, education = ?,
            company = ?, industry = ?, financing = ?, company_size = ?,
            source = ?, source_job_id = ?, source_url = ?, url = ?, description = ?,
            matched = ?, score = ?, matched_reasons = ?,
            exclusion_reason = ?, tracking_status = ?, notes = ?, is_favorite = ?,
            created_at = ?, updated_at = ?, last_seen_at = ?, unfavorited_at = ?
        WHERE job_key = ?
        """,
        (
            merged["title"],
            merged["salary"],
            merged["location"],
            merged["experience"],
            merged["education"],
            merged["company"],
            merged["industry"],
            merged["financing"],
            merged["company_size"],
            merged["source"],
            merged["source_job_id"],
            merged["source_url"],
            merged["url"],
            merged["description"],
            merged["matched"],
            merged["score"],
            merged["matched_reasons"],
            merged["exclusion_reason"],
            merged["tracking_status"],
            merged["notes"],
            merged["is_favorite"],
            merged["created_at"],
            merged["updated_at"],
            merged["last_seen_at"],
            merged["unfavorited_at"],
            key,
        ),
    )


def _json_list(value: list[str]) -> str:
    return json.dumps(value, ensure_ascii=False)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["matched"] = bool(data["matched"])
    data["is_favorite"] = bool(data["is_favorite"])
    try:
        data["matched_reasons"] = json.loads(data["matched_reasons"] or "[]")
    except json.JSONDecodeError:
        data["matched_reasons"] = []
    return data


def upsert_saved_job(db_path: str | Path, scored_job: ScoredJob) -> dict[str, Any]:
    init_db(db_path)
    now = utc_now()
    identity = job_identity(scored_job.job)
    key = identity["job_key"]
    job_data = asdict(scored_job.job)
    job_data.update(identity)
    if not job_data.get("url"):
        job_data["url"] = identity["source_url"]
    if not job_data.get("source_url"):
        job_data["source_url"] = str(job_data.get("url", "") or "")

    with connect(db_path) as connection:
        existing = connection.execute(
            "SELECT tracking_status, notes, created_at FROM saved_jobs WHERE job_key = ?",
            (key,),
        ).fetchone()
        tracking_status = existing["tracking_status"] if existing else "未投递"
        notes = existing["notes"] if existing else ""
        created_at = existing["created_at"] if existing else now

        connection.execute(
            """
            INSERT INTO saved_jobs (
                job_key, title, salary, location, experience, education, company,
                industry, financing, company_size, source, source_job_id, source_url,
                url, description, matched, score, matched_reasons, exclusion_reason,
                tracking_status, notes, is_favorite, created_at, updated_at,
                last_seen_at, unfavorited_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, '')
            ON CONFLICT(job_key) DO UPDATE SET
                title = excluded.title,
                salary = excluded.salary,
                location = excluded.location,
                experience = excluded.experience,
                education = excluded.education,
                company = excluded.company,
                industry = excluded.industry,
                financing = excluded.financing,
                company_size = excluded.company_size,
                source = excluded.source,
                source_job_id = excluded.source_job_id,
                source_url = excluded.source_url,
                url = excluded.url,
                description = excluded.description,
                matched = excluded.matched,
                score = excluded.score,
                matched_reasons = excluded.matched_reasons,
                exclusion_reason = excluded.exclusion_reason,
                tracking_status = excluded.tracking_status,
                notes = excluded.notes,
                is_favorite = 1,
                updated_at = excluded.updated_at,
                last_seen_at = excluded.last_seen_at,
                unfavorited_at = ''
            """,
            (
                key,
                *(str(job_data.get(column, "") or "") for column in JOB_COLUMNS),
                1 if scored_job.matched else 0,
                int(scored_job.score),
                _json_list(scored_job.matched_reasons),
                scored_job.exclusion_reason,
                tracking_status,
                notes,
                created_at,
                now,
                now,
            ),
        )

        return get_saved_job_from_connection(connection, key) or {}


def get_saved_job_from_connection(
    connection: sqlite3.Connection, key: str
) -> dict[str, Any] | None:
    row = connection.execute("SELECT * FROM saved_jobs WHERE job_key = ?", (key,)).fetchone()
    return _row_to_dict(row) if row else None


def get_saved_job(db_path: str | Path, key: str) -> dict[str, Any] | None:
    init_db(db_path)
    with connect(db_path) as connection:
        return get_saved_job_from_connection(connection, key)


def list_saved_jobs(db_path: str | Path, include_unfavorited: bool = False) -> list[dict[str, Any]]:
    init_db(db_path)
    where = "" if include_unfavorited else "WHERE is_favorite = 1"
    with connect(db_path) as connection:
        rows = connection.execute(
            f"SELECT * FROM saved_jobs {where} ORDER BY is_favorite DESC, score DESC, updated_at DESC"
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def unsave_job(db_path: str | Path, key: str) -> bool:
    init_db(db_path)
    now = utc_now()
    with connect(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE saved_jobs
            SET is_favorite = 0, updated_at = ?, unfavorited_at = ?
            WHERE job_key = ?
            """,
            (now, now, key),
        )
        return cursor.rowcount > 0


def update_tracking(
    db_path: str | Path, key: str, tracking_status: str, notes: str | None = None
) -> dict[str, Any] | None:
    init_db(db_path)
    now = utc_now()
    with connect(db_path) as connection:
        if notes is None:
            connection.execute(
                "UPDATE saved_jobs SET tracking_status = ?, updated_at = ? WHERE job_key = ?",
                (tracking_status, now, key),
            )
        else:
            connection.execute(
                "UPDATE saved_jobs SET tracking_status = ?, notes = ?, updated_at = ? WHERE job_key = ?",
                (tracking_status, notes, now, key),
            )
        return get_saved_job_from_connection(connection, key)


def _json_loads_list(value: str) -> list[Any]:
    try:
        result = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return result if isinstance(result, list) else []


def _bounded_score(value: Any) -> int:
    try:
        score = int(value or 0)
    except (TypeError, ValueError):
        score = 0
    return max(0, min(100, score))


def upsert_job_skill_mentions(
    db_path: str | Path, key: str, mentions: list[dict[str, Any]]
) -> None:
    init_db(db_path)
    now = utc_now()
    with connect(db_path) as connection:
        connection.execute("DELETE FROM job_skill_mentions WHERE job_key = ?", (key,))
        for mention in mentions:
            name = str(mention.get("name", "") or "").strip()
            if not name:
                continue
            category = str(mention.get("category", "") or "").strip()
            existing_skill = connection.execute(
                "SELECT name FROM skills WHERE name = ?", (name,)
            ).fetchone()
            if existing_skill:
                connection.execute(
                    "UPDATE skills SET category = COALESCE(NULLIF(?, ''), category), updated_at = ? WHERE name = ?",
                    (category, now, name),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO skills (
                        name, category, mastery_level, mastery_score, notes,
                        learning_notes, created_at, updated_at
                    ) VALUES (?, ?, '未评估', 0, '', '', ?, ?)
                    """,
                    (name, category, now, now),
                )
            connection.execute(
                """
                INSERT INTO job_skill_mentions (
                    job_key, skill_name, mention_count, contexts, importance, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    name,
                    int(mention.get("mention_count") or 0),
                    json.dumps(mention.get("contexts") or [], ensure_ascii=False),
                    int(mention.get("importance") or 0),
                    now,
                    now,
                ),
            )


def list_skills(db_path: str | Path) -> list[dict[str, Any]]:
    init_db(db_path)
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                s.*,
                COALESCE(SUM(jsm.mention_count), 0) AS mention_count,
                COALESCE(MAX(jsm.importance), 0) AS max_importance,
                COUNT(DISTINCT jsm.job_key) AS job_count,
                COUNT(DISTINCT psl.project_id) AS project_count
            FROM skills s
            LEFT JOIN job_skill_mentions jsm ON jsm.skill_name = s.name
            LEFT JOIN project_skill_links psl ON psl.skill_name = s.name
            GROUP BY s.name
            ORDER BY mention_count DESC, job_count DESC, s.name ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_skill_detail(db_path: str | Path, name: str) -> dict[str, Any] | None:
    init_db(db_path)
    skill_name = str(name or "").strip()
    with connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                s.*,
                COALESCE(SUM(jsm.mention_count), 0) AS mention_count,
                COALESCE(MAX(jsm.importance), 0) AS max_importance,
                COUNT(DISTINCT jsm.job_key) AS job_count,
                COUNT(DISTINCT psl.project_id) AS project_count
            FROM skills s
            LEFT JOIN job_skill_mentions jsm ON jsm.skill_name = s.name
            LEFT JOIN project_skill_links psl ON psl.skill_name = s.name
            WHERE s.name = ?
            GROUP BY s.name
            """,
            (skill_name,),
        ).fetchone()
        if not row:
            return None
        job_rows = connection.execute(
            """
            SELECT j.job_key, j.title, j.company, j.salary, j.location, jsm.mention_count, jsm.contexts, jsm.importance
            FROM job_skill_mentions jsm
            JOIN saved_jobs j ON j.job_key = jsm.job_key
            WHERE jsm.skill_name = ? AND j.is_favorite = 1
            ORDER BY jsm.importance DESC, j.score DESC, j.updated_at DESC
            """,
            (skill_name,),
        ).fetchall()
        project_rows = connection.execute(
            """
            SELECT p.project_id, p.name, p.role, p.period, psl.evidence
            FROM project_skill_links psl
            JOIN projects p ON p.project_id = psl.project_id
            WHERE psl.skill_name = ?
            ORDER BY p.updated_at DESC, p.project_id DESC
            """,
            (skill_name,),
        ).fetchall()
    data = dict(row)
    data["jobs"] = [
        {
            **dict(job_row),
            "contexts": _json_loads_list(job_row["contexts"]),
        }
        for job_row in job_rows
    ]
    data["projects"] = [dict(project_row) for project_row in project_rows]
    return data


def get_skill_mentions_for_job(db_path: str | Path, key: str) -> list[dict[str, Any]]:
    init_db(db_path)
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT skill_name, mention_count, contexts, importance
            FROM job_skill_mentions
            WHERE job_key = ?
            ORDER BY importance DESC, mention_count DESC, skill_name ASC
            """,
            (key,),
        ).fetchall()
    return [
        {
            "skill_name": row["skill_name"],
            "mention_count": row["mention_count"],
            "contexts": _json_loads_list(row["contexts"]),
            "importance": row["importance"],
        }
        for row in rows
    ]


def update_skill_profile(
    db_path: str | Path,
    name: str,
    mastery_level: str,
    mastery_score: int,
    notes: str = "",
    learning_notes: str = "",
    category: str = "",
) -> dict[str, Any]:
    init_db(db_path)
    skill_name = str(name or "").strip()
    if not skill_name:
        raise ValueError("技能名称不能为空")
    score = max(0, min(100, int(mastery_score or 0)))
    now = utc_now()
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO skills (
                name, category, mastery_level, mastery_score, notes, learning_notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                category = COALESCE(NULLIF(excluded.category, ''), skills.category),
                mastery_level = excluded.mastery_level,
                mastery_score = excluded.mastery_score,
                notes = excluded.notes,
                learning_notes = excluded.learning_notes,
                updated_at = excluded.updated_at
            """,
            (
                skill_name,
                category,
                mastery_level or "未评估",
                score,
                notes,
                learning_notes,
                now,
                now,
            ),
        )
        row = connection.execute("SELECT * FROM skills WHERE name = ?", (skill_name,)).fetchone()
    return dict(row) if row else {}


def _split_skill_names(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = re_split_values(str(value or ""))
    names: list[str] = []
    for item in raw_items:
        name = str(item or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def re_split_values(value: str) -> list[str]:
    normalized = value.replace("，", ",").replace("、", ",").replace("\n", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def create_project(db_path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    init_db(db_path)
    now = utc_now()
    skills = _split_skill_names(payload.get("skills", []))
    with connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO projects (name, role, period, description, outcome, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(payload.get("name", "") or "").strip(),
                str(payload.get("role", "") or "").strip(),
                str(payload.get("period", "") or "").strip(),
                str(payload.get("description", "") or "").strip(),
                str(payload.get("outcome", "") or "").strip(),
                now,
                now,
            ),
        )
        project_id = int(cursor.lastrowid)
        evidence = str(payload.get("evidence", "") or "").strip()
        for skill_name in skills:
            connection.execute(
                """
                INSERT INTO skills (
                    name, category, mastery_level, mastery_score, notes, learning_notes, created_at, updated_at
                ) VALUES (?, '', '未评估', 0, '', '', ?, ?)
                ON CONFLICT(name) DO NOTHING
                """,
                (skill_name, now, now),
            )
            connection.execute(
                """
                INSERT INTO project_skill_links (project_id, skill_name, evidence, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_id, skill_name) DO UPDATE SET
                    evidence = excluded.evidence,
                    updated_at = excluded.updated_at
                """,
                (project_id, skill_name, evidence, now, now),
            )
    return get_project(db_path, project_id) or {}


def get_project(db_path: str | Path, project_id: int) -> dict[str, Any] | None:
    init_db(db_path)
    with connect(db_path) as connection:
        row = connection.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        if not row:
            return None
        skills = connection.execute(
            "SELECT skill_name, evidence FROM project_skill_links WHERE project_id = ? ORDER BY skill_name",
            (project_id,),
        ).fetchall()
    data = dict(row)
    data["skills"] = [dict(skill) for skill in skills]
    return data


def list_projects(db_path: str | Path) -> list[dict[str, Any]]:
    init_db(db_path)
    with connect(db_path) as connection:
        rows = connection.execute("SELECT * FROM projects ORDER BY updated_at DESC, project_id DESC").fetchall()
        skill_rows = connection.execute(
            "SELECT project_id, skill_name, evidence FROM project_skill_links ORDER BY skill_name"
        ).fetchall()
    skills_by_project: dict[int, list[dict[str, Any]]] = {}
    for row in skill_rows:
        skills_by_project.setdefault(int(row["project_id"]), []).append(
            {"skill_name": row["skill_name"], "evidence": row["evidence"]}
        )
    projects = []
    for row in rows:
        data = dict(row)
        data["skills"] = skills_by_project.get(int(row["project_id"]), [])
        projects.append(data)
    return projects


def _questions_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_questions = payload.get("questions", [])
    if isinstance(raw_questions, str):
        try:
            raw_questions = json.loads(raw_questions or "[]")
        except json.JSONDecodeError:
            raw_questions = []
    if not isinstance(raw_questions, list):
        return []

    questions: list[dict[str, Any]] = []
    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "") or "").strip()
        if not question:
            continue
        questions.append(
            {
                "question": question,
                "answer_summary": str(item.get("answer_summary", "") or "").strip(),
                "performance_score": _bounded_score(item.get("performance_score")),
                "skills": _split_skill_names(item.get("skills", [])),
            }
        )
    return questions


def create_interview(db_path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    init_db(db_path)
    now = utc_now()
    job_key_value = str(payload.get("job_key", "") or "").strip()
    questions = _questions_from_payload(payload)

    with connect(db_path) as connection:
        job = (
            connection.execute("SELECT * FROM saved_jobs WHERE job_key = ?", (job_key_value,)).fetchone()
            if job_key_value
            else None
        )
        company = str(payload.get("company", "") or "").strip() or (job["company"] if job else "")
        title = str(payload.get("title", "") or "").strip() or (job["title"] if job else "")
        cursor = connection.execute(
            """
            INSERT INTO interviews (
                job_key, company, title, round_name, interview_time, interview_type,
                result, performance_score, summary, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_key_value,
                company,
                title,
                str(payload.get("round_name", "") or "").strip(),
                str(payload.get("interview_time", "") or "").strip(),
                str(payload.get("interview_type", "") or "").strip(),
                str(payload.get("result", "") or "").strip(),
                _bounded_score(payload.get("performance_score")),
                str(payload.get("summary", "") or "").strip(),
                now,
                now,
            ),
        )
        interview_id = int(cursor.lastrowid)

        tracking_status = str(payload.get("tracking_status", "") or "").strip()
        if job_key_value and tracking_status:
            connection.execute(
                "UPDATE saved_jobs SET tracking_status = ?, updated_at = ? WHERE job_key = ?",
                (tracking_status, now, job_key_value),
            )

        for question in questions:
            question_cursor = connection.execute(
                """
                INSERT INTO interview_questions (
                    interview_id, question, answer_summary, performance_score, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    interview_id,
                    question["question"],
                    question["answer_summary"],
                    question["performance_score"],
                    now,
                    now,
                ),
            )
            question_id = int(question_cursor.lastrowid)
            for skill_name in question["skills"]:
                connection.execute(
                    """
                    INSERT INTO skills (
                        name, category, mastery_level, mastery_score, notes,
                        learning_notes, created_at, updated_at
                    ) VALUES (?, '', '未评估', 0, '', '', ?, ?)
                    ON CONFLICT(name) DO NOTHING
                    """,
                    (skill_name, now, now),
                )
                connection.execute(
                    """
                    INSERT INTO interview_question_skills (question_id, skill_name, created_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(question_id, skill_name) DO NOTHING
                    """,
                    (question_id, skill_name, now),
                )

    return get_interview(db_path, interview_id) or {}


def get_interview(db_path: str | Path, interview_id: int) -> dict[str, Any] | None:
    init_db(db_path)
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM interviews WHERE interview_id = ?",
            (interview_id,),
        ).fetchone()
        if not row:
            return None
        question_rows = connection.execute(
            """
            SELECT * FROM interview_questions
            WHERE interview_id = ?
            ORDER BY question_id ASC
            """,
            (interview_id,),
        ).fetchall()
        skill_rows = connection.execute(
            """
            SELECT iqs.question_id, iqs.skill_name
            FROM interview_question_skills iqs
            JOIN interview_questions iq ON iq.question_id = iqs.question_id
            WHERE iq.interview_id = ?
            ORDER BY iqs.skill_name ASC
            """,
            (interview_id,),
        ).fetchall()

    skills_by_question: dict[int, list[str]] = {}
    for skill_row in skill_rows:
        skills_by_question.setdefault(int(skill_row["question_id"]), []).append(skill_row["skill_name"])

    data = dict(row)
    data["questions"] = [
        {
            **dict(question_row),
            "skills": skills_by_question.get(int(question_row["question_id"]), []),
        }
        for question_row in question_rows
    ]
    return data


def list_interviews(db_path: str | Path, job_key: str | None = None) -> list[dict[str, Any]]:
    init_db(db_path)
    params: tuple[Any, ...] = ()
    where = ""
    if job_key:
        where = "WHERE i.job_key = ?"
        params = (job_key,)
    with connect(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT
                i.*,
                COUNT(DISTINCT iq.question_id) AS question_count,
                COUNT(DISTINCT iqs.skill_name) AS skill_count,
                GROUP_CONCAT(DISTINCT iq.question) AS question_texts,
                GROUP_CONCAT(DISTINCT iqs.skill_name) AS skill_names
            FROM interviews i
            LEFT JOIN interview_questions iq ON iq.interview_id = i.interview_id
            LEFT JOIN interview_question_skills iqs ON iqs.question_id = iq.question_id
            {where}
            GROUP BY i.interview_id
            ORDER BY i.updated_at DESC, i.interview_id DESC
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def interview_skill_stats(db_path: str | Path) -> list[dict[str, Any]]:
    init_db(db_path)
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                iqs.skill_name,
                COUNT(*) AS asked_count,
                ROUND(AVG(iq.performance_score), 1) AS average_score,
                SUM(CASE WHEN iq.performance_score < 60 THEN 1 ELSE 0 END) AS weak_count,
                MAX(i.updated_at) AS last_asked_at
            FROM interview_question_skills iqs
            JOIN interview_questions iq ON iq.question_id = iqs.question_id
            JOIN interviews i ON i.interview_id = iq.interview_id
            GROUP BY iqs.skill_name
            ORDER BY weak_count DESC, asked_count DESC, average_score ASC, iqs.skill_name ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]
