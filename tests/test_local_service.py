import json
import threading
from contextlib import contextmanager
from email.message import Message
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import quote

import pytest
import yaml

from boss_job_assistant.local_service import (
    HOST,
    MAX_BODY_BYTES,
    ClientInputError,
    LocalServiceHandler,
    ThreadingHTTPServer,
    jobs_from_payload,
    save_job_response,
    update_settings_response,
)


def make_payload() -> dict:
    return {
        "jobs": [
            {
                "extension_json": {
                    "title": "Java 后端开发工程师",
                    "salary": "25-35K",
                    "location": "广州·天河",
                    "company_size": "100-499人",
                    "description": "职位描述：Java Spring Boot C端交易系统开发。",
                    "url": "https://www.zhipin.com/job_detail/example.html",
                }
            }
        ]
    }


def make_config(output_dir: Path) -> dict:
    return {
        "search": {"keyword": "Java Spring Boot"},
        "filters": {
            "min_salary_k": 22,
            "min_company_size": 100,
            "required_location": "广州",
        },
        "scoring": {
            "positive_keywords": ["Java", "Spring Boot", "Redis"],
            "c_side_keywords": ["C端", "用户"],
            "exclude_keywords": ["外包"],
        },
        "runtime": {
            "output_dir": str(output_dir),
            "database_path": str(output_dir / "jobs.sqlite3"),
        },
        "commute": {
            "home_address": "",
            "max_commute_minutes": 60,
            "map_provider": "amap",
            "map_api_key": "",
        },
    }


def write_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(make_config(tmp_path), allow_unicode=True), encoding="utf-8")
    return config_path


def test_jobs_from_payload_converts_extension_json():
    jobs = jobs_from_payload(make_payload())

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Java 后端开发工程师"
    assert job.salary == "25-35K"
    assert job.location == "广州·天河"
    assert job.company_size == "100-499人"
    assert job.description == "职位描述：Java Spring Boot C端交易系统开发。"


def test_save_job_response_scores_and_persists(tmp_path):
    response = save_job_response({"job": make_payload()["jobs"][0]["extension_json"]}, make_config(tmp_path))

    assert response["ok"] is True
    assert response["job"]["title"] == "Java 后端开发工程师"
    assert response["job"]["score"] > 0
    assert Path(response["database"]).exists()


def test_update_settings_response_writes_config_yaml(tmp_path):
    config_path = write_config(tmp_path)

    response = update_settings_response(
        {
            "min_salary_k": "30",
            "min_company_size": "500",
            "required_location": "深圳",
            "positive_keywords": "Java\nDDD\n",
            "c_side_keywords": "C端\n交易",
            "exclude_keywords": "外包\n驻场",
            "home_address": "广州天河区体育西路",
            "max_commute_minutes": "45",
            "map_provider": "amap",
            "map_api_key": "test-key",
        },
        config_path,
    )

    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert response["ok"] is True
    assert saved["filters"]["min_salary_k"] == 30
    assert saved["filters"]["min_company_size"] == 500
    assert saved["filters"]["required_location"] == "深圳"
    assert saved["scoring"]["positive_keywords"] == ["Java", "DDD"]
    assert saved["scoring"]["c_side_keywords"] == ["C端", "交易"]
    assert saved["scoring"]["exclude_keywords"] == ["外包", "驻场"]
    assert saved["commute"]["home_address"] == "广州天河区体育西路"
    assert saved["commute"]["max_commute_minutes"] == 45
    assert saved["commute"]["map_provider"] == "amap"
    assert saved["commute"]["map_api_key"] == "test-key"


