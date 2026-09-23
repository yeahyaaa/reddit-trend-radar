from radar import cli
from radar.cli import build_parser, main
from radar.models import Post

POST = Post(
    title="Ubuntu 26.04 released",
    subreddit="ubuntu",
    score=900,
    num_comments=120,
    upvote_ratio=0.97,
    permalink="/r/ubuntu/comments/1",
)


def stub_fetch(posts, failures=()):
    """Build a fetch_many replacement that returns a fixed result."""
    return lambda subreddits, period, limit: (list(posts), list(failures))


def test_parser_defaults_cover_the_open_source_subreddits():
    args = build_parser().parse_args([])
    assert "ubuntu" in args.subreddits
    assert args.period == "day"


def test_parser_accepts_custom_subreddits_and_period():
    args = build_parser().parse_args(["-s", "linux", "-p", "week", "-n", "3"])
    assert args.subreddits == ["linux"]
    assert args.period == "week"
    assert args.top == 3


def test_main_writes_a_markdown_report(tmp_path, monkeypatch):
    target = tmp_path / "report.md"
    monkeypatch.setattr(cli, "fetch_many", stub_fetch([POST]))
    assert main(["-o", str(target)]) == 0
    assert "Ubuntu 26.04 released" in target.read_text(encoding="utf-8")


def test_main_writes_csv_when_asked(tmp_path, monkeypatch):
    md, csv_path = tmp_path / "r.md", tmp_path / "r.csv"
    monkeypatch.setattr(cli, "fetch_many", stub_fetch([POST]))
    main(["-o", str(md), "--csv", str(csv_path)])
    assert "ubuntu" in csv_path.read_text(encoding="utf-8")


def test_main_returns_an_error_code_when_nothing_was_fetched(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "fetch_many", stub_fetch([]))
    assert main(["-o", str(tmp_path / "r.md")]) == 1


def test_main_reports_skipped_subreddits(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "fetch_many", stub_fetch([POST], ["r/broken: HTTP 404"]))
    main(["-o", str(tmp_path / "r.md")])
    assert "r/broken" in capsys.readouterr().err


def test_main_explains_what_to_do_about_rate_limits(tmp_path, monkeypatch, capsys):
    failures = ["r/devops: 429 Client Error: Too Many Requests"]
    monkeypatch.setattr(cli, "fetch_many", stub_fetch([POST], failures))
    main(["-o", str(tmp_path / "r.md")])
    assert "rate-limited" in capsys.readouterr().err


def test_main_stays_quiet_about_rate_limits_when_there_were_none(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "fetch_many", stub_fetch([POST], ["r/broken: HTTP 404"]))
    main(["-o", str(tmp_path / "r.md")])
    assert "rate-limited" not in capsys.readouterr().err
