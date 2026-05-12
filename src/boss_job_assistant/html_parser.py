from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from boss_job_assistant.models import JobPosting


BOSS_BASE_URL = "https://www.zhipin.com"


@dataclass
class HtmlNode:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["HtmlNode"] = field(default_factory=list)
    data: list[str] = field(default_factory=list)

    def text(self) -> str:
        parts = self.data[:]
        for child in self.children:
            parts.append(child.text())
        return " ".join(part.strip() for part in parts if part.strip())

    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def find_all(self, predicate) -> list["HtmlNode"]:
        matches = [self] if predicate(self) else []
        for child in self.children:
            matches.extend(child.find_all(predicate))
        return matches


class TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HtmlNode("document")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = HtmlNode(tag=tag, attrs={key: value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.stack[-1].data.append(data)


def _has_class(node: HtmlNode, *class_names: str) -> bool:
    classes = node.classes()
    return any(class_name in classes for class_name in class_names)


def _first_text(node: HtmlNode, *class_names: str) -> str:
    matches = node.find_all(lambda item: _has_class(item, *class_names))
    return matches[0].text() if matches else ""


def _list_text(node: HtmlNode, *class_names: str) -> list[str]:
    containers = node.find_all(lambda item: _has_class(item, *class_names))
    values: list[str] = []
    for container in containers:
        for child in container.find_all(lambda item: item.tag in {"li", "span", "p"}):
            text = child.text()
            if text and text not in values:
                values.append(text)
    return values


def _first_job_href(node: HtmlNode) -> str:
    links = node.find_all(lambda item: item.tag == "a" and item.attrs.get("href"))
    for link in links:
        href = link.attrs["href"]
        if "/job_detail/" in href:
            return urljoin(BOSS_BASE_URL, href)
    if links:
        return urljoin(BOSS_BASE_URL, links[0].attrs["href"])
    return ""


def parse_jobs_from_html(html: str) -> list[JobPosting]:
    parser = TreeParser()
    parser.feed(html)

    cards = parser.root.find_all(
        lambda node: _has_class(node, "job-card-wrapper", "job-card-box")
    )
    jobs: list[JobPosting] = []

    for card in cards:
        tags = _list_text(card, "tag-list", "job-card-footer")
        company_info = _list_text(card, "company-tag-list", "company-info")
        description = card.text()

        jobs.append(
            JobPosting(
                title=_first_text(card, "job-name", "job-title"),
                salary=_first_text(card, "salary"),
                location=_first_text(card, "job-area", "job-location"),
                experience=tags[0] if len(tags) > 0 else "",
                education=tags[1] if len(tags) > 1 else "",
                company=_first_text(card, "company-name"),
                industry=company_info[0] if len(company_info) > 0 else "",
                financing=company_info[1] if len(company_info) > 1 else "",
                company_size=company_info[2] if len(company_info) > 2 else "",
                url=_first_job_href(card),
                description=description,
            )
        )

    return jobs


def parse_jobs_from_html_file(path: str | Path) -> list[JobPosting]:
    html_path = Path(path)
    return parse_jobs_from_html(html_path.read_text(encoding="utf-8", errors="ignore"))