@contextmanager
def run_test_server(config_path: Path | None = None):
    previous_config_path = LocalServiceHandler.config_path
    if config_path is not None:
        LocalServiceHandler.config_path = str(config_path)
    server = ThreadingHTTPServer((HOST, 0), LocalServiceHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        LocalServiceHandler.config_path = previous_config_path


def request(port: int, method: str, path: str, body: bytes | None = None, headers=None):
    connection = HTTPConnection(HOST, port, timeout=5)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        response_body = response.read().decode("utf-8")
        content_type = response.headers.get("Content-Type", "")
        payload = json.loads(response_body) if "application/json" in content_type else response_body
        return response.status, dict(response.headers), payload
    finally:
        connection.close()


def test_handler_health_returns_json():
    with run_test_server() as port:
        status, _, payload = request(port, "GET", "/health")

    assert status == 200
    assert payload == {"ok": True, "service": "boss-job-assistant"}


def test_handler_unknown_path_returns_404(tmp_path):
    with run_test_server(write_config(tmp_path)) as port:
        status, _, payload = request(port, "GET", "/missing")

    assert status == 404
    assert payload["ok"] is False


def test_handler_malformed_json_returns_400():
    with run_test_server() as port:
        status, _, payload = request(
            port,
            "POST",
            "/jobs/save",
            body=b"{",
            headers={"Content-Type": "application/json"},
        )

    assert status == 400
    assert payload["ok"] is False
    assert "JSON" in payload["error"]


def test_handler_too_large_content_length_rejects_without_reading_body():
    class UnreadableBody:
        def read(self, size: int = -1):  # noqa: ARG002
            raise AssertionError("body should not be read")

    handler = LocalServiceHandler.__new__(LocalServiceHandler)
    headers = Message()
    headers["Content-Length"] = str(MAX_BODY_BYTES + 1)
    handler.headers = headers
    handler.rfile = UnreadableBody()

    with pytest.raises(ClientInputError):
        handler._read_json_payload()


def test_handler_cors_echoes_allowed_extension_origin():
    origin = "chrome-extension://dev-extension-id"

    with run_test_server() as port:
        status, headers, payload = request(
            port,
            "GET",
            "/health",
            headers={"Origin": origin},
        )

    assert status == 200
    assert payload["ok"] is True
    assert headers["Access-Control-Allow-Origin"] == origin
    assert headers["Access-Control-Allow-Origin"] != "*"


def test_handler_save_list_and_unsave_job(tmp_path):
    config_path = write_config(tmp_path)
    body = json.dumps({"job": make_payload()["jobs"][0]["extension_json"]}, ensure_ascii=False).encode("utf-8")

    with run_test_server(config_path) as port:
        status, _, saved = request(
            port,
            "POST",
            "/jobs/save",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        assert status == 200
        assert saved["ok"] is True

        status, _, listed = request(port, "GET", "/jobs")
        assert status == 200
        assert len(listed["jobs"]) == 1

        unsave_body = json.dumps({"job_key": saved["job"]["job_key"]}).encode("utf-8")
        status, _, unsaved = request(
            port,
            "POST",
            "/jobs/unsave",
            body=unsave_body,
            headers={"Content-Type": "application/json"},
        )
        assert status == 200
        assert unsaved["ok"] is True

        status, _, listed_after = request(port, "GET", "/jobs")
        assert status == 200
        assert listed_after["jobs"] == []


def test_handler_get_and_post_settings(tmp_path):
    config_path = write_config(tmp_path)

    with run_test_server(config_path) as port:
        status, _, current = request(port, "GET", "/settings")
        assert status == 200
        assert current["settings"]["min_salary_k"] == 22

        body = json.dumps(
            {
                "min_salary_k": "28",
                "min_company_size": "300",
                "required_location": "广州",
                "positive_keywords": "Java\nSpring Boot\n高并发",
                "c_side_keywords": "C端\n用户",
                "exclude_keywords": "外包\n派遣",
                "home_address": "广州天河区",
                "max_commute_minutes": "50",
                "map_provider": "amap",
                "map_api_key": "abc",
            },
            ensure_ascii=False,
        ).encode("utf-8")
        status, _, updated = request(
            port,
            "POST",
            "/settings",
            body=body,
            headers={"Content-Type": "application/json"},
        )

    assert status == 200
    assert updated["ok"] is True
    assert updated["settings"]["min_salary_k"] == 28
    assert updated["settings"]["home_address"] == "广州天河区"
    assert updated["settings"]["max_commute_minutes"] == 50
    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved["scoring"]["positive_keywords"] == ["Java", "Spring Boot", "高并发"]
    assert saved["commute"]["map_api_key"] == "abc"


def test_handler_root_returns_dashboard_html(tmp_path):
    config_path = write_config(tmp_path)
    body = json.dumps({"job": make_payload()["jobs"][0]["extension_json"]}, ensure_ascii=False).encode("utf-8")

    with run_test_server(config_path) as port:
        request(
            port,
            "POST",
            "/jobs/save",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        status, headers, payload = request(port, "GET", "/")

    assert status == 200
    assert "text/html" in headers["Content-Type"]
    assert "求职总览" in payload
    assert "适合岗位" in payload
    assert "已投递" in payload
    assert "面试中" in payload
    assert "查看具体岗位" in payload
    assert 'class="side-nav"' in payload
    assert 'class="side-link active" href="/"' in payload
    assert "/jobs/page" in payload
    assert "/settings/page" in payload
    assert "/jobs/detail?job_key=" not in payload
    assert "job-list" not in payload
    assert "匹配规则配置" not in payload
    assert "settings-form" not in payload
    assert "description-row" not in payload


def test_handler_jobs_page_returns_job_list(tmp_path):
    config_path = write_config(tmp_path)
    body = json.dumps({"job": make_payload()["jobs"][0]["extension_json"]}, ensure_ascii=False).encode("utf-8")

    with run_test_server(config_path) as port:
        request(
            port,
            "POST",
            "/jobs/save",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        status, headers, payload = request(port, "GET", "/jobs/page")

    assert status == 200
    assert "text/html" in headers["Content-Type"]
    assert "岗位列表" in payload
    assert "filter-keyword" in payload
    assert "filter-status" in payload
    assert "sort-jobs" in payload
    assert "page-size" in payload
    assert "page-prev" in payload
    assert "page-next" in payload
    assert "page-info" in payload
    assert 'class="side-nav"' in payload
    assert 'class="side-link active" href="/jobs/page"' in payload
    assert 'data-score="' in payload
    assert 'data-salary-upper="' in payload
    assert "详情分析" in payload
    assert "match-grid" in payload
    assert "/jobs/detail?job_key=" in payload
    assert "settings-form" not in payload


def test_handler_settings_page_returns_config_form(tmp_path):
    config_path = write_config(tmp_path)

    with run_test_server(config_path) as port:
        status, headers, payload = request(port, "GET", "/settings/page")

    assert status == 200
    assert "text/html" in headers["Content-Type"]
    assert "匹配规则配置" in payload
    assert "settings-form" in payload
    assert "家庭地址" in payload
    assert "地图 API Key" in payload
    assert 'class="side-nav"' in payload
    assert 'class="side-link active" href="/settings/page"' in payload
    assert "岗位列表" in payload


def test_handler_skills_page_and_profile_update(tmp_path):
    config_path = write_config(tmp_path)
    body = json.dumps({"job": make_payload()["jobs"][0]["extension_json"]}, ensure_ascii=False).encode("utf-8")

    with run_test_server(config_path) as port:
        request(
            port,
            "POST",
            "/jobs/save",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        status, _, skills_payload = request(port, "GET", "/skills")
        assert status == 200
        assert any(skill["name"] == "Java" for skill in skills_payload["skills"])

        update_body = json.dumps(
            {
                "name": "Java",
                "mastery_level": "项目实战",
                "mastery_score": "82",
                "notes": "能结合项目讲清楚核心链路",
                "learning_notes": "补 JVM 调优",
            },
            ensure_ascii=False,
        ).encode("utf-8")
        status, _, updated = request(
            port,
            "POST",
            "/skills/profile",
            body=update_body,
            headers={"Content-Type": "application/json"},
        )
        assert status == 200
        assert updated["skill"]["mastery_level"] == "项目实战"
        assert updated["skill"]["mastery_score"] == 82

        status, headers, page = request(port, "GET", "/skills/page")
        detail_status, detail_headers, detail_page = request(port, "GET", "/skills/detail?name=Java")

    assert status == 200
    assert "text/html" in headers["Content-Type"]
    assert "skill-search" in page
    assert "Java" in page
    assert "/projects/page" in page
    assert "/skills/detail?name=Java" in page
    assert "skill-form" not in page
    assert 'class="side-link active" href="/skills/page"' in page
    assert detail_status == 200
    assert "text/html" in detail_headers["Content-Type"]
    assert "skill-form" in detail_page
    assert "关联岗位上下文" in detail_page
    assert "项目经验支撑" in detail_page
    assert "项目实战" in detail_page


def test_handler_projects_page_and_create_project(tmp_path):
    config_path = write_config(tmp_path)

    with run_test_server(config_path) as port:
        body = json.dumps(
            {
                "name": "交易中台重构",
                "role": "核心后端开发",
                "period": "2024.03-2024.12",
                "description": "负责订单链路和缓存改造",
                "outcome": "降低接口耗时并提升稳定性",
                "skills": "Java\nRedis\n高并发",
            },
            ensure_ascii=False,
        ).encode("utf-8")
        status, _, created = request(
            port,
            "POST",
            "/projects",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        assert status == 200
        assert created["project"]["name"] == "交易中台重构"
        assert {skill["skill_name"] for skill in created["project"]["skills"]} == {"Java", "Redis", "高并发"}

        status, _, projects = request(port, "GET", "/projects")
        assert status == 200
        assert len(projects["projects"]) == 1

        status, headers, page = request(port, "GET", "/projects/page")

    assert status == 200
    assert "text/html" in headers["Content-Type"]
    assert "project-form" in page
    assert "交易中台重构" in page
    assert 'class="side-link active" href="/projects/page"' in page


def test_handler_interviews_page_create_and_job_detail_entry(tmp_path):
    config_path = write_config(tmp_path)
    job_body = json.dumps({"job": make_payload()["jobs"][0]["extension_json"]}, ensure_ascii=False).encode("utf-8")

    with run_test_server(config_path) as port:
        _, _, saved = request(
            port,
            "POST",
            "/jobs/save",
            body=job_body,
            headers={"Content-Type": "application/json"},
        )
        interview_body = json.dumps(
            {
                "job_key": saved["job"]["job_key"],
                "round_name": "一面",
                "interview_type": "视频",
                "result": "待反馈",
                "performance_score": "70",
                "summary": "Java 基础还行，JVM 要补。",
                "tracking_status": "面试中",
                "questions": [
                    {
                        "question": "HashMap 扩容过程？",
                        "skills": "Java, 集合",
                        "performance_score": "78",
                        "answer_summary": "细节基本覆盖",
                    },
                    {
                        "question": "JVM 线上 CPU 高怎么排查？",
                        "skills": "JVM, Java",
                        "performance_score": "45",
                        "answer_summary": "缺少真实案例",
                    },
                ],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        status, _, created = request(
            port,
            "POST",
            "/interviews",
            body=interview_body,
            headers={"Content-Type": "application/json"},
        )
        assert status == 200
        assert created["interview"]["round_name"] == "一面"
        assert len(created["interview"]["questions"]) == 2

        status, _, payload = request(port, "GET", "/interviews")
        assert status == 200
        assert payload["interviews"][0]["question_count"] == 2
        assert any(item["skill_name"] == "Java" and item["asked_count"] == 2 for item in payload["skill_stats"])
        assert any(item["skill_name"] == "JVM" and item["weak_count"] == 1 for item in payload["skill_stats"])

        status, headers, page = request(port, "GET", "/interviews/page")
        assert status == 200
        assert "text/html" in headers["Content-Type"]
        assert "interview-page-form" in page
        assert "question-editor" in page
        assert '<select name="round_name">' in page
        assert '<select name="interview_type">' in page
        assert '<select name="result">' in page
        assert '<select name="tracking_status">' in page
        assert "技术终面" in page
        assert "在线笔试" in page
        assert 'class="side-link active" href="/interviews/page"' in page

        status, _, jobs_payload = request(port, "GET", "/jobs?include_unfavorited=1")
        assert status == 200
        assert jobs_payload["jobs"][0]["tracking_status"] == "面试中"

        status, _, detail_page = request(
            port,
            "GET",
            "/jobs/detail?job_key=" + quote(saved["job"]["job_key"], safe=""),
        )
        assert status == 200
        assert "job-detail-interview-form" in detail_page
        assert "HashMap" in detail_page


def test_handler_job_detail_page_shows_clean_description(tmp_path):
    config_path = write_config(tmp_path)
    job_data = dict(make_payload()["jobs"][0]["extension_json"])
    job_data["description"] = (
        "高级Java17-27K 广州 5-10年 本科 职位描述：\nJava\n知识库\n团队管理经验\nSpringCloud\nMySQL\nAI\nSpring\n"
        "YiSkaYF{display:inline-block;width:0.1px;height:0.1px;overflow:hidden;visibility:hidden;}"
        "AtAWrBQspQF{font-style:normal;font-weight:normal;}"
        "岗位职责：1.负责系统开发；2.解决疑难问题；知识技能：1.熟悉 MySQL；2.熟悉 Spring。任职要求：1.有业务理解能力。"
        "\n竞争力分析\n这些内容来自 Boss 附加模块，不应该进入职位描述。"
    )
    body = json.dumps({"job": job_data}, ensure_ascii=False).encode("utf-8")

    with run_test_server(config_path) as port:
        _, _, saved = request(
            port,
            "POST",
            "/jobs/save",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        status, headers, payload = request(
            port,
            "GET",
            "/jobs/detail?job_key=" + quote(saved["job"]["job_key"], safe=""),
        )

    assert status == 200
    assert "text/html" in headers["Content-Type"]
    assert "职位描述" in payload
    assert "岗位职责" in payload
    assert "SpringCloud" in payload
    assert "<span>Java</span>" in payload
    assert "description-tags" in payload
    assert "tag-section" in payload
    assert "<h3>知识技能</h3>" in payload
    assert "任职要求" in payload
    assert "职位描述：" not in payload
    assert "高级Java17-27K" not in payload
    assert "title-row" in payload
    assert 'class="side-nav"' in payload
    assert 'class="side-link active" href="/jobs/page"' in payload
    assert "/jobs/page" in payload
    assert "匹配分析" in payload
    assert "match-analysis" in payload
    assert "C端匹配" in payload
    assert "chips" in payload
    assert "salary" in payload
    assert "description-body" in payload
    assert "description-list" in payload
    assert "<pre>" not in payload
    assert "display:inline-block" not in payload
    assert "YiSkaYF" not in payload
    assert "font-style" not in payload
    assert "AtAWrBQspQF" not in payload
    assert "竞争力分析" not in payload
    assert "附加模块" not in payload
