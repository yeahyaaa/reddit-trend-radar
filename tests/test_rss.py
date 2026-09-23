from radar.rss import parse_atom

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Ubuntu 26.04 LTS is out</title>
    <link href="https://www.reddit.com/r/ubuntu/comments/abc/ubuntu_2604/"/>
    <updated>2026-09-24T10:00:00+00:00</updated>
  </entry>
  <entry>
    <title>Snap vs flatpak again</title>
    <link href="https://www.reddit.com/r/ubuntu/comments/def/snap/"/>
    <updated>2026-09-24T09:00:00+00:00</updated>
  </entry>
</feed>"""


def test_parse_returns_one_post_per_entry():
    assert len(parse_atom(FEED, "ubuntu")) == 2


def test_parse_reads_title_and_subreddit():
    first = parse_atom(FEED, "ubuntu")[0]
    assert first.title == "Ubuntu 26.04 LTS is out"
    assert first.subreddit == "ubuntu"


def test_parse_converts_link_to_permalink():
    assert parse_atom(FEED, "ubuntu")[0].permalink == "/r/ubuntu/comments/abc/ubuntu_2604/"


def test_parse_marks_metrics_as_unavailable():
    first = parse_atom(FEED, "ubuntu")[0]
    assert first.score is None
    assert first.num_comments is None
    assert first.source == "rss"
    assert first.has_metrics is False


def test_parse_handles_empty_feed():
    empty = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    assert parse_atom(empty, "ubuntu") == []


def test_parse_skips_entries_without_a_title():
    feed = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
      <entry><link href="https://www.reddit.com/r/x/comments/1/"/></entry></feed>"""
    assert parse_atom(feed, "x") == []
