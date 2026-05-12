# Boss 浏览器扩展岗位助手 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 Chrome/Edge 浏览器扩展 + 本地 Python 服务，让用户在正常 Boss 页面点击扩展按钮即可采集岗位、评分并导出 Excel。

**Architecture:** 扩展运行在用户正常浏览器会话中，只读取页面上已展示的岗位 DOM，并通过 `http://127.0.0.1:8765` 发送给本地 Python 服务。本地服务复用现有 `JobPosting`、`score_job`、`export_jobs` 和 `config.yaml`，负责评分、导出和返回结果。

**Tech Stack:** Python 3.10+ 标准库 `http.server`、Chrome Manifest V3、JavaScript DOM API、现有 openpyxl/PyYAML/pytest。

---

## File Structure

- Create: `src/boss_job_assistant/local_service.py`，本地 HTTP 服务。
- Create: `tests/test_local_service.py`，服务请求解析和导出接口测试。
- Create: `start_service.bat`，启动本地服务。
- Create: `extension/manifest.json`，扩展声明。
- Create: `extension/popup.html`，扩展弹窗 UI。
- Create: `extension/popup.js`，弹窗交互和调用本地服务。
- Create: `extension/content.js`，Boss 页面 DOM 采集和低频翻页。
- Create: `tests/extension/content_parser_test.js`，content.js 纯解析函数测试。
- Modify: `README.md`，加入扩展安装和使用说明。

Existing reusable files:

- `src/boss_job_assistant/models.py`
- `src/boss_job_assistant/config.py`
- `src/boss_job_assistant/scorer.py`
- `src/boss_job_assistant/exporter.py`
- `config.yaml`

---

### Task 1: Local Service Core

**Files:**
- Create: `src/boss_job_assistant/local_service.py`
- Create: `tests/test_local_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_local_service.py`:

```python
import json
from pathlib import Path

from openpyxl import load_workbook

from boss_job_assistant.local_service import build_response, jobs_from_payload


def test_jobs_from_payload_converts_extension_json():
    payload = {
        "source": "boss-extension",
        "jobs": [
            {
                "title": "Java 后端开发工程师",
                "salary": "25-35K",
                "location": "广州",
                "experience": "5-10年",
                "education": "本科",
                "company": "示例公司",
                "industry": "电商",
                "financing": "B轮",
                "company_size": "100-499人",
                "url": "https://www.zhipin.com/job_detail/example.html",
                "description": "Java Spring Boot C端交易系统",
            }
        ],
    }

    jobs = jobs_from_payload(payload)

    assert len(jobs) == 1
    assert jobs[0].title == "Java 后端开发工程师"
    assert jobs[0].company_size == "100-499人"


def test_build_response_scores_and_exports(tmp_path: Path):
    config = {
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
        "runtime": {"output_dir": str(tmp_path)},
    }
    payload = {
        "jobs": [
            {
                "title": "Java 后端开发工程师",
                "salary": "25-35K",
                "location": "广州",
                "company_size": "100-499人",
                "description": "Java Spring Boot C端交易系统 Redis",
            }
        ]
    }

    response = build_response(payload, config)

    assert response["ok"] is True
    assert response["received"] == 1
    assert response["matched"] == 1
    output_file = Path(response["output_file"])
    assert output_file.exists()
    workbook = load_workbook(output_file)
    assert workbook.active["A2"].value == "匹配"


def test_build_response_rejects_empty_jobs(tmp_path: Path):
    config = {
        "filters": {"min_salary_k": 22, "min_company_size": 100, "required_location": "广州"},
        "scoring": {"positive_keywords": [], "c_side_keywords": [], "exclude_keywords": []},
        "runtime": {"output_dir": str(tmp_path)},
    }

    response = build_response({"jobs": []}, config)

    assert response["ok"] is False
    assert "没有收到岗位数据" in response["error"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_local_service.py -v --basetemp D:\future\.tmp\pytest
```

Expected: FAIL because `local_service.py` does not exist.

- [ ] **Step 3: Implement service functions and HTTP handler**

