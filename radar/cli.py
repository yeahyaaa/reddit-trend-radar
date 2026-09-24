"""Command line entry point: fetch, analyse, compare against history, write."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import requests

from radar import ai, briefing, history, providers
from radar.briefing import Briefing
from radar.fetch import fetch_each
from radar.latex import to_latex
from radar.models import Post, SubredditResult
from radar.report import to_markdown, write_csv
from radar.subreddits import normalise_all
from radar.xlsx import write_xlsx

DEFAULT_SUBS = ["ubuntu", "linux", "kubernetes", "opensource", "devops", "selfhosted"]

# What to call each transport in the progress lines, rather than leaking field names.
SOURCE_LABEL = {"json": "listing", "rss": "feed"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Trend briefing for any set of public subreddits."
    )
    parser.add_argument(
        "-s", "--subreddits", nargs="+", default=DEFAULT_SUBS,
        help="names, r/ prefixes or pasted Reddit URLs",
    )
    parser.add_argument(
        "-p", "--period", default="day", choices=["hour", "day", "week", "month", "year"]
    )
    parser.add_argument("-l", "--limit", type=int, default=25, help="posts pulled per subreddit")
    parser.add_argument(
        "--pause", type=float, default=None,
        help="seconds between subreddits; raise it when Reddit keeps answering 429",
    )
    parser.add_argument("-n", "--top", type=int, default=20, help="posts kept per subreddit")
    parser.add_argument("-o", "--out", default="radar-report.md")
    parser.add_argument("--csv", default=None, help="also write a CSV to this path")
    parser.add_argument("--xlsx", default=None, help="also write an Excel sheet")
    parser.add_argument("--tex", default=None, help="also write a LaTeX document to compile")
    parser.add_argument(
        "--history", default=str(history.DEFAULT_PATH), help="where to keep past runs"
    )
    parser.add_argument(
        "--no-history", action="store_true", help="do not read or write the history file"
    )
    parser.add_argument(
        "--ai", action="store_true", help="group the posts into stories with a language model"
    )
    parser.add_argument(
        "--ai-provider", default=None, choices=sorted(providers.PROVIDERS),
        help="which API key to use; guessed from the environment when omitted",
    )
    parser.add_argument("--ai-model", default=None, help="override the provider's default model")
    parser.add_argument(
        "--ai-free", action="store_true",
        help="OpenRouter only: rotate through its best free models, moving on when one is spent",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="only print the final summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline and return a process exit code."""
    args = build_parser().parse_args(argv)
    try:
        args.subreddits = normalise_all(args.subreddits)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    _say(args, f"Reading {len(args.subreddits)} subreddits, top of the {args.period}\n")

    posts: list[Post] = []
    results: list[SubredditResult] = []
    for result in fetch_each(args.subreddits, args.period, args.limit, args.pause):
        results.append(result)
        posts.extend(result.posts)
        _say(args, _progress_line(result))

    if not posts:
        print("\nNothing fetched. Check your connection, or try fewer subreddits.", file=sys.stderr)
        return 1
    _advise_on_rate_limits(results)
    return _emit(args, posts)


def _progress_line(result: SubredditResult) -> str:
    """One aligned line per subreddit, so a slow run shows its work."""
    name = f"r/{result.subreddit}".ljust(16)
    if not result.ok:
        return f"  {name}skipped   {result.error}"
    label = SOURCE_LABEL.get(result.source, result.source)
    return f"  {name}{len(result.posts):>3} posts  {label}"


def _advise_on_rate_limits(results: list[SubredditResult]) -> None:
    """A 429 means Reddit wants fewer requests, so say what that looks like."""
    if not any("429" in (r.error or "") for r in results):
        return
    print(
        "\nReddit rate-limited this run. Ask for fewer subreddits at a time "
        "(-s ubuntu linux), or wait a few minutes and run it again.",
        file=sys.stderr,
    )


def _assemble(args: argparse.Namespace, posts: list[Post]) -> Briefing:
    """Record this run, then read it back alongside the one before it.

    Recording first means the comparison is today against the previous day rather
    than today against itself, and a second run on one day replaces the first.
    """
    today = date.today().isoformat()
    changes = []
    if not args.no_history:
        with history.open_store(args.history) as store:
            history.record_run(store, posts, args.subreddits, today)
            changes = history.compare_runs(store)
    brief = briefing.build(posts, args.subreddits, today, changes, args.top)
    return briefing.build(
        posts, args.subreddits, today, changes, args.top, _stories(args, brief)
    )


def _stories(args: argparse.Namespace, brief: Briefing) -> list[ai.Story]:
    """Ask a model to group the posts, if one was asked for.

    A failure here loses the optional section, not the run: the briefing is still
    worth writing when the model is rate-limited or the key has expired.
    """
    if not args.ai:
        return []
    try:
        found, used = ai.analyse(brief.posts, args.ai_provider, args.ai_model, args.ai_free)
    except (providers.ProviderError, requests.RequestException) as exc:
        print(f"\nThe model step did not run: {exc}", file=sys.stderr)
        return []
    _say(args, f"  {used} grouped them into {len(found)} stories")
    return found


def _emit(args: argparse.Namespace, posts: list[Post]) -> int:
    """Write every requested format and say where each landed."""
    brief = _assemble(args, posts)
    Path(args.out).write_text(to_markdown(brief), encoding="utf-8")
    print(
        f"\nWrote {args.out}  -  {brief.post_count} posts across "
        f"{brief.community_count} communities, {len(brief.spreads)} shared topics"
    )
    if args.csv:
        write_csv(brief.posts, args.csv)
        print(f"Wrote {args.csv}")
    if args.xlsx:
        write_xlsx(brief.posts, args.xlsx)
        print(f"Wrote {args.xlsx}")
    if args.tex:
        Path(args.tex).write_text(to_latex(brief), encoding="utf-8")
        print(f"Wrote {args.tex}  -  compile with: pdflatex {args.tex}")
    return 0


def _say(args: argparse.Namespace, line: str) -> None:
    """Progress goes to stderr, so piping the summary somewhere stays clean."""
    if not args.quiet:
        print(line, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
