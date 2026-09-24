from radar.analysis import cross_community, topic_counts
from radar.models import Post


def post(title, sub="ubuntu", body=""):
    return Post(title=title, subreddit=sub, summary=body, permalink=f"/r/{sub}/1")


class TestTopicCounts:
    def test_numbers_alone_are_not_topics(self):
        """Version fragments like 04 and 26 dominated the old word counts."""
        counts = dict(topic_counts([post("Ubuntu 26.04 released")]))
        assert "ubuntu" in counts
        assert "04" not in counts
        assert "26" not in counts

    def test_two_letter_words_are_dropped(self):
        assert "up" not in dict(topic_counts([post("Speed up my pc")]))

    def test_a_word_in_the_body_counts_too(self):
        counts = dict(topic_counts([post("A question", body="my wayland session crashes")]))
        assert counts["wayland"] == 1

    def test_the_same_word_twice_in_one_post_counts_once(self):
        """Otherwise one rambling post decides the whole briefing."""
        counts = dict(topic_counts([post("snap snap snap", body="snap snap")]))
        assert counts["snap"] == 1

    def test_counts_come_back_commonest_first(self):
        posts = [post("snap issue"), post("snap again"), post("wayland")]
        assert topic_counts(posts)[0] == ("snap", 2)


class TestCrossCommunity:
    def test_a_topic_in_two_communities_is_reported(self):
        posts = [
            post("snap broke", sub="ubuntu"),
            post("snap trouble", sub="ubuntu"),
            post("snap again", sub="linux"),
        ]
        spread = cross_community(posts)
        assert spread[0].word == "snap"
        assert spread[0].communities == 2

    def test_a_topic_in_one_community_only_is_not_a_spread(self):
        posts = [post("snap broke", sub="ubuntu"), post("snap again", sub="ubuntu")]
        assert cross_community(posts) == []

    def test_the_per_community_counts_are_kept(self):
        posts = [
            post("snap broke", sub="ubuntu"),
            post("snap again", sub="ubuntu"),
            post("snap too", sub="linux"),
        ]
        assert cross_community(posts)[0].counts == {"ubuntu": 2, "linux": 1}

    def test_widest_spread_comes_first(self):
        posts = [
            post("snap wayland", sub="ubuntu"),
            post("snap wayland", sub="linux"),
            post("wayland", sub="devops"),
        ]
        assert cross_community(posts)[0].word == "wayland"

    def test_no_posts_means_no_spread(self):
        assert cross_community([]) == []


class TestNoiseFiltering:
    """Scanning post bodies floods the counts with ordinary English unless filtered."""

    def test_common_filler_words_are_not_topics(self):
        filler = "then you similar like other now also maybe something someone basically"
        counts = dict(topic_counts([post("Wayland", body=filler)]))
        assert list(counts) == ["wayland"]

    def test_a_word_in_almost_every_post_is_not_distinguishing(self):
        """Ten posts all mentioning ubuntu: true, but it tells you nothing."""
        posts = [post(f"ubuntu thing {i}", body="ubuntu") for i in range(10)]
        posts.append(post("wayland crash"))
        counts = dict(topic_counts(posts))
        assert "wayland" in counts
        assert "ubuntu" not in counts

    def test_the_ceiling_does_not_apply_to_tiny_runs(self):
        """With three posts, everything looks frequent; filtering would empty the report."""
        counts = dict(topic_counts([post("snap issue"), post("snap again")]))
        assert "snap" in counts

    def test_a_genuinely_shared_topic_survives_both_filters(self):
        posts = [post(f"filler {i}", body="ordinary words here") for i in range(8)]
        posts += [
            post("wayland crash", sub="ubuntu"),
            post("wayland stutter", sub="ubuntu"),
            post("wayland tearing", sub="linux"),
        ]
        spread = {s.word for s in cross_community(posts)}
        assert "wayland" in spread
        assert "ordinary" not in spread


class TestSpreadQuality:
    """A word in three communities once each is a coincidence, not a trend."""

    def test_a_topic_needs_more_than_one_mention_per_community_to_count(self):
        posts = [
            post("thanks for this", sub="ubuntu"),
            post("thanks all", sub="linux"),
        ]
        assert [s.word for s in cross_community(posts)] == []

    def test_a_topic_mentioned_enough_times_survives(self):
        posts = [
            post("wayland tearing", sub="ubuntu"),
            post("wayland crash", sub="ubuntu"),
            post("wayland session", sub="linux"),
        ]
        assert [s.word for s in cross_community(posts)] == ["wayland"]

    def test_the_most_mentioned_topic_leads_not_the_most_scattered(self):
        # Padding keeps the document-frequency ceiling out of the way; without it
        # wayland is in five of eight posts and gets pruned as too common to matter.
        posts = [post(f"unrelated chatter {i}", sub="ubuntu") for i in range(10)]
        posts += [post(f"wayland {i}", sub="ubuntu") for i in range(4)]
        posts += [post("wayland elsewhere", sub="linux")]
        posts += [
            post("snap a", sub="ubuntu"),
            post("snap b", sub="linux"),
            post("snap c", sub="devops"),
        ]
        ranked = cross_community(posts)
        assert ranked[0].word == "wayland"
        assert ranked[0].total > ranked[1].total
        assert ranked[1].communities > ranked[0].communities
