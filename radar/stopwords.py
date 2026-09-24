"""Ordinary English, which is not a topic no matter how often it appears.

Counting post bodies rather than titles alone multiplies the recall and the noise
together. A fixed list handles the words that are filler in any subject area; the
document-frequency ceiling in analysis.py handles the ones that are filler only in
this particular corpus, like "ubuntu" in a run that reads r/ubuntu.

Deliberately domain-neutral. Nothing here is about Linux, because the next person
to run this is watching something else.
"""

_WORDS = """
a about above actual actually after again against all almost along already also although
always am among apparently
an and another any anybody anyone anything anyway are around as at away

back basically be because been before being below best better between big both but by

came can cannot certain could couldn currently definitely didn does doesn doing don done
down during

each either else enough especially essentially even eventually ever every everybody everyone
everything except

far few finally first for found from further

generally get gets getting give go goes going gone good got

guy guys had has have having he hello her here hers herself him himself his how however

i if in indeed instead into is isn it its itself

just

keep kept know known knows

last least less let like likely little long look looking lot

made make makes making many may maybe me mean means mentioned might mine more most much
must my myself

near need needs neither never new next nice no nobody none nor not nothing now

obviously of off often on once one only onto or other others otherwise ought our ours
ourselves out over own

particular per perhaps please pretty probably put

quite

rather really recently right

said same saw say says see seem seems seen several shall she should shows similar similarly
sorry
simply
since so some somebody someone something sometimes somewhat soon still such sure

specifically take taken takes tell thank thanks than that the their theirs them themselves
then there
therefore these
they thing things think thinking this those though thought through thus time to today
together too took toward try trying two

truly under until up upon us use used useful uses using usually various

very

want wants was way we well went were what whatever when whenever where whether which while
wondering
who whoever whole whom whose why will with within without won would

yes yet you your yours yourself
"""

STOPWORDS = frozenset(_WORDS.split())
