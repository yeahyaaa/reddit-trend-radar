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


FEED_WITH_AUTHOR = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <author><name>/u/someone</name></author>
    <title>Ubuntu 26.04 LTS is out</title>
    <link href="https://www.reddit.com/r/ubuntu/comments/abc/x/"/>
    <published>2026-09-23T11:23:09+00:00</published>
  </entry>
</feed>"""


def test_parse_reads_the_author():
    assert parse_atom(FEED_WITH_AUTHOR, "ubuntu")[0].author == "someone"


def test_the_u_prefix_is_stripped_from_the_author():
    assert not parse_atom(FEED_WITH_AUTHOR, "ubuntu")[0].author.startswith("/u/")


def test_parse_reads_the_publication_time():
    assert parse_atom(FEED_WITH_AUTHOR, "ubuntu")[0].published == "2026-09-23T11:23:09+00:00"


def test_missing_author_and_time_are_empty_not_an_error():
    post = parse_atom(FEED, "ubuntu")[0]
    assert post.author == ""
    assert post.published == ""


def feed_with_content(inner_html: str) -> str:
    """Wrap raw HTML the way Reddit does: escaped, inside an Atom content element."""
    from xml.sax.saxutils import escape as xml_escape

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
        "<title>A post</title>"
        '<link href="https://www.reddit.com/r/ubuntu/comments/abc/x/"/>'
        f'<content type="html">{xml_escape(inner_html)}</content>'
        "</entry></feed>"
    )


SELF_BODY = (
    '<!-- SC_OFF --><div class="md">'
    "<p>I have a <b>laptop</b> with 8GB RAM.</p>"
    "<p>Will Ubuntu run well on it?</p>"
    "</div><!-- SC_ON --> submitted by "
    '<a href="https://www.reddit.com/user/x">/u/x</a> <br/>'
    # A text post's [link] points back at its own thread, which is not a source.
    '<span><a href="https://www.reddit.com/r/ubuntu/comments/abc/x/">[link]</a></span>'
    '<span><a href="https://www.reddit.com/r/ubuntu/comments/abc/x/">[comments]</a></span>'
)

LINK_BODY = (
    "<table><tr><td>"
    '<a href="https://x"><img src="https://y" /></a>'
    "</td><td> submitted by "
    '<a href="https://z">/u/q</a> <br/>'
    '<span><a href="https://x">[link]</a></span>'
    "</td></tr></table>"
)

SELF_POST = feed_with_content(SELF_BODY)
LINK_POST = feed_with_content(LINK_BODY)


def test_the_body_of_a_text_post_is_extracted():
    summary = parse_atom(SELF_POST, "ubuntu")[0].summary
    assert "8GB RAM" in summary
    assert "Will Ubuntu run well on it?" in summary


def test_the_body_has_no_html_tags_left_in_it():
    summary = parse_atom(SELF_POST, "ubuntu")[0].summary
    assert "<" not in summary
    assert "laptop" in summary


def test_reddits_own_boilerplate_is_not_treated_as_body_text():
    summary = parse_atom(SELF_POST, "ubuntu")[0].summary
    assert "submitted by" not in summary
    assert "[link]" not in summary


def test_a_link_post_has_no_body_rather_than_boilerplate():
    assert parse_atom(LINK_POST, "ubuntu")[0].summary == ""


def test_paragraphs_are_joined_with_a_space_not_run_together():
    assert "RAM. Will" in parse_atom(SELF_POST, "ubuntu")[0].summary


def test_an_entry_with_no_content_has_an_empty_summary():
    assert parse_atom(FEED, "ubuntu")[0].summary == ""


LONG_BODY = "word " * 300  # ~1500 characters, far past any display limit


def test_the_parser_keeps_the_whole_body():
    """Truncating here would throw the text away for the CSV and the sheet too."""
    post = parse_atom(feed_with_content(f'<div class="md"><p>{LONG_BODY}</p></div>'), "ubuntu")[0]
    assert len(post.summary) > 1000
    assert not post.summary.endswith("...")


LINK_POST_WITH_SOURCE = (
    "<table><tr><td>"
    '<a href="https://www.bbc.co.uk/news/articles/abc">'
    '<img src="https://preview.redd.it/x.png" /></a>'
    "</td><td> submitted by "
    '<a href="https://www.reddit.com/user/q">/u/q</a> <br/>'
    '<span><a href="https://www.bbc.co.uk/news/articles/abc">[link]</a></span>'
    '<span><a href="https://www.reddit.com/r/news/comments/1/">[comments]</a></span>'
    "</td></tr></table>"
)


def test_the_article_the_post_points_at_is_captured():
    post = parse_atom(feed_with_content(LINK_POST_WITH_SOURCE), "news")[0]
    assert post.source_url == "https://www.bbc.co.uk/news/articles/abc"


def test_the_reddit_thread_stays_the_main_link():
    post = parse_atom(feed_with_content(LINK_POST_WITH_SOURCE), "news")[0]
    assert post.link.startswith("https://www.reddit.com/r/")


def test_a_self_post_points_at_no_article():
    """A text post's [link] is its own thread, which is not a source worth repeating."""
    post = parse_atom(SELF_POST, "ubuntu")[0]
    assert post.source_url == ""


def test_an_entry_with_no_content_has_no_article():
    assert parse_atom(FEED, "ubuntu")[0].source_url == ""