Create `src/boss_job_assistant/local_service.py`:

```python
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from boss_job_assistant.config import load_config
from boss_job_assistant.exporter import export_jobs
from boss_job_assistant.models import JobPosting
from boss_job_assistant.scorer import score_job


HOST = "127.0.0.1"
PORT = 8765


def jobs_from_payload(payload: dict[str, Any]) -> list[JobPosting]:
    jobs = []
    for item in payload.get("jobs", []):
        jobs.append(
            JobPosting(
                title=str(item.get("title", "") or ""),
                salary=str(item.get("salary", "") or ""),
                location=str(item.get("location", "") or ""),
                experience=str(item.get("experience", "") or ""),
                education=str(item.get("education", "") or ""),
                company=str(item.get("company", "") or ""),
                industry=str(item.get("industry", "") or ""),
                financing=str(item.get("financing", "") or ""),
                company_size=str(item.get("company_size", "") or ""),
                url=str(item.get("url", "") or ""),
                description=str(item.get("description", "") or ""),
            )
        )
    return jobs


def build_response(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    jobs = jobs_from_payload(payload)
    if not jobs:
        return {"ok": False, "error": "没有收到岗位数据"}

    scored_jobs = [score_job(job, config) for job in jobs]
    output_file = export_jobs(scored_jobs, config["runtime"]["output_dir"])
    matched = sum(1 for item in scored_jobs if item.matched)

    return {
        "ok": True,
        "received": len(scored_jobs),
        "matched": matched,
        "output_file": str(Path(output_file).resolve()),
    }


class LocalServiceHandler(BaseHTTPRequestHandler):
    config_path = "config.yaml"

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self._send_json(200, {"ok": True})

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"ok": True, "service": "boss-job-assistant"})
            return
        self._send_json(404, {"ok": False, "error": "接口不存在"})

    def do_POST(self) -> None:
        if self.path != "/jobs/export":
            self._send_json(404, {"ok": False, "error": "接口不存在"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            config = load_config(self.config_path)
            response = build_response(payload, config)
            self._send_json(200 if response.get("ok") else 400, response)
        except Exception as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})


def run_server(config_path: str = "config.yaml", host: str = HOST, port: int = PORT) -> None:
    LocalServiceHandler.config_path = config_path
    server = ThreadingHTTPServer((host, port), LocalServiceHandler)
    print(f"Boss 岗位助手本地服务已启动: http://{host}:{port}")
    print("请在 Chrome/Edge 中打开 Boss 搜索页，然后点击扩展按钮采集岗位。")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_local_service.py -v --basetemp D:\future\.tmp\pytest
```

Expected: PASS.

---

### Task 2: Service Startup Script

**Files:**
- Create: `start_service.bat`

- [ ] **Step 1: Create startup script**

Create `start_service.bat`:

```bat
@echo off
setlocal

cd /d "%~dp0"

set "SSLKEYLOGFILE="
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

echo [1/3] Checking Python...
python --version
if errorlevel 1 (
    echo Python was not found. Please install Python 3.10 or newer.
    pause
    exit /b 1
)

echo [2/3] Checking Python packages...
python -c "import importlib.util, sys; mods={'PyYAML':'yaml','openpyxl':'openpyxl'}; missing=[name for name,mod in mods.items() if importlib.util.find_spec(mod) is None]; print('Missing packages: ' + ', '.join(missing) if missing else 'Required packages are installed.'); sys.exit(1 if missing else 0)"
if errorlevel 1 (
    python -m pip install PyYAML>=6.0.1 openpyxl>=3.1.2
    if errorlevel 1 (
        echo Failed to install required packages.
        pause
        exit /b 1
    )
)

echo [3/3] Starting local service...
python -m boss_job_assistant.local_service

pause
```

- [ ] **Step 2: Static check script content**

Run:

```powershell
python -c "from pathlib import Path; text=Path('start_service.bat').read_text(); assert 'local_service' in text and 'PYTHONPATH' in text; print('script ok')"
```

