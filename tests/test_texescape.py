from radar.texescape import escape


class TestLatexSyntax:
    def test_ampersand_and_percent(self):
        assert escape("Snap & flatpak, 50% slower") == r"Snap \& flatpak, 50\% slower"

    def test_underscores_and_hashes(self):
        assert escape("apt_get #1") == r"apt\_get \#1"

    def test_braces_and_dollars(self):
        assert escape("${HOME} {x}") == r"\$\{HOME\} \{x\}"

    def test_backslash_is_not_double_escaped(self):
        assert escape("C:\path") == r"C:\textbackslash{}path"

    def test_tilde_and_caret(self):
        assert escape("~/x^2") == r"\textasciitilde{}/x\textasciicircum{}2"


class TestUnicode:
    """pdflatex refuses characters it has no glyph for, and dies on the whole document."""

    def test_an_emoji_does_not_reach_the_document(self):
        assert "\U0001f603" not in escape("Happy \U0001f603 user")

    def test_the_words_around_an_emoji_survive(self):
        assert escape("Happy \U0001f603 user").split() == ["Happy", "user"]

    def test_curly_quotes_become_straight_ones(self):
        assert escape("i\u2019m here") == "i'm here"

    def test_smart_double_quotes_become_straight_ones(self):
        assert escape("\u201cquoted\u201d") == '"quoted"'

    def test_dashes_and_ellipsis_are_spelled_out(self):
        assert escape("a\u2014b\u2013c\u2026") == "a---b--c..."

    def test_accented_latin_is_kept_because_latex_can_set_it(self):
        assert escape("café naïve") == "café naïve"

    def test_non_latin_scripts_are_dropped_rather_than_breaking_the_build(self):
        assert escape("hello \u4e16\u754c world").split() == ["hello", "world"]

    def test_a_string_of_nothing_but_emoji_comes_back_empty(self):
        assert escape("\U0001f603\U0001f440").strip() == ""
