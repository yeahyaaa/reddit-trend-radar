# Reddit Trend Radar

[![CI](https://github.com/YOUR-USERNAME/reddit-trend-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR-USERNAME/reddit-trend-radar/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

For five months I ran the social media for five company accounts, and every week I built the
content calendar the same way: by guessing what people would care about, and then finding out
afterwards what they had actually been arguing about. The guessing was the part of the job I was
worst at, and it was the part a machine could obviously do better.

This is that problem solved properly, pointed at the audience I care about now. It reads the top
posts from a handful of Linux and open-source subreddits, ranks them by how much discussion they
caused rather than how many upvotes they collected, pulls out the words showing up across all of
them, and writes a short briefing you can read in a minute.

**Contents:** [Output](#what-it-looks-like) · [Running it](#running-it) · [Ranking](#how-it-decides-what-is-interesting) · [Data paths](#getting-the-data-out-of-reddit) · [Rate limits](#when-reddit-tells-you-to-slow-down) · [Signing in](#signing-in-optional) · [Tests](#tests) · [Limitations](#what-it-does-not-do)

## What it looks like

```
# Reddit Trend Radar - 2026-09-24

## Trending words

linux (8), ubuntu (7), self (6), open (5), windows (4), boot (4), source (4), hosting (4)

## Top posts

1. I wanted to share my desktop with you.                              - r/ubuntu
2. Thinking of switching to ubuntu                                     - r/ubuntu
3. Snap's automatic refresh broke firefox then i lost recent bookmarks  - r/ubuntu
4. Linux vs Windows Benchmark Half Life 2 RTX                          - r/ubuntu
```

That third one is the reason I find this useful. A Snap update quietly eating someone's
bookmarks is the kind of thing you want to know about the morning it happens, not after it has
turned into a thread with four hundred replies.

Real output includes links and, when the metrics are available, points and comment counts.

## Running it

```bash
pip install -r requirements.txt
python -m radar.cli
```

No credentials needed. If you want the higher rate limit or private subreddits, see
[Signing in](#signing-in-optional).

That checks r/ubuntu, r/linux, r/kubernetes, r/opensource, r/devops and r/selfhosted over the
last day and writes `radar-report.md` next to you. It takes a minute or two, because it waits
between requests instead of hammering Reddit.

Pick your own subreddits and window:

```bash
python -m radar.cli -s ubuntu kubernetes rust -p week -n 20 --csv week.csv
```

| Flag | What it does | Default |
| --- | --- | --- |
| `-s, --subreddits` | which subreddits to read (no `r/` prefix needed) | the six above |
| `-p, --period` | `hour`, `day`, `week` or `month` | `day` |
| `-l, --limit` | how many posts to pull from each one | 25 |
| `-n, --top` | how many make it into the report | 15 |
| `-o, --out` | where to write the Markdown | `radar-report.md` |
| `--csv` | also write a CSV here | off |

## How it decides what is interesting

```
engagement = (points + comments * 3) * upvote_ratio
```

Comments count triple. A post 900 people quietly upvoted tells you less than a post 200 people
are still replying to, and if you are planning what to write about, the argument is the signal.

The upvote ratio pulls contested posts back down. A post sitting at 55% is usually a fight
rather than a topic, and those burn out fast.

None of this is science. I picked the weights because they matched what I would have chosen by
hand over a few weeks of reading, and they are one constant each at the top of `rank.py` if you
disagree.

## Getting the data out of Reddit

No API key, no account, no browser. Reddit will hand you the same content a page shows in
machine-readable form if you ask for `/r/<sub>/top.json`, and that is all this does.

Except it does not always hand it over. Reddit serves those listings to some networks and
answers 403 to others, and that seems to depend mostly on whether you look like a home
connection. When the JSON is refused, the script falls back to the public Atom feed, which
Reddit serves to everybody.

The catch is that the Atom feed carries titles and links but no points or comment counts. When
that happens the ranking has nothing to rank on, so those posts stay in Reddit's own order and
the report says at the top that it could not get the numbers. I would rather it told you than
quietly handed you a list that looks ranked and is not.

One thing worth knowing if you read the code: the first refusal switches the whole run over.
Asking for JSON again for every subreddit would triple the requests and get you rate-limited
for nothing.

## When Reddit tells you to slow down

You will see 429s if you ask for a lot at once. Requests get retried with increasing gaps, and
if Reddit sends a `Retry-After` header the script waits exactly that long rather than guessing.

If subreddits still get skipped, ask for fewer (`-s ubuntu linux`) or come back in a few
minutes. VPN and data-centre addresses get throttled far harder than home connections, so if
you are running this on a server expect to feel it.

Or sign in, which is the next section.

## Signing in (optional)

Two reasons to bother:

- **The rate limit.** Anonymous requests get throttled hard. Signed-in ones get a much longer
  leash, which is the difference between six subreddits and thirty.
- **Private subreddits.** Anonymous requests cannot see a subreddit that is members-only, even
  if you are a member, because the script is not you. Being logged in your browser does nothing
  for it. Giving it a login does.

You only need the second one if you actually want private subreddits, and it costs more, so
the setup below is in two stages. Stop after stage one if the rate limit is all you care about.

### Stage one: lift the rate limit, no password anywhere

1. Go to <https://www.reddit.com/prefs/apps> and press **create another app...**
2. Pick **script** as the type. Give it any name. Put `http://localhost:8080` as the redirect
   URI, which is required by the form and never used.
3. Create it. The **client id** is the short string sitting under the app's name, and the
   **secret** is the field labelled `secret`.
4. Copy `.env.example` to `.env` and fill in those two:

   ```
   REDDIT_CLIENT_ID=your_id_here
   REDDIT_CLIENT_SECRET=your_secret_here
   ```

5. `pip install python-dotenv` so the file gets read, then run as normal.

That gets an app-only token. Your Reddit password is not involved at any point, because this
grant never asks for one.

### Stage two: read your private subreddits

Add your login to the same `.env`:

```
REDDIT_USERNAME=your_username
REDDIT_PASSWORD=your_password
```

The script notices they are there and switches to a user token, which can see whatever your
account can see. If you have two-factor authentication on, the password has to be written as
`yourpassword:123456` with a live code, which expires in seconds. That is genuinely annoying and
it is meant to be.

Worth saying plainly: this puts your actual Reddit password in a file on your disk. `.env` is in
`.gitignore` and nothing logs it, but it is still a password sitting in plaintext, and it is the
reason stage one exists separately. If you only want the rate limit, do not do stage two.

### Checking it worked

```bash
python -c "from radar import auth; print('signed in' if auth.bearer_token() else 'anonymous')"
```

If the credentials are wrong you get an `AuthError` naming the HTTP status, rather than a
silent fall back to anonymous, so a typo in `.env` does not quietly cost you the rate limit you
thought you had.

## Tests

```bash
pip install -e ".[dev]"
python -m pytest tests/ --cov=radar
python -m ruff check .
python -m mypy radar
```

CI runs all three on Python 3.11, 3.12 and 3.13 for every push, and fails the build if coverage
drops below 90%. Currently 66 tests at 92%, ruff clean, mypy clean under `strict`. The uncovered lines are the live
HTTP calls. Everything that parses, scores, authenticates or renders is tested against fixtures,
including the awkward cases: feeds with no entries, posts with missing fields, credentials that
are half filled in, and the fallback kicking in halfway through a run.

## What it does not do

- No sentiment analysis. Counting words is crude and I have left it crude, because every
  cleverer version I tried was harder to trust and not obviously better.
- No history. Each run is a snapshot. If you want week-on-week movement you would need to keep
  the CSVs and diff them, which I have not built.
- No comment text. Titles only.
- Nothing is cached, so two runs in a row means two sets of requests.

## Layout

```
radar/
  models.py     the Post dataclass every stage passes along
  auth.py       optional OAuth, and the two grants it picks between
  net.py        user agent, timeout, bearer token, and the 429 retry policy
  fetch.py      JSON listings, host fallback, remembering which path works
  rss.py        Atom feed fallback
  rank.py       scoring and ordering
  keywords.py   splitting titles into words and counting them
  report.py     Markdown and CSV output
  cli.py        arguments and wiring
```

## Licence

MIT. Do what you like with it.