Expected: `script ok`.

---

### Task 3: Extension Manifest And Popup

**Files:**
- Create: `extension/manifest.json`
- Create: `extension/popup.html`

- [ ] **Step 1: Create manifest**

Create `extension/manifest.json`:

```json
{
  "manifest_version": 3,
  "name": "Boss 岗位助手",
  "version": "0.1.0",
  "description": "采集当前 Boss 搜索页岗位并发送到本地服务导出 Excel。",
  "permissions": ["activeTab", "scripting"],
  "host_permissions": [
    "https://www.zhipin.com/*",
    "http://127.0.0.1:8765/*"
  ],
  "action": {
    "default_title": "Boss 岗位助手",
    "default_popup": "popup.html"
  },
  "content_scripts": [
    {
      "matches": ["https://www.zhipin.com/*"],
      "js": ["content.js"],
      "run_at": "document_idle"
    }
  ]
}
```

- [ ] **Step 2: Create popup HTML**

Create `extension/popup.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>Boss 岗位助手</title>
    <style>
      body {
        width: 320px;
        margin: 0;
        padding: 12px;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: #1f2937;
      }
      h1 {
        margin: 0 0 12px;
        font-size: 16px;
      }
      label {
        display: block;
        margin: 8px 0 4px;
        font-size: 12px;
      }
      input {
        width: 72px;
        padding: 4px;
      }
      button {
        width: 100%;
        margin-top: 10px;
        padding: 8px;
        border: 0;
        border-radius: 6px;
        background: #2563eb;
        color: white;
        cursor: pointer;
      }
      button:disabled {
        background: #9ca3af;
        cursor: not-allowed;
      }
      #status {
        margin-top: 10px;
        white-space: pre-wrap;
        font-size: 12px;
        line-height: 1.5;
      }
    </style>
  </head>
  <body>
    <h1>Boss 岗位助手</h1>
    <label for="pages">最多采集页数，1-3</label>
    <input id="pages" type="number" min="1" max="3" value="1" />
    <button id="collect">采集并导出 Excel</button>
    <div id="status">请先启动本地服务，并打开 Boss 搜索结果页。</div>
    <script src="popup.js"></script>
  </body>
</html>
```

- [ ] **Step 3: Validate JSON**

Run:

```powershell
python -m json.tool extension/manifest.json
```

Expected: formatted JSON printed with exit code 0.

---

### Task 4: Content Script DOM Collection

**Files:**
- Create: `extension/content.js`
- Create: `tests/extension/content_parser_test.js`

- [ ] **Step 1: Create content script**

Create `extension/content.js`:

```javascript
function textOf(root, selector) {
  const el = root.querySelector(selector);
  return el ? el.textContent.trim().replace(/\s+/g, " ") : "";
}

function listText(root, selector) {
  return Array.from(root.querySelectorAll(selector))
    .map((el) => el.textContent.trim().replace(/\s+/g, " "))
    .filter(Boolean);
}

function absoluteUrl(href) {
  if (!href) return "";
  return new URL(href, location.origin).href;
}

function parseJobCard(card) {
  const tags = listText(card, ".tag-list li, .job-card-footer li");
  const companyInfo = listText(card, ".company-tag-list li, .company-info li");
  const link = card.querySelector('a[href*="/job_detail/"]') || card.querySelector("a[href]");

  return {
    title: textOf(card, ".job-name, .job-title"),
    salary: textOf(card, ".salary"),
    location: textOf(card, ".job-area, .job-location"),
    experience: tags[0] || "",
    education: tags[1] || "",
    company: textOf(card, ".company-name"),
    industry: companyInfo[0] || "",
    financing: companyInfo[1] || "",
    company_size: companyInfo[2] || "",
    url: absoluteUrl(link ? link.getAttribute("href") : ""),
    description: card.textContent.trim().replace(/\s+/g, " ").slice(0, 1000)
  };
}

function collectCurrentPageJobs() {
  const cards = Array.from(document.querySelectorAll(".job-card-wrapper, .job-card-box"));
  return cards.map(parseJobCard).filter((job) => job.title || job.company || job.url);
}

function findNextButton() {
  const candidates = Array.from(document.querySelectorAll("a, button"));
  return candidates.find((el) => /下一页|下页|next/i.test(el.textContent || ""));
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function collectJobs(maxPages) {
  const seen = new Set();
  const jobs = [];
  const pages = Math.max(1, Math.min(Number(maxPages) || 1, 3));

  for (let page = 0; page < pages; page += 1) {
    for (const job of collectCurrentPageJobs()) {
      const key = job.url || `${job.title}-${job.company}-${job.salary}`;
      if (!seen.has(key)) {
        seen.add(key);
        jobs.push(job);
      }
    }

    if (page >= pages - 1) break;
    const next = findNextButton();
    if (!next) break;
    next.click();
    await sleep(2500);
  }

  return jobs;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type !== "COLLECT_BOSS_JOBS") return false;

  collectJobs(message.maxPages)
    .then((jobs) => sendResponse({ ok: true, jobs }))
    .catch((error) => sendResponse({ ok: false, error: String(error) }));

  return true;
});

if (typeof module !== "undefined") {
  module.exports = { parseJobCard, collectCurrentPageJobs };
}
```

