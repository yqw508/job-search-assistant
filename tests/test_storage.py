from boss_job_assistant.models import JobPosting, ScoredJob
from boss_job_assistant.storage import (
    connect,
    create_interview,
    get_saved_job,
    interview_skill_stats,
    init_db,
    job_identity,
    job_key,
    list_interviews,
    list_saved_jobs,
    normalize_job_url,
    unsave_job,
    update_tracking,
    upsert_saved_job,
)


def make_scored_job(title: str = "Java 后端开发工程师", score: int = 88) -> ScoredJob:
    return ScoredJob(
        job=JobPosting(
            title=title,
            salary="25-35K",
            location="广州·天河",
            experience="5-10年",
            education="本科",
            company="未来科技有限公司",
            industry="互联网",
            financing="B轮",
            company_size="100-499人",
            url="https://www.zhipin.com/job_detail/example.html",
            description="职位描述：负责 C 端 Java Spring Boot 业务开发。",
        ),
        matched=True,
        score=score,
        matched_reasons=["薪资满足 22K+", "命中 Java"],
    )


def test_upsert_saved_job_persists_scored_job(tmp_path):
    db_path = tmp_path / "jobs.sqlite3"

    saved = upsert_saved_job(db_path, make_scored_job())

    assert saved["title"] == "Java 后端开发工程师"
    assert saved["score"] == 88
    assert saved["matched"] is True
    assert saved["is_favorite"] is True
    assert saved["source"] == "boss"
    assert saved["source_job_id"] == "https://www.zhipin.com/job_detail/example.html"
    assert saved["source_url"] == "https://www.zhipin.com/job_detail/example.html"
    assert saved["tracking_status"] == "未投递"
    assert saved["matched_reasons"] == ["薪资满足 22K+", "命中 Java"]


def test_upsert_preserves_tracking_status_and_notes(tmp_path):
    db_path = tmp_path / "jobs.sqlite3"
    saved_job = upsert_saved_job(db_path, make_scored_job())
    key = saved_job["job_key"]

    update_tracking(db_path, key, "面试中", "一面已约")
    upsert_saved_job(db_path, make_scored_job(score=91))

    saved = get_saved_job(db_path, key)
    assert saved["score"] == 91
    assert saved["tracking_status"] == "面试中"
    assert saved["notes"] == "一面已约"


def test_unsave_hides_job_from_default_list(tmp_path):
    db_path = tmp_path / "jobs.sqlite3"
    key = upsert_saved_job(db_path, make_scored_job())["job_key"]

    assert unsave_job(db_path, key) is True

    assert list_saved_jobs(db_path) == []
    assert list_saved_jobs(db_path, include_unfavorited=True)[0]["is_favorite"] is False


def test_job_key_uses_url_when_available():
    job = JobPosting(title="Java", company="A", salary="22K", url="https://example.test/job")

    assert job_key(job) == "boss:https://example.test/job"


def test_job_key_uses_source_to_avoid_cross_site_collisions():
    boss = JobPosting(title="Java", company="A", salary="22K", source="boss", url="https://example.test/job")
    liepin = JobPosting(title="Java", company="A", salary="22K", source="liepin", url="https://example.test/job")

    assert job_key(boss) == "boss:https://example.test/job"
    assert job_key(liepin) == "liepin:https://example.test/job"


def test_job_identity_uses_manual_hash_without_url():
    identity = job_identity(
        JobPosting(title="Java", company="A", salary="22K", location="广州", source="manual")
    )

    assert identity["source"] == "manual"
    assert identity["job_key"].startswith("manual:")
    assert len(identity["source_job_id"]) == 64


def test_job_key_normalizes_boss_detail_url_variants():
    canonical = "https://www.zhipin.com/job_detail/abc123.html"

    assert normalize_job_url("https://www.zhipin.com/job_detail/abc123.html?lid=1") == canonical
    assert normalize_job_url("https://www.zhipin.com/job_detail/abc123.html?securityId=x#main") == canonical
    assert normalize_job_url("/job_detail/abc123.html?ka=search_list") == canonical


