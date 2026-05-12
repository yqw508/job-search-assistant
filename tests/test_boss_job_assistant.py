from pathlib import Path

from boss_job_assistant.boss_job_assistant import (
    _current_page,
    _launch_context,
    _search_url,
)


def test_search_url_uses_city_code_when_present():
    assert _search_url("Java Spring Boot", "广州", "101280100") == (
        "https://www.zhipin.com/web/geek/job"
        "?query=Java%20Spring%20Boot&city=101280100"
    )


def test_search_url_falls_back_to_encoded_city_name():
    assert _search_url("Java Spring Boot", "广州") == (
        "https://www.zhipin.com/web/geek/job"
        "?query=Java%20Spring%20Boot&city=%E5%B9%BF%E5%B7%9E"
    )


def test_source_has_no_common_mojibake_fragments():
    files = [
        Path("src/boss_job_assistant/boss_job_assistant.py"),
        Path("config.yaml"),
        Path("README.md"),
    ]
    fragments = ("æ", "ç¼", "éª", "å¹", "î", "�")

    for path in files:
        source = path.read_text(encoding="utf-8")
        for fragment in fragments:
            assert fragment not in source, f"{path} contains mojibake fragment {fragment}"


def test_source_contains_next_page_text_and_browser_install_command():
    source = Path("src/boss_job_assistant/boss_job_assistant.py").read_text(
        encoding="utf-8"
    )

    assert "下一页" in source
    assert "python -m playwright install chromium" in source


def test_launch_context_uses_system_browser_channel(monkeypatch):
    calls = []

    class FakeChromium:
        def launch_persistent_context(self, user_data_dir, **kwargs):
            calls.append((user_data_dir, kwargs))
            return object()

    class FakePlaywright:
        chromium = FakeChromium()

    monkeypatch.setenv("BOSS_BROWSER_CHANNEL", "msedge")

    _launch_context(FakePlaywright())

    user_data_dir, kwargs = calls[0]
    assert user_data_dir == ".browser-profile"
    assert kwargs["channel"] == "msedge"
    assert kwargs["headless"] is False
    assert kwargs["slow_mo"] == 200


def test_launch_context_connects_over_cdp(monkeypatch):
    calls = []

    class FakeBrowser:
        contexts = ["existing-context"]

    class FakeChromium:
        def connect_over_cdp(self, endpoint):
            calls.append(endpoint)
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    monkeypatch.setenv("BOSS_CDP_ENDPOINT", "http://127.0.0.1:9222")

    assert _launch_context(FakePlaywright()) == "existing-context"
    assert calls == ["http://127.0.0.1:9222"]


def test_current_page_prefers_non_blank_page():
    class FakePage:
        def __init__(self, url):
            self.url = url

    class FakeContext:
        pages = [
            FakePage("about:blank"),
            FakePage("https://www.zhipin.com/web/geek/job"),
        ]

    assert _current_page(FakeContext()).url == "https://www.zhipin.com/web/geek/job"


def test_config_defaults_to_manual_start():
    import yaml

    config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))

    assert config["search"]["manual_start"] is True
