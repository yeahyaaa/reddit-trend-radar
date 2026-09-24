import pytest

from radar import cli
from radar.cli import build_parser, main
from radar.models import Post, SubredditResult

POST = Post(
    title="Ubuntu 26.04 released",
    subreddit="ubuntu",
    score=900,
    num_comments=120,
    upvote_ratio=0.97,
    permalink="/r/ubuntu/comments/1",
)


SECOND = Post(
    title="Ubuntu 26.04 also covered here",
    subreddit="ubuntu",
    permalink="/r/ubuntu/comments/2",
)


def stub_each(*results):
    """Replace the fetch generator with a fixed sequence of outcomes."""
    return lambda subreddits, period, limit, pause=None: iter(results)


def test_parser_defaults_cover_the_open_source_subreddits():
    args = build_parser().parse_args([])
    assert "ubuntu" in args.subreddits
    assert args.period == "day"
    assert args.quiet is False


def test_parser_accepts_custom_subreddits_and_period():
    args = build_parser().parse_args(["-s", "linux", "-p", "week", "-n", "3"])
    assert args.subreddits == ["linux"]
    assert args.period == "week"
    assert args.top == 3


def test_main_writes_a_markdown_report(tmp_path, monkeypatch):
    target = tmp_path / "report.md"
    monkeypatch.setattr(cli, "fetch_each", stub_each(SubredditResult("ubuntu", [POST])))
    assert main(["-o", str(target), "--no-history"]) == 0
    assert "Ubuntu 26.04 released" in target.read_text(encoding="utf-8")


def test_main_writes_csv_when_asked(tmp_path, monkeypatch):
    md, csv_path = tmp_path / "r.md", tmp_path / "r.csv"
    monkeypatch.setattr(cli, "fetch_each", stub_each(SubredditResult("ubuntu", [POST])))
    main(["-o", str(md), "--csv", str(csv_path), "--no-history"])
    assert "ubuntu" in csv_path.read_text(encoding="utf-8")


def test_main_returns_an_error_code_when_nothing_was_fetched(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "fetch_each", stub_each())
    assert main(["-o", str(tmp_path / "r.md"), "--no-history"]) == 1


def test_quiet_suppresses_progress_but_keeps_the_summary(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "fetch_each", stub_each(SubredditResult("ubuntu", [POST])))
    main(["-o", str(tmp_path / "r.md"), "--quiet", "--no-history"])
    captured = capsys.readouterr()
    assert "r/ubuntu" not in captured.err
    assert "Wrote" in captured.out


def test_xlsx_is_written_when_asked(tmp_path, monkeypatch):
    target = tmp_path / "r.xlsx"
    monkeypatch.setattr(cli, "fetch_each", stub_each(SubredditResult("ubuntu", [POST])))
    main(["-o", str(tmp_path / "r.md"), "--xlsx", str(target), "--no-history"])
    assert target.exists()


def test_latex_is_written_when_asked(tmp_path, monkeypatch):
    target = tmp_path / "r.tex"
    monkeypatch.setattr(cli, "fetch_each", stub_each(SubredditResult("ubuntu", [POST])))
    main(["-o", str(tmp_path / "r.md"), "--tex", str(target), "--no-history"])
    assert r"\documentclass" in target.read_text(encoding="utf-8")


def test_optional_formats_stay_unwritten_unless_requested(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "fetch_each", stub_each(SubredditResult("ubuntu", [POST])))
    main(["-o", str(tmp_path / "r.md"), "--no-history"])
    assert list(tmp_path.iterdir()) == [tmp_path / "r.md"]


def test_a_pasted_url_is_accepted_as_a_subreddit(tmp_path, monkeypatch):
    seen = {}

    def spy(subreddits, period, limit, pause=None):
        seen["subreddits"] = subreddits
        return iter([SubredditResult("news", [POST])])

    monkeypatch.setattr(cli, "fetch_each", spy)
    main(["-s", "https://www.reddit.com/r/news/", "r/soccer", "-o", str(tmp_path / "r.md"),
          "--no-history"])
    assert seen["subreddits"] == ["news", "soccer"]


def test_something_that_is_not_a_subreddit_is_refused(tmp_path, capsys):
    code = main(["-s", "https://example.com/news", "-o", str(tmp_path / "r.md"), "--no-history"])
    assert code == 2
    assert "not a subreddit" in capsys.readouterr().err


class TestAiStep:
    def stub_reply(self, monkeypatch, reply):
        from radar import ai
        from radar.providers import Provider

        fake = Provider("x", "X_API_KEY", "https://x", "m")
        monkeypatch.setattr(ai, "detect", lambda chosen: fake)
        monkeypatch.setattr(ai, "request", lambda *args: reply)

    def test_no_ai_flag_means_no_model_call(self, tmp_path, monkeypatch):
        from radar import ai

        monkeypatch.setattr(cli, "fetch_each", stub_each(SubredditResult("ubuntu", [POST])))
        monkeypatch.setattr(ai, "detect", lambda chosen: pytest.fail("should not be called"))
        target = tmp_path / "r.md"
        assert main(["-o", str(target), "--no-history"]) == 0

    def test_stories_reach_the_report(self, tmp_path, monkeypatch):
        pair = SubredditResult("ubuntu", [POST, SECOND])
        monkeypatch.setattr(cli, "fetch_each", stub_each(pair))
        self.stub_reply(
            monkeypatch,
            '{"stories": [{"headline": "Release week", "summary": "Two posts.", "posts": [1, 2]}]}',
        )
        target = tmp_path / "r.md"
        assert main(["-o", str(target), "--no-history", "--ai"]) == 0
        assert "Release week" in target.read_text(encoding="utf-8")

    def test_a_model_failure_still_writes_the_briefing(self, tmp_path, monkeypatch, capsys):
        from radar import ai
        from radar.providers import Provider, ProviderError

        monkeypatch.setattr(cli, "fetch_each", stub_each(SubredditResult("ubuntu", [POST])))
        fake = Provider("x", "X_API_KEY", "https://x", "m")
        monkeypatch.setattr(ai, "detect", lambda chosen: fake)

        def boom(*args):
            raise ProviderError("rate limited")

        monkeypatch.setattr(ai, "request", boom)
        target = tmp_path / "r.md"
        assert main(["-o", str(target), "--no-history", "--ai"]) == 0
        assert "Ubuntu 26.04 released" in target.read_text(encoding="utf-8")
        assert "did not run" in capsys.readouterr().err
