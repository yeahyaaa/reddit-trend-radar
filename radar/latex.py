"""The briefing as a document someone reads, rather than a list they scan.

Written, not compiled. Requiring a LaTeX distribution to run a Reddit script would
be rude, so the .tex lands next to the other output and compiling is your call:

    pdflatex radar-report.tex

Every package beyond the base class is guarded with \\IfFileExists, so a minimal
LaTeX install still produces a document. It just looks plainer.
"""

from __future__ import annotations

from radar.ai import Story
from radar.briefing import Briefing
from radar.models import Post
from radar.texescape import escape

PREAMBLE = r"""\documentclass[11pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[margin=2.2cm,headsep=14pt]{geometry}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}

% Optional throughout: a bare LaTeX install still compiles this, just plainer.
\IfFileExists{libertinus.sty}{\usepackage{libertinus}}{\usepackage{lmodern}}
\IfFileExists{microtype.sty}{\usepackage{microtype}}{}
% Rules are chosen here, not inside the tabular: \toprule expands to \noalign,
% which cannot sit inside a conditional in the middle of a table body.
\IfFileExists{booktabs.sty}{
  \usepackage{booktabs}
  \newcommand{\radartop}{\toprule}
  \newcommand{\radarmid}{\midrule}
  \newcommand{\radarbottom}{\bottomrule}
}{
  \newcommand{\radartop}{\hline}
  \newcommand{\radarmid}{\hline}
  \newcommand{\radarbottom}{\hline}
}
\IfFileExists{titlesec.sty}{
  \usepackage{titlesec}
  \titleformat{\section}{\normalfont\bfseries\large}{}{0pt}{}[\vspace{-6pt}\rule{\linewidth}{0.4pt}]
  \titlespacing{\section}{0pt}{18pt}{8pt}
}{}
\IfFileExists{fancyhdr.sty}{
  \usepackage{fancyhdr}
  \pagestyle{fancy}\fancyhf{}
  \renewcommand{\headrulewidth}{0.4pt}
  \fancyfoot[C]{\small\thepage}
}{}

\setlength{\parindent}{0pt}
\setlist[enumerate]{leftmargin=*,itemsep=9pt,topsep=4pt}
\setlist[itemize]{leftmargin=*,itemsep=3pt,topsep=3pt}
"""

SEPARATOR = r" \textbullet\ "

GENERATED_NOTE = (
    r"{\small\itshape Grouped by a language model from the posts below. The links are "
    r"ours, not its: it was shown post numbers, never URLs.}\par"
)


def to_latex(brief: Briefing) -> str:
    """Render the whole briefing as a standalone, compilable document.

    The model's reading sits near the top because it is a summary, the posts follow
    as the evidence for it, and the counting is a footnote at the end.
    """
    parts = [
        PREAMBLE,
        _running_head(brief),
        r"\begin{document}",
        _title(brief),
        _summary(brief),
        _story_section(brief),
        _community_sections(brief),
        _change_section(brief),
        _spread_section(brief),
        r"\end{document}",
    ]
    return "\n".join(part for part in parts if part) + "\n"


def _running_head(brief: Briefing) -> str:
    """The header line repeated on every page, once the document runs long."""
    watched = escape(", ".join(f"r/{name}" for name in brief.subreddits))
    return (
        r"\IfFileExists{fancyhdr.sty}{"
        r"\fancyhead[L]{\small Reddit Trend Radar}"
        rf"\fancyhead[R]{{\small {watched}{SEPARATOR}{escape(brief.generated_on)}}}"
        "}{}"
    )


def _title(brief: Briefing) -> str:
    watched = escape(", ".join(f"r/{name}" for name in brief.subreddits))
    return "\n".join(
        [
            r"{\LARGE\bfseries Reddit Trend Radar}\par",
            r"\vspace{4pt}",
            rf"{{\large Watching {watched}}}\par",
            r"\vspace{2pt}",
            rf"{{\small {escape(brief.generated_on)}}}\par",
            r"\vspace{16pt}",
        ]
    )


def _summary(brief: Briefing) -> str:
    """One line saying what this is and how much of it there is."""
    counts = ", ".join(rf"r/{escape(n)}~{len(p)}" for n, p in brief.by_community.items())
    lines = [
        "Top posts of the period, in Reddit's own ranking. "
        rf"{brief.post_count} posts: {counts}.\par"
    ]
    if not brief.has_history:
        lines.append(r"\vspace{4pt}")
        lines.append(r"{\small\itshape First run: nothing to compare against yet.}\par")
    lines.append(r"\vspace{6pt}")
    return "\n".join(lines)