def test_upsert_merges_same_boss_job_url_variants(tmp_path):
    db_path = tmp_path / "jobs.sqlite3"
    first = make_scored_job()
    first.job.url = "https://www.zhipin.com/job_detail/abc123.html?lid=1"
    first.job.description = "列表页描述"
    second = make_scored_job(score=95)
    second.job.url = "https://www.zhipin.com/job_detail/abc123.html?securityId=x"
    second.job.description = "详情页描述更完整，包含 Spring、JVM、Redis 和项目经验要求"

    first_saved = upsert_saved_job(db_path, first)
    second_saved = upsert_saved_job(db_path, second)
    jobs = list_saved_jobs(db_path)

    assert first_saved["job_key"] == "boss:https://www.zhipin.com/job_detail/abc123.html"
    assert second_saved["job_key"] == first_saved["job_key"]
    assert len(jobs) == 1
    assert jobs[0]["score"] == 95
    assert jobs[0]["description"] == second.job.description


def test_init_db_migrates_legacy_url_job_key_to_source_identity(tmp_path):
    db_path = tmp_path / "jobs.sqlite3"
    old_key = "https://www.zhipin.com/job_detail/legacy.html?lid=1"

    with connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE saved_jobs (
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
            """
            INSERT INTO saved_jobs (
                job_key, title, url, created_at, updated_at, last_seen_at
            ) VALUES (?, 'Java', ?, '2026-05-12T00:00:00+00:00', '2026-05-12T00:00:00+00:00', '2026-05-12T00:00:00+00:00')
            """,
            (old_key, old_key),
        )

    init_db(db_path)
    jobs = list_saved_jobs(db_path)

    assert len(jobs) == 1
    assert jobs[0]["job_key"] == "boss:https://www.zhipin.com/job_detail/legacy.html"
    assert jobs[0]["source"] == "boss"
    assert jobs[0]["source_job_id"] == "https://www.zhipin.com/job_detail/legacy.html"
    assert jobs[0]["source_url"] == old_key


def test_init_db_seeds_schema_comments(tmp_path):
    db_path = tmp_path / "jobs.sqlite3"

    init_db(db_path)

    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT object_type, table_name, column_name, comment
            FROM schema_comments
            WHERE table_name IN ('saved_jobs', 'skills', 'projects', 'interviews', 'schema_comments')
            """
        ).fetchall()

    comments = {
        (row["object_type"], row["table_name"], row["column_name"]): row["comment"]
        for row in rows
    }
    assert comments[("table", "saved_jobs", "")] == "收藏岗位主表，保存从 Boss 页面采集并评分后的岗位信息和跟进状态。"
    assert comments[("column", "saved_jobs", "title")] == "岗位名称。"
    assert comments[("column", "skills", "mastery_level")] == "个人掌握程度文本描述。"
    assert comments[("column", "projects", "description")] == "项目背景、核心工作和技术方案描述。"
    assert comments[("table", "schema_comments", "")] == "SQLite 表结构注释元数据表，用于替代 MySQL 原生 COMMENT。"
    assert comments[("table", "interviews", "")] == "面试记录主表，记录每次面试的岗位、轮次、结果和整体表现。"


def test_create_interview_links_questions_skills_and_updates_job_status(tmp_path):
    db_path = tmp_path / "jobs.sqlite3"
    saved_job = upsert_saved_job(db_path, make_scored_job())
    key = saved_job["job_key"]

    interview = create_interview(
        db_path,
        {
            "job_key": key,
            "round_name": "一面",
            "interview_type": "视频",
            "result": "待反馈",
            "performance_score": "72",
            "summary": "整体还可以，JVM 回答不完整",
            "tracking_status": "面试中",
            "questions": [
                {
                    "question": "Spring 事务失效有哪些场景？",
                    "skills": "Spring, Java",
                    "performance_score": "80",
                    "answer_summary": "基本答出来了",
                },
                {
                    "question": "JVM 排查线上问题怎么做？",
                    "skills": "JVM, Java",
                    "performance_score": "45",
                    "answer_summary": "案例不够清晰",
                },
            ],
        },
    )

    assert interview["company"] == saved_job["company"]
    assert interview["title"] == saved_job["title"]
    assert len(interview["questions"]) == 2
    assert interview["questions"][0]["skills"] == ["Java", "Spring"]
    assert get_saved_job(db_path, key)["tracking_status"] == "面试中"

    listed = list_interviews(db_path)
    assert listed[0]["question_count"] == 2
    assert listed[0]["skill_count"] == 3

    stats = interview_skill_stats(db_path)
    java = next(item for item in stats if item["skill_name"] == "Java")
    jvm = next(item for item in stats if item["skill_name"] == "JVM")
    assert java["asked_count"] == 2
    assert jvm["weak_count"] == 1
