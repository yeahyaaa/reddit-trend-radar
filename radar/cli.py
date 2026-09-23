"""Command line entry point: fetch, rank, extract, write."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from radar.fetch import fetch_many
from radar.keywords import extract_keywords
from radar.models import Post
from radar.rank import rank_posts
from radar.report import to_markdown, write_csv

DEFAULT_SUBS = ["ubuntu", "linux", "kubernetes", "opensource", "devops", "selfhosted"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Daily trend radar for Linux and open-source subreddits."
    )
    parser.add_argument("-s", "--subreddits", nargs="+", default=DEFAULT_SUBS)
    parser.add_argument("-p", "--period", default="day", choices=["hour", "day", "week", "month"])
    parser.add_argument("-l", "--limit", type=int, default=25, help="posts pulled per subreddit")
    parser.add_argument("-n", "--top", type=int, default=15, help="posts kept in the report")
    parser.add_argument("-o", "--out", default="radar-report.md")
    parser.add_argument("--csv", default=None, help="also write a CSV to this path")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline and return a process exit code."""
    args = build_parser().parse_args(argv)
    posts, failures = fetch_many(args.subreddits, args.period, args.limit)
    for problem in failures:
        print(f"skipped {problem}", file=sys.stderr)
    _advise_on_rate_limits(failures)
    if not posts:
        print("No posts fetched. Check your connection or try again shortly.", file=sys.stderr)
        return 1
    return _emit(args, rank_posts(posts, args.top), posts)


def _advise_on_rate_limits(failures: list[str]) -> None:
    """A 429 means Reddit wants fewer requests, so say what that looks like."""
    if not any("429" in problem for problem in failures):
        return
    print(
        "Reddit rate-limited this run. Ask for fewer subreddits at a time "
        "(-s ubuntu linux), add credentials to lift the limit (see the README), "
        "or wait a few minutes and run it again.",
        file=sys.stderr,
    )


def _emit(args: argparse.Namespace, ranked: list[Post], all_posts: list[Post]) -> int:
    """Write the report files and say where they landed."""
    markdown = to_markdown(ranked, extract_keywords(all_posts, 12), date.today().isoformat())
    Path(args.out).write_text(markdown, encoding="utf-8")
    print(f"Wrote {args.out} ({len(ranked)} posts from {len(all_posts)} fetched)")
    if args.csv:
        write_csv(ranked, args.csv)
        print(f"Wrote {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
