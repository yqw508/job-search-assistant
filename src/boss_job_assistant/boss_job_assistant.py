from __future__ import annotations

import random
import sys
import os
from pathlib import Path
from urllib.parse import quote

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:
    PlaywrightError = RuntimeError
    PlaywrightTimeoutError = TimeoutError
    sync_playwright = None

from boss_job_assistant.boss_parser import fill_detail, parse_job_cards
from boss_job_assistant.config import load_config
from boss_job_assistant.exporter import export_jobs
from boss_job_assistant.scorer import score_job


BOSS_HOME_URL = "https://www.zhipin.com"
JOB_CARD_SELECTOR = ".job-card-wrapper, .job-card-box, .job-list-box"
USER_DATA_DIR = Path(".browser-profile")


def _search_url(keyword: str, city: str, city_code: str | None = None) -> str:
    city_value = city_code or city
    return (
        "https://www.zhipin.com/web/geek/job"
        f"?query={quote(keyword)}&city={quote(str(city_value))}"
    )


def _sleep(page, config: dict) -> None:
    runtime = config.get("runtime", {})
    min_delay = float(runtime.get("min_delay_seconds", 1) or 0)
    max_delay = float(runtime.get("max_delay_seconds", min_delay) or min_delay)
    if max_delay < min_delay:
        min_delay, max_delay = max_delay, min_delay

    page.wait_for_timeout(int(random.uniform(min_delay, max_delay) * 1000))


def wait_for_login(page) -> None:
    print("请在打开的浏览器中手动登录 Boss。登录完成后回到终端按 Enter 继续。")
    input()
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except PlaywrightTimeoutError:
        pass


def _wait_for_job_cards(page) -> None:
    try:
        page.wait_for_selector(JOB_CARD_SELECTOR, timeout=15000)
    except PlaywrightTimeoutError:
        print("等待岗位列表超时，将尝试解析当前页面。")


def _open_detail_page(page, job):
    detail_page = page.context.new_page()
    try:
        return fill_detail(detail_page, job)
    except Exception as exc:
        print(f"详情页读取失败，保留列表数据: {getattr(job, 'url', '')}，原因: {exc}")
        return job
    finally:
        try:
            detail_page.close()
        except Exception:
            pass


def _next_page_button(page):
    selector = ".options-pages a:has-text('下一页'), a:has-text('下一页')"
    try:
        buttons = page.locator(selector)
        if buttons.count() == 0:
            return None
        return buttons.first
    except PlaywrightError:
        return None


def _raise_missing_playwright() -> None:
    raise RuntimeError(
        "缺少 Playwright Python 依赖，请先执行: pip install -r requirements.txt"
    )


def _launch_context(playwright):
    cdp_endpoint = os.environ.get("BOSS_CDP_ENDPOINT")
    if cdp_endpoint:
        browser = playwright.chromium.connect_over_cdp(cdp_endpoint)
        return browser.contexts[0] if browser.contexts else browser.new_context()

    browser_channel = os.environ.get("BOSS_BROWSER_CHANNEL")
    launch_options = {
        "headless": False,
        "slow_mo": 200,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ],
    }
    if browser_channel:
        launch_options["channel"] = browser_channel

    try:
        return playwright.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            **launch_options,
        )
    except PlaywrightError as exc:
        if browser_channel:
            message = f"无法启动本机浏览器通道 {browser_channel}，请确认 Chrome 或 Edge 已安装。"
        else:
            message = (
                "无法启动 Chromium 浏览器。请先执行: "
                "python -m playwright install chromium"
            )
        print(message)
        raise RuntimeError(message) from exc


def _first_page(context):
    if context.pages:
        return context.pages[0]
    return context.new_page()


def _current_page(context):
    non_blank_pages = [page for page in context.pages if page.url != "about:blank"]
    if non_blank_pages:
        return non_blank_pages[-1]
    return _first_page(context)


def _wait_for_manual_start(context, search_url: str):
    page = _first_page(context)
    print("浏览器已打开。为降低 Boss 自动化拦截，请手动完成下面几步：")
    print(f"1. 在浏览器地址栏粘贴并打开这个地址: {search_url}")
    print("2. 手动登录 Boss，并确认页面上已经出现岗位列表。")
    print("3. 回到这个终端，按 Enter，程序会读取当前页面。")
    input()
    page = _current_page(context)
    print(f"准备读取当前页面: {page.url}")
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except PlaywrightTimeoutError:
        pass
    return page


def run(config_path: str = "config.yaml") -> Path | None:
    if sync_playwright is None:
        _raise_missing_playwright()

    config = load_config(config_path)
    search = config.get("search", {})
    runtime = config.get("runtime", {})
    collected = []

    keyword = str(search.get("keyword", "") or "")
    city = str(search.get("city", "") or "")
    city_code = search.get("city_code")
    max_pages = int(search.get("max_pages", 1) or 1)
    detail_pages = bool(search.get("detail_pages", False))
    manual_start = bool(search.get("manual_start", True))
    using_cdp = bool(os.environ.get("BOSS_CDP_ENDPOINT"))

    context = None
    with sync_playwright() as playwright:
        try:
            context = _launch_context(playwright)
            search_url = _search_url(keyword, city, city_code)

            if manual_start:
                page = _wait_for_manual_start(context, search_url)
            else:
                page = _first_page(context)
                page.goto(BOSS_HOME_URL, wait_until="domcontentloaded")
                print(f"当前页面: {page.url}")
                wait_for_login(page)
                print(f"正在打开搜索页: {search_url}")
                page.goto(search_url, wait_until="domcontentloaded")
                print(f"当前页面: {page.url}")

            for page_number in range(1, max_pages + 1):
                print(f"正在采集第 {page_number} 页...")
                _sleep(page, config)
                _wait_for_job_cards(page)

                jobs = parse_job_cards(page)
                print(f"第 {page_number} 页读取到 {len(jobs)} 个岗位。")

                for job in jobs:
                    if detail_pages:
                        job = _open_detail_page(page, job)
                        _sleep(page, config)
                    collected.append(score_job(job, config))

                if page_number >= max_pages:
                    break

                next_button = _next_page_button(page)
                if next_button is None:
                    print("没有找到下一页按钮，停止采集。")
                    break

                try:
                    next_button.click()
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                except (PlaywrightTimeoutError, PlaywrightError) as exc:
                    print(f"下一页跳转失败，停止采集。原因: {exc}")
                    break
        finally:
            if context is not None and not using_cdp:
                context.close()

    if not collected:
        print("没有采集到岗位，请确认已登录、搜索条件有效，或页面结构未发生较大变化。")
        return None

    output_path = export_jobs(collected, runtime.get("output_dir", "output"))
    print(f"已导出 {len(collected)} 个岗位: {output_path}")
    return output_path


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "config.yaml")