def _story_section(brief: Briefing) -> str:
    """What the model made of the run, labelled as its reading and not ours."""
    if not brief.has_stories:
        return ""
    blocks = [
        r"\section*{What these communities are talking about}",
        GENERATED_NOTE,
        r"\vspace{8pt}",
    ]
    blocks.extend(_story(story) for story in brief.stories)
    return "\n".join(blocks)


def _story(story: Story) -> str:
    """One group: what it is, how far it spread, and every post in it."""
    where = ", ".join(rf"r/{escape(name)}" for name in story.subreddits)
    lines = [
        rf"\textbf{{{escape(story.headline)}}}\par",
        rf"{{\small {_count(len(story.posts))} across {where}}}\par",
    ]
    if story.summary:
        lines.append(rf"\vspace{{2pt}}{escape(story.summary)}\par")
    lines.append(r"\begin{itemize}")
    lines.extend(rf"  \item \href{{{p.link}}}{{{escape(p.title)}}}" for p in story.posts)
    lines.extend([r"\end{itemize}", r"\vspace{6pt}"])
    return "\n".join(lines)


def _count(number: int) -> str:
    """One post, two posts. A grammar slip here reads as carelessness everywhere else."""
    return f"{number} post" if number == 1 else f"{number} posts"


def _community_sections(brief: Briefing) -> str:
    """Every post, grouped by where it came from."""
    blocks = []
    for name, posts in brief.by_community.items():
        blocks.append(rf"\section*{{r/{escape(name)} \normalsize({len(posts)} posts)}}")
        blocks.append(r"\begin{enumerate}")
        blocks.extend(_post_item(post) for post in posts)
        blocks.append(r"\end{enumerate}")
    return "\n".join(blocks)


def _post_item(post: Post) -> str:
    """Title, provenance, both links, then whatever the author wrote.

    Every font switch sits in its own group. An ungrouped \\itshape runs to the end
    of the enclosing environment and italicises every later item too.
    """
    parts = [rf"  \item \href{{{post.link}}}{{{escape(post.title)}}}"]
    meta = _meta(post)
    if meta:
        parts.append(rf"\\ {{\small {meta}}}")
    parts.append(rf"\\ {{\small {_links(post)}}}")
    if post.summary:
        parts.append(rf"\\ {{\small\itshape {escape(post.summary)}}}")
    return "".join(parts)


def _meta(post: Post) -> str:
    """Author, time and score, each skipped when this transport did not carry it."""
    bits = []
    if post.author:
        bits.append(rf"u/{escape(post.author)}")
    if post.posted_at:
        bits.append(escape(post.posted_at))
    if post.has_metrics:
        bits.append(f"{int(post.score or 0)} points, {int(post.num_comments or 0)} comments")
    return SEPARATOR.join(bits)


def _links(post: Post) -> str:
    """The discussion, and the article it points at when there is one."""
    parts = [rf"\href{{{post.link}}}{{Discussion}}"]
    if post.source_url:
        parts.append(rf"\href{{{post.source_url}}}{{Source}}")
    return SEPARATOR.join(parts)


def _change_section(brief: Briefing) -> str:
    """What moved since the previous run. Absent on a first run, by design."""
    if not brief.has_history:
        return ""
    rows = [
        rf"\item \textbf{{{escape(c.word)}}} --- {c.status}, {c.before} to {c.now}"
        for c in (brief.risers + brief.faders)[:12]
    ]
    return "\n".join(
        [
            r"\section*{What changed since the last run}",
            r"\begin{itemize}",
            *rows,
            r"\end{itemize}",
        ]
    )


def _spread_section(brief: Briefing) -> str:
    """Word counting, which is what you get without a model configured."""
    if not brief.spreads:
        return ""
    names = list(brief.by_community)
    header = " & ".join([r"\textbf{Topic}"] + [rf"\textbf{{r/{escape(n)}}}" for n in names])
    rows = [
        " & ".join([escape(s.word)] + [str(s.counts.get(n, "") or "") for n in names])
        for s in brief.spreads
    ]
    return "\n".join(
        [
            r"\section*{Words appearing in more than one community}",
            r"{\small Counted, not read. The section above does this properly when a "
            r"model is configured.}\par",
            r"\vspace{8pt}",
            r"\noindent",
            rf"\begin{{tabular}}{{l{'r' * len(names)}}}",
            r"\radartop",
            header + r" \\",
            r"\radarmid",
            " \\\\\n".join(rows) + r" \\",
            r"\radarbottom",
            r"\end{tabular}",
        ]
    )
