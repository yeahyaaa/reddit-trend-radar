import pytest

from radar.history import compare_runs, open_store, recent_runs, record_run, topic_series
from radar.models import Post


@pytest.fixture
def store(tmp_path):
    with open_store(tmp_path / "radar.db") as connection:
        yield connection


def post(title, sub="ubuntu", body=""):
    return Post(title=title, subreddit=sub, summary=body, permalink=f"/r/{sub}/{title[:4]}")


class TestRecording:
    def test_a_run_comes_back_with_its_posts(self, store):
        record_run(store, [post("snap broke")], ["ubuntu"], "2026-09-24")
        runs = recent_runs(store, 5)
        assert len(runs) == 1
        assert runs[0].post_count == 1

    def test_runs_come_back_newest_first(self, store):
        record_run(store, [post("old")], ["ubuntu"], "2026-09-22")
        record_run(store, [post("new")], ["ubuntu"], "2026-09-24")
        assert [r.ran_on for r in recent_runs(store, 5)] == ["2026-09-24", "2026-09-22"]

    def test_the_watched_communities_are_remembered(self, store):
        record_run(store, [post("x")], ["ubuntu", "linux"], "2026-09-24")
        assert recent_runs(store, 1)[0].subreddits == ["ubuntu", "linux"]

    def test_reopening_the_store_keeps_what_was_written(self, tmp_path):
        path = tmp_path / "radar.db"
        with open_store(path) as connection:
            record_run(connection, [post("snap")], ["ubuntu"], "2026-09-24")
        with open_store(path) as connection:
            assert len(recent_runs(connection, 5)) == 1

    def test_two_runs_on_one_day_replace_rather_than_double_count(self, store):
        record_run(store, [post("first")], ["ubuntu"], "2026-09-24")
        record_run(store, [post("second"), post("third")], ["ubuntu"], "2026-09-24")
        runs = recent_runs(store, 5)
        assert len(runs) == 1
        assert runs[0].post_count == 2


class TestComparison:
    def test_the_first_ever_run_has_nothing_to_compare_against(self, store):
        record_run(store, [post("snap broke")], ["ubuntu"], "2026-09-24")
        assert compare_runs(store) == []

    def test_a_topic_absent_before_is_marked_new(self, store):
        record_run(store, [post("wayland crash")], ["ubuntu"], "2026-09-23")
        record_run(store, [post("snap broke")], ["ubuntu"], "2026-09-24")
        changes = {c.word: c for c in compare_runs(store)}
        assert changes["snap"].status == "new"
        assert changes["snap"].before == 0

    def test_a_topic_mentioned_more_than_before_is_rising(self, store):
        record_run(store, [post("snap broke")], ["ubuntu"], "2026-09-23")
        busier = [post("snap a"), post("snap b"), post("snap c")]
        record_run(store, busier, ["ubuntu"], "2026-09-24")
        changes = {c.word: c for c in compare_runs(store)}
        assert changes["snap"].status == "rising"
        assert changes["snap"].now == 3

    def test_a_topic_that_stopped_being_mentioned_is_gone(self, store):
        record_run(store, [post("wayland crash")], ["ubuntu"], "2026-09-23")
        record_run(store, [post("snap broke")], ["ubuntu"], "2026-09-24")
        changes = {c.word: c for c in compare_runs(store)}
        assert changes["wayland"].status == "gone"

    def test_an_unchanged_topic_is_steady(self, store):
        record_run(store, [post("snap broke")], ["ubuntu"], "2026-09-23")
        record_run(store, [post("snap again")], ["ubuntu"], "2026-09-24")
        changes = {c.word: c for c in compare_runs(store)}
        assert changes["snap"].status == "steady"

    def test_the_biggest_movers_come_first(self, store):
        record_run(store, [post("snap x"), post("wayland y")], ["ubuntu"], "2026-09-23")
        later = [post(f"snap {i}") for i in range(5)] + [post("wayland z")]
        record_run(store, later, ["ubuntu"], "2026-09-24")
        assert compare_runs(store)[0].word == "snap"


class TestSeries:
    def test_a_topic_traced_across_runs(self, store):
        record_run(store, [post("snap a")], ["ubuntu"], "2026-09-22")
        record_run(store, [post("snap b"), post("snap c")], ["ubuntu"], "2026-09-23")
        record_run(store, [], ["ubuntu"], "2026-09-24")
        assert topic_series(store, "snap") == [
            ("2026-09-22", 1),
            ("2026-09-23", 2),
            ("2026-09-24", 0),
        ]

    def test_a_topic_never_seen_is_flat_not_missing(self, store):
        record_run(store, [post("snap a")], ["ubuntu"], "2026-09-22")
        assert topic_series(store, "wayland") == [("2026-09-22", 0)]
