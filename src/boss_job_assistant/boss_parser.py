from __future__ import annotations

try:
    from playwright.sync_api import Page
except ImportError:
    from typing import Any as Page

from boss_job_assistant.models import JobPosting


BOSS_BASE_URL = "https://www.zhipin.com"


def _absolute_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("http"):
        return url
    return f"{BOSS_BASE_URL}{url}"


def _first_text(locator, selector: str) -> str:
    try:
        child = locator.locator(selector)
        if child.count() == 0:
            return ""
        return child.first.inner_text().strip()
    except Exception:
        return ""


def _safe_inner_text(page: Page, selector: str) -> str:
    try:
        locator = page.locator(selector)
        if locator.count() == 0:
            return ""
        return locator.first.inner_text().strip()
    except Exception:
        return ""


def _texts(locator, selector: str) -> list[str]:
    try:
        items = locator.locator(selector)
        return [items.nth(index).inner_text().strip() for index in range(items.count())]
    except Exception:
        return []


def _first_href(locator, selector: str) -> str:
    try:
        links = locator.locator(selector)
        if links.count() == 0:
            return ""
        return links.first.get_attribute("href") or ""
    except Exception:
        return ""


def parse_job_cards(page: Page) -> list[JobPosting]:
    jobs: list[JobPosting] = []

    try:
        cards = page.locator(".job-card-wrapper, .job-card-box")
        card_count = cards.count()
    except Exception:
        return jobs

    for index in range(card_count):
        card = cards.nth(index)
        href = _first_href(card, 'a[href*="/job_detail/"]') or _first_href(card, "a")
        url = _absolute_url(href)
        tags = _texts(card, ".tag-list li, .job-card-footer li")
        company_info = _texts(card, ".company-tag-list li, .company-info li")

        jobs.append(
            JobPosting(
                title=_first_text(card, ".job-name, .job-title"),
                salary=_first_text(card, ".salary"),
                location=_first_text(card, ".job-area, .job-location"),
                experience=tags[0] if len(tags) > 0 else "",
                education=tags[1] if len(tags) > 1 else "",
                company=_first_text(card, ".company-name"),
                industry=company_info[0] if len(company_info) > 0 else "",
                financing=company_info[1] if len(company_info) > 1 else "",
                company_size=company_info[2] if len(company_info) > 2 else "",
                url=url,
            )
        )

    return jobs


def fill_detail(page: Page, job: JobPosting) -> JobPosting:
    if not job.url:
        return job

    try:
        page.goto(job.url, wait_until="domcontentloaded")
        page.wait_for_timeout(1000)
    except Exception as exc:
        print(f"Warning: failed to load job detail {job.url}: {exc}")
        return job

    try:
        description = _safe_inner_text(page, ".job-sec-text, .job-detail-section")
        if description:
            job.description = description

        if not job.company_size:
            for selector in (
                '.sider-company p:has-text("人")',
                ".company-scale",
                '.company-info:has-text("人")',
            ):
                company_size = _safe_inner_text(page, selector)
                if company_size:
                    job.company_size = company_size
                    break
    except Exception as exc:
        print(f"Warning: failed to parse job detail {job.url}: {exc}")

    return job
