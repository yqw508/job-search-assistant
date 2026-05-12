from pathlib import Path

from boss_job_assistant.boss_parser import _absolute_url, fill_detail, parse_job_cards
from boss_job_assistant.models import JobPosting


class FakeLocator:
    def __init__(self, *, text="", attrs=None, children=None, items=None):
        self.text = text
        self.attrs = attrs or {}
        self.children = children or {}
        self.items = items

    @property
    def first(self):
        return self.nth(0)

    def count(self):
        return len(self.items) if self.items is not None else 1

    def nth(self, index):
        if self.items is None:
            if index != 0:
                raise IndexError(index)
            return self
        return self.items[index]

    def locator(self, selector):
        if selector in self.children:
            value = self.children[selector]
            if isinstance(value, list):
                return FakeLocator(items=value)
            return FakeLocator(items=[value])
        return FakeLocator(items=[])

    def inner_text(self):
        return self.text

    def get_attribute(self, name):
        return self.attrs.get(name)


def test_absolute_url():
    assert _absolute_url("") == ""
    assert _absolute_url("https://example.com/job") == "https://example.com/job"
    assert _absolute_url("/job_detail/x.html") == "https://www.zhipin.com/job_detail/x.html"


def test_parse_job_cards_reads_expected_fields():
    card = FakeLocator(
        children={
            "a": FakeLocator(attrs={"href": "/job_detail/x.html"}),
            ".job-name, .job-title": FakeLocator(text=" Java Developer "),
            ".salary": FakeLocator(text="25-35K"),
            ".job-area, .job-location": FakeLocator(text="Shanghai"),
            ".tag-list li, .job-card-footer li": [
                FakeLocator(text="3-5 years"),
                FakeLocator(text="Bachelor"),
            ],
            ".company-name": FakeLocator(text="Acme"),
            ".company-tag-list li, .company-info li": [
                FakeLocator(text="Internet"),
                FakeLocator(text="Series B"),
                FakeLocator(text="100-499 people"),
            ],
        }
    )
    page = FakeLocator(children={".job-card-wrapper, .job-card-box": [card]})

    jobs = parse_job_cards(page)

    assert len(jobs) == 1
    assert jobs[0].title == "Java Developer"
    assert jobs[0].url == "https://www.zhipin.com/job_detail/x.html"
    assert jobs[0].education == "Bachelor"
    assert jobs[0].company_size == "100-499 people"


def test_parse_job_cards_prefers_job_detail_anchor():
    card = FakeLocator(
        children={
            "a": FakeLocator(attrs={"href": "/web/geek/chat"}),
            'a[href*="/job_detail/"]': FakeLocator(attrs={"href": "/job_detail/x.html"}),
        }
    )
    page = FakeLocator(children={".job-card-wrapper, .job-card-box": [card]})

    jobs = parse_job_cards(page)

    assert jobs[0].url == "https://www.zhipin.com/job_detail/x.html"


def test_fill_detail_fills_description_and_company_size():
    page = FakeDetailPage(
        children={
            ".job-sec-text, .job-detail-section": FakeLocator(text="Build backend services"),
            '.sider-company p:has-text("人")': FakeLocator(text="100-499人"),
        }
    )
    job = JobPosting(url="https://www.zhipin.com/job_detail/x.html")

    filled = fill_detail(page, job)

    assert page.visited_url == "https://www.zhipin.com/job_detail/x.html"
    assert filled.description == "Build backend services"
    assert filled.company_size == "100-499人"


def test_parser_source_has_real_utf8_chinese_fragments():
    source = Path("src/boss_job_assistant/boss_parser.py").read_text(encoding="utf-8")

    assert 'has-text("人")' in source
    assert "æµœ" not in source
    assert "mojibake" not in source.lower()


class FakeDetailPage(FakeLocator):
    def __init__(self, *, children=None, fail_goto=False):
        super().__init__(children=children)
        self.fail_goto = fail_goto
        self.visited_url = ""
        self.waited_ms = 0

    def goto(self, url, wait_until=None):
        if self.fail_goto:
            raise RuntimeError("navigation failed")
        self.visited_url = url
        self.wait_until = wait_until

    def wait_for_timeout(self, timeout):
        self.waited_ms = timeout
