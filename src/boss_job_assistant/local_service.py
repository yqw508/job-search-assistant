import json
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from pathlib import Path
from typing import Any

from boss_job_assistant.config import load_config
from boss_job_assistant.exporter import export_jobs
from boss_job_assistant.models import JobPosting
from boss_job_assistant.scorer import score_job


HOST = "127.0.0.1"
PORT = 8765
MAX_BODY_BYTES = 2 * 1024 * 1024

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
    "url",
    "description",
)


class ClientInputError(ValueError):
    pass


def _safe_str(value: Any) -> str:
    return str(value if value is not None else "")


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
    if not isinstance(raw_jobs, list):
        return []

    jobs = []
    for item in raw_jobs:
        job_data = _job_data_from_item(item)
        jobs.append(
            JobPosting(**{field: _safe_str(job_data.get(field, "")) for field in JOB_FIELDS})
        )

    return jobs


def build_response(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    jobs = jobs_from_payload(payload)
    if not jobs:
        return {"ok": False, "error": "没有收到岗位数据"}

    scored_jobs = [score_job(job, config) for job in jobs]
    output_file = export_jobs(scored_jobs, config["runtime"]["output_dir"])

    return {
        "ok": True,
        "received": len(jobs),
        "matched": sum(1 for scored_job in scored_jobs if scored_job.matched),
        "output_file": str(Path(output_file).resolve()),
    }


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


class LocalServiceHandler(BaseHTTPRequestHandler):
    config_path = "config.yaml"

    def _set_headers(self, status_code: int = 200) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
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

    def _read_json_payload(self) -> dict[str, Any]:
        content_length_text = self.headers.get("Content-Length", "0") or "0"
        try:
            content_length = int(content_length_text)
        except ValueError as exc:
            raise ClientInputError("请求数据格式不正确") from exc

        if content_length < 0 or content_length > MAX_BODY_BYTES:
            raise ClientInputError("请求数据过大或格式不正确")

        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ClientInputError("请求 JSON 格式不正确") from exc

        if not isinstance(payload, dict):
            raise ClientInputError("请求数据格式不正确")

        return payload

    def do_OPTIONS(self) -> None:
        self._set_headers()

    def do_GET(self) -> None:
        if self.path == "/health":
            self._write_json({"ok": True, "service": "boss-job-assistant"})
            return

        self._write_json({"ok": False, "error": "Not Found"}, 404)

    def do_POST(self) -> None:
        if self.path != "/jobs/export":
            self._write_json({"ok": False, "error": "Not Found"}, 404)
            return

        try:
            payload = self._read_json_payload()
            config = load_config(self.config_path)
            response = build_response(payload, config)
            self._write_json(response, 200 if response.get("ok") else 400)
        except ClientInputError as exc:
            self._write_json({"ok": False, "error": str(exc)}, 400)
        except Exception as exc:  # noqa: BLE001 - local service should report JSON errors.
            print(f"本地服务处理请求失败: {exc}")
            traceback.print_exc()
            self._write_json({"ok": False, "error": "服务处理失败，请稍后重试"}, 500)


def run_server(config_path: str = "config.yaml", host: str = HOST, port: int = PORT) -> None:
    if not _is_loopback_host(host):
        raise ValueError("本地服务只允许监听 127.0.0.1、localhost 或 loopback 地址")

    LocalServiceHandler.config_path = config_path
    server = ThreadingHTTPServer((host, port), LocalServiceHandler)
    print(f"本地服务已启动: http://{host}:{port}")
    print("健康检查: GET /health；导出岗位: POST /jobs/export")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
