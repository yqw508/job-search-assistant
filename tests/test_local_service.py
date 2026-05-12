import json
import threading
from contextlib import contextmanager
from email.message import Message
from http.client import HTTPConnection
from pathlib import Path

import pytest
from openpyxl import load_workbook

from boss_job_assistant.local_service import (
    HOST,
    MAX_BODY_BYTES,
    ClientInputError,
    LocalServiceHandler,
    ThreadingHTTPServer,
    build_response,
    jobs_from_payload,
)


def make_payload() -> dict:
    return {
        "jobs": [
            {
                "extension_json": {
                    "title": "Java 后端开发工程师",
                    "salary": "25-35K",
                    "location": "广州",
                    "company_size": "100-499人",
                    "description": "Java Spring Boot C端交易系统",
                }
            }
        ]
    }


def make_config(output_dir: Path) -> dict:
    return {
        "filters": {
            "min_salary_k": 22,
            "min_company_size": 100,
            "required_location": "广州",
        },
        "scoring": {
            "positive_keywords": ["Java", "Spring Boot", "Redis"],
            "c_side_keywords": ["C端", "交易"],
            "exclude_keywords": ["外包"],
        },
        "runtime": {"output_dir": str(output_dir)},
    }


def test_jobs_from_payload_converts_extension_json():
    jobs = jobs_from_payload(make_payload())

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Java 后端开发工程师"
    assert job.salary == "25-35K"
    assert job.location == "广州"
    assert job.company_size == "100-499人"
    assert job.description == "Java Spring Boot C端交易系统"


def test_build_response_scores_and_exports(tmp_path):
    response = build_response(make_payload(), make_config(tmp_path))

    assert response["ok"] is True
    assert response["received"] == 1
    assert response["matched"] == 1

    output_file = Path(response["output_file"])
    assert output_file.is_absolute()
    assert output_file.exists()

    workbook = load_workbook(output_file)
    assert workbook.active["A2"].value == "匹配"


def test_build_response_rejects_empty_jobs(tmp_path):
    response = build_response({"jobs": []}, make_config(tmp_path))

    assert response["ok"] is False
    assert "没有收到岗位数据" in response["error"]


@contextmanager
def run_test_server():
    server = ThreadingHTTPServer((HOST, 0), LocalServiceHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request(port: int, method: str, path: str, body: bytes | None = None, headers=None):
    connection = HTTPConnection(HOST, port, timeout=5)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        response_body = response.read().decode("utf-8")
        return response.status, dict(response.headers), json.loads(response_body)
    finally:
        connection.close()


def test_handler_health_returns_json():
    with run_test_server() as port:
        status, _, payload = request(port, "GET", "/health")

    assert status == 200
    assert payload == {"ok": True, "service": "boss-job-assistant"}


def test_handler_unknown_path_returns_404():
    with run_test_server() as port:
        status, _, payload = request(port, "GET", "/missing")

    assert status == 404
    assert payload["ok"] is False


def test_handler_malformed_json_returns_400():
    with run_test_server() as port:
        status, _, payload = request(
            port,
            "POST",
            "/jobs/export",
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