- [ ] **Step 2: Create Node parser test**

Create `tests/extension/content_parser_test.js`:

```javascript
const assert = require("node:assert");
const { JSDOM } = require("jsdom");

global.location = new URL("https://www.zhipin.com/web/geek/job");
global.chrome = { runtime: { onMessage: { addListener() {} } } };

const { parseJobCard } = require("../../extension/content.js");

const dom = new JSDOM(`
  <div class="job-card-wrapper">
    <a href="/job_detail/example.html">
      <span class="job-name">Java 后端开发工程师</span>
      <span class="salary">25-35K</span>
      <span class="job-area">广州</span>
    </a>
    <ul class="tag-list"><li>5-10年</li><li>本科</li></ul>
    <div class="company-name">示例公司</div>
    <ul class="company-tag-list"><li>电商</li><li>B轮</li><li>100-499人</li></ul>
  </div>
`);

const card = dom.window.document.querySelector(".job-card-wrapper");
const job = parseJobCard(card);

assert.equal(job.title, "Java 后端开发工程师");
assert.equal(job.salary, "25-35K");
assert.equal(job.location, "广州");
assert.equal(job.company, "示例公司");
assert.equal(job.company_size, "100-499人");
assert.equal(job.url, "https://www.zhipin.com/job_detail/example.html");

console.log("content parser test passed");
```

- [ ] **Step 3: Run parser test if jsdom is available**

Run:

```powershell
node tests/extension/content_parser_test.js
```

Expected: If `jsdom` is installed, prints `content parser test passed`. If `jsdom` is missing, note that extension parser is manually tested or add `package.json` in a follow-up.

---

### Task 5: Popup Script And Service Integration

**Files:**
- Create: `extension/popup.js`

- [ ] **Step 1: Create popup script**

Create `extension/popup.js`:

```javascript
const SERVICE_URL = "http://127.0.0.1:8765";

const statusEl = document.getElementById("status");
const collectButton = document.getElementById("collect");
const pagesInput = document.getElementById("pages");

function setStatus(text) {
  statusEl.textContent = text;
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function checkService() {
  const response = await fetch(`${SERVICE_URL}/health`);
  if (!response.ok) throw new Error("本地服务未启动");
  return response.json();
}

async function collectFromTab(tab, maxPages) {
  return chrome.tabs.sendMessage(tab.id, {
    type: "COLLECT_BOSS_JOBS",
    maxPages
  });
}

async function exportJobs(jobs) {
  const response = await fetch(`${SERVICE_URL}/jobs/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source: "boss-extension", jobs })
  });
  return response.json();
}

