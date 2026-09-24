from radar import cli, fetch
from radar.cli import main
from radar.models import Post, SubredditResult


def ok(name, count=3, source="json"):
    posts = [
        Post(title=f"{name} {i}", subreddit=name, score=10 * i, source=source)
        for i in range(count)
    ]
    return SubredditResult(subreddit=name, posts=posts, source=source)


def failed(name, error="HTTP 429"):
    return SubredditResult(subreddit=name, posts=[], error=error)


def stub_each(results):
    return lambda subreddits, period, limit, pause=None: iter(results)


def run(monkeypatch, tmp_path, results):
    monkeypatch.setattr(cli, "fetch_each", stub_each(results))
    monkeypatch.setattr(fetch, "reset_transport", lambda: None)
    return main(["-o", str(tmp_path / "r.md"), "--no-history"])


def test_each_subreddit_is_named_as_it_finishes(monkeypatch, tmp_path, capsys):
    run(monkeypatch, tmp_path, [ok("ubuntu"), ok("linux")])
    err = capsys.readouterr().err
    assert "r/ubuntu" in err
    assert "r/linux" in err


def test_post_counts_are_shown(monkeypatch, tmp_path, capsys):
    run(monkeypatch, tmp_path, [ok("ubuntu", count=7)])
    assert "7 posts" in capsys.readouterr().err


def test_the_transport_is_named(monkeypatch, tmp_path, capsys):
    run(monkeypatch, tmp_path, [ok("ubuntu", source="rss")])
    assert "feed" in capsys.readouterr().err


def test_failures_appear_on_their_own_line(monkeypatch, tmp_path, capsys):
    run(monkeypatch, tmp_path, [ok("ubuntu"), failed("devops")])
    err = capsys.readouterr().err
    assert "r/devops" in err
    assert "HTTP 429" in err


def test_a_run_with_only_failures_exits_non_zero(monkeypatch, tmp_path):
    assert run(monkeypatch, tmp_path, [failed("ubuntu"), failed("linux")]) == 1


def test_a_partial_run_still_succeeds(monkeypatch, tmp_path):
    assert run(monkeypatch, tmp_path, [ok("ubuntu"), failed("linux")]) == 0


def test_the_summary_counts_what_was_kept_and_what_was_read(monkeypatch, tmp_path, capsys):
    run(monkeypatch, tmp_path, [ok("ubuntu", count=4), ok("linux", count=6)])
    assert "10" in capsys.readouterr().out
