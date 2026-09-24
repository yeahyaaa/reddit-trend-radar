import json

import pytest

from radar import ai
from radar.ai import build_prompt, parse_stories
from radar.models import Post
from radar.providers import Provider, ProviderError

POSTS = [
    Post(
        title="Hurricane Polo explodes into Category 5",
        subreddit="news",
        permalink="/r/news/comments/1",
        source_url="https://www.cnn.com/2026/09/22/weather/hurricane-polo",
    ),
    Post(
        title="Cat 5 hurricane bears down on Mexico",
        subreddit="worldnews",
        permalink="/r/worldnews/comments/2",
        source_url="https://www.bbc.co.uk/news/articles/xyz",
    ),
    Post(title="Spurs fans leaving at 80 minutes", subreddit="soccer", permalink="/r/soccer/3"),
]


class TestPrompt:
    def test_every_post_is_numbered_for_the_model_to_refer_back_to(self):
        prompt = build_prompt(POSTS)
        assert "[1]" in prompt
        assert "[3]" in prompt

    def test_the_subreddit_is_given_so_spread_can_be_seen(self):
        assert "r/worldnews" in build_prompt(POSTS)

    def test_the_source_domain_is_given_but_not_the_url(self):
        """The model never sees a link, so it can never invent one."""
        prompt = build_prompt(POSTS)
        assert "cnn.com" in prompt
        assert "https://" not in prompt

    def test_the_reddit_permalink_is_never_shown_either(self):
        assert "/r/news/comments/1" not in build_prompt(POSTS)

    def test_bodies_are_included_but_capped(self):
        wordy = Post(title="t", subreddit="news", summary="word " * 500)
        prompt = build_prompt([wordy])
        assert "word" in prompt
        assert len(prompt) < 6000

    def test_the_prompt_asks_for_post_numbers_not_prose_citations(self):
        assert "posts" in build_prompt(POSTS).lower()


class TestParsing:
    """An unreadable reply and an honest "nothing grouped" are different answers."""

    def reply(self, stories):
        return json.dumps({"stories": stories})

    def test_a_story_is_matched_back_to_its_real_posts(self):
        raw = [{"headline": "Hurricane", "summary": "Two covered it", "posts": [1, 2]}]
        stories = parse_stories(self.reply(raw), POSTS)
        assert stories[0].headline == "Hurricane"
        assert [p.subreddit for p in stories[0].posts] == ["news", "worldnews"]

    def test_the_links_come_from_our_data_not_the_model(self):
        reply = self.reply([{"headline": "H", "summary": "s", "posts": [1, 2]}])
        story = parse_stories(reply, POSTS)[0]
        assert story.posts[0].link == "https://www.reddit.com/r/news/comments/1"

    def test_the_communities_a_story_spans_are_counted(self):
        reply = self.reply([{"headline": "H", "summary": "s", "posts": [1, 2]}])
        story = parse_stories(reply, POSTS)[0]
        assert story.subreddits == ["news", "worldnews"]
        assert story.community_count == 2

    def test_an_index_out_of_range_is_dropped(self):
        reply = self.reply([{"headline": "H", "summary": "s", "posts": [1, 2, 99]}])
        assert len(parse_stories(reply, POSTS)[0].posts) == 2

    def test_a_group_of_one_is_not_a_group(self):
        """The post is already listed under its community; repeating it says nothing twice."""
        reply = self.reply([{"headline": "H", "summary": "s", "posts": [1]}])
        assert parse_stories(reply, POSTS) == []

    def test_a_group_left_with_one_real_post_is_also_dropped(self):
        reply = self.reply([{"headline": "H", "summary": "s", "posts": [1, 99]}])
        assert parse_stories(reply, POSTS) == []

    def test_a_story_referring_to_nothing_real_is_discarded(self):
        reply = self.reply([{"headline": "H", "summary": "s", "posts": [98, 99]}])
        assert parse_stories(reply, POSTS) == []

    def test_a_story_with_no_headline_is_discarded(self):
        reply = self.reply([{"headline": "", "summary": "s", "posts": [1, 2]}])
        assert parse_stories(reply, POSTS) == []

    def test_an_honest_empty_answer_is_a_list_not_a_failure(self):
        """Nothing covered twice is a real finding, not a model that misbehaved."""
        assert parse_stories(self.reply([]), POSTS) == []

    def test_json_wrapped_in_a_code_fence_is_still_read(self):
        """Models add fences even when asked for bare JSON."""
        body = self.reply([{"headline": "H", "summary": "s", "posts": [1, 2]}])
        fenced = "```json\n" + body + "\n```"
        assert len(parse_stories(fenced, POSTS)) == 1

    def test_prose_before_the_json_is_ignored(self):
        messy = "Here you go!\n" + self.reply([{"headline": "H", "summary": "s", "posts": [1, 2]}])
        assert len(parse_stories(messy, POSTS)) == 1

    def test_a_reply_that_is_not_json_at_all_is_unreadable(self):
        assert parse_stories("I cannot help with that.", POSTS) is None

    def test_an_empty_reply_is_unreadable(self):
        assert parse_stories("", POSTS) is None

    def test_json_without_a_stories_key_is_unreadable(self):
        assert parse_stories('{"result": "ok"}', POSTS) is None

    def test_truncated_json_is_unreadable(self):
        assert parse_stories('{"stories": [{"headline": "Sto', POSTS) is None

    def test_stories_covering_more_communities_come_first(self):
        POSTS.append(Post(title="More soccer", subreddit="soccer", permalink="/r/soccer/4"))
        reply = self.reply(
            [
                {"headline": "Single", "summary": "s", "posts": [3, 4]},
                {"headline": "Shared", "summary": "s", "posts": [1, 2]},
            ]
        )
        assert [s.headline for s in parse_stories(reply, POSTS)] == ["Shared", "Single"]
        POSTS.pop()


class TestAnalyse:
    def test_no_key_configured_means_no_analysis_and_no_error(self, monkeypatch):
        monkeypatch.setattr(ai, "detect", lambda chosen: None)
        assert ai.analyse(POSTS, None, None) == ([], "")

    def test_an_empty_run_is_not_sent_to_a_model(self, monkeypatch):
        called = []
        fake = Provider("x", "X_API_KEY", "https://x", "m")
        monkeypatch.setattr(ai, "detect", lambda chosen: fake)
        monkeypatch.setattr(ai, "request", lambda *a, **k: called.append(1) or "{}")
        assert ai.analyse([], None, None) == ([], "")
        assert called == []

    def test_a_provider_failure_does_not_take_the_run_down(self, monkeypatch):
        """The briefing is still worth writing without the optional section."""
        fake = Provider("x", "X_API_KEY", "https://x", "m")
        monkeypatch.setattr(ai, "detect", lambda chosen: fake)

        def boom(*args):
            raise ProviderError("rate limited")

        monkeypatch.setattr(ai, "request", boom)
        with pytest.raises(ProviderError):
            ai.analyse(POSTS, None, None)