collectButton.addEventListener("click", async () => {
  collectButton.disabled = true;
  try {
    setStatus("正在检查本地服务...");
    await checkService();

    const tab = await getActiveTab();
    if (!tab || !tab.url || !tab.url.includes("zhipin.com")) {
      throw new Error("请先打开 Boss 搜索结果页");
    }

    const maxPages = Math.max(1, Math.min(Number(pagesInput.value) || 1, 3));
    setStatus(`正在采集，最多 ${maxPages} 页...`);
    const collected = await collectFromTab(tab, maxPages);
    if (!collected || !collected.ok) {
      throw new Error(collected && collected.error ? collected.error : "页面采集失败");
    }
    if (!collected.jobs.length) {
      throw new Error("没有采集到岗位，请确认岗位列表已加载");
    }

    setStatus(`采集到 ${collected.jobs.length} 个岗位，正在导出 Excel...`);
    const result = await exportJobs(collected.jobs);
    if (!result.ok) {
      throw new Error(result.error || "导出失败");
    }

    setStatus(`导出成功
采集岗位: ${result.received}
匹配岗位: ${result.matched}
文件: ${result.output_file}`);
  } catch (error) {
    setStatus(`失败: ${error.message || error}`);
  } finally {
    collectButton.disabled = false;
  }
});

checkService()
  .then(() => setStatus("本地服务已连接。打开 Boss 搜索页后点击采集。"))
  .catch(() => setStatus("本地服务未启动，请先运行 start_service.bat。"));
```

- [ ] **Step 2: Manual load check**

Open `extension/popup.html` in a browser file tab only to verify it renders. Full extension behavior is tested manually after loading unpacked extension.

---

### Task 6: README And Extension Install Guide

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Add a “浏览器扩展模式” section to `README.md`:

```markdown
## 浏览器扩展模式，推荐

1. 运行 `start_service.bat`。
2. 打开 Chrome 或 Edge 的扩展管理页。
3. 开启开发者模式。
4. 点击“加载已解压的扩展程序”。
5. 选择项目里的 `extension` 文件夹。
6. 正常打开 Boss 搜索结果页。
7. 点击工具栏里的“Boss 岗位助手”扩展。
8. 选择采集页数，点击“采集并导出 Excel”。

扩展只读取当前页面展示的岗位信息，并发送到本机 `127.0.0.1:8765`。如果提示本地服务未启动，请先运行 `start_service.bat`。
```

- [ ] **Step 2: Run full Python tests**

Run:

```powershell
python -m pytest -v --basetemp D:\future\.tmp\pytest
```

Expected: all Python tests PASS.

---

### Task 7: Manual End-To-End Verification

**Files:**
- No code changes unless verification finds a bug.

- [ ] **Step 1: Start local service**

Run:

```powershell
.\start_service.bat
```

Expected:

```text
Boss 岗位助手本地服务已启动: http://127.0.0.1:8765
```

- [ ] **Step 2: Check health endpoint**

Run in another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
```

Expected:

```text
ok service
-- -------
True boss-job-assistant
```

- [ ] **Step 3: Load extension**

In Chrome or Edge:

1. Open extension management page.
2. Enable developer mode.
3. Load unpacked extension.
4. Select `D:\future\extension`.

Expected: Extension appears as “Boss 岗位助手”.

- [ ] **Step 4: Test on Boss search page**

1. Open Boss normally.
2. Search `Java Spring Boot` in Guangzhou.
3. Click extension.
4. Set pages to `1`.
5. Click “采集并导出 Excel”.

Expected:

- Popup shows export success.
- `output/boss_jobs_*.xlsx` exists.
- Excel contains rows with job title, salary, company, score, matched/excluded status.

---

## Self-Review

- Spec coverage: covers local service, startup script, extension manifest, popup UI, content script collection, local export, README, and manual verification.
- Placeholder scan: no `TODO`, `TBD`, or incomplete “fill later” instructions.
- Type consistency: extension sends snake_case fields matching `JobPosting`; service returns `ok`, `received`, `matched`, and `output_file` as specified.
- Scope check: first version stays focused on current page and low-frequency 1-3 page collection. It does not implement auto-apply, chat, captcha bypass, or direct Boss API calls.
