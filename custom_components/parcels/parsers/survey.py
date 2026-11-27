"""What a survey about a delivery says besides naming that delivery.

A survey or a request for a rating names the delivery it is about ("O seu
objeto RR123456785PT foi entregue em 25-11-2026. Ajude-nos a melhorar"):
its number, its order and its last status. That's no news. Anything else
it says is: a status still to come (in transit, out for delivery, a missed
attempt), a pickup code, the last day to collect, or a day to come for a
delivery ("will be delivered on Monday 30 November"). The topic gate
(``parsers._gate``) drops a survey only when it brings no news (``news``),
and sends a delivery whose body asks to answer a survey to review when the
delivery is an old one (``old_delivery``).

Sentences that ask for feedback or to answer a survey
(``prefilter.survey_sentence``) are left out: their dates are the
survey's ("Responda até 4 de dezembro"). So are footers' rating requests,
which name no date. Every check reads folded text, never fetches anything
and keeps nothing from the e-mail.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta, tzinfo
from itertools import pairwise
import re

from ..const import MailKind
from . import eta, prefilter
from ._amazon_shopify_common import fold_text, local_date, says_yesterday
from .base import MailMessage, ParseResult
from .carriers._common import NOTE_KIND_UNCLEAR
from .generic import NOTE_KIND_DEFAULT, SCAN_CHARS
from .lang import detect_language

# What ``news`` finds: a status, a pickup code or a last day to collect, or
# only a day to come.
NEWS_LIVE = "live"
NEWS_DATE = "date"

# How many days ahead a date written in a survey is still news.
MAX_NEWS_DAYS = 31
# Characters read to tell the language, when no parser told it.
_LANGUAGE_CHARS = 5000

# Kinds that only name what a survey is about: the delivery, the parcel
# waiting at its point, or the order.
_NAMING_KINDS = frozenset(
    {
        MailKind.DELIVERED,
        MailKind.READY_FOR_PICKUP,
        MailKind.ORDER,
        MailKind.CUSTOMER_RETURN,
        MailKind.UNKNOWN,
        MailKind.NOT_PARCEL,
    }
)
# Kinds a parser falls back to when no words say one (the notes below).
_DEFAULT_KINDS = frozenset({MailKind.SHIPPED, MailKind.IN_TRANSIT})
_DEFAULT_NOTES = frozenset({NOTE_KIND_UNCLEAR, NOTE_KIND_DEFAULT})

# A sentence ends at a full stop, a question or exclamation mark followed by
# a space, or a line break; never at the point of a date ("30. November").
_BOUNDARY_RE = re.compile(r"(?<!\d)[.!?](?=\s|$)|\n")

# A delivery done or a parcel collected, over folded text. Words that are
# also nouns ("punto de recogida", "ponto de retirada", "livreur") or mean
# something else in another language (pt "livre" is free) are left out.
_DONE_RE = re.compile(
    r"(?<![a-z0-9])(?:"
    r"delivered|picked\s+up|collected"
    r"|entregues?|levantad[ao]s?|recolhid[ao]s?"
    r"|entregad[ao]s?|recogidos?"
    r"|zugestellt|geliefert|ausgeliefert|abgeholt"
    r"|recuperee?s?"
    r"|consegnat[aeio]|ritirat[aeio]"
    r"|bezorgd|afgeleverd|geleverd|opgehaald"
    r")(?![a-z0-9])"
)
# French "livré": done in French only.
_LIVRE_RE = re.compile(r"(?<![a-z0-9])livree?s?(?![a-z0-9])")
# A parcel waiting at its point, over folded text.
_READY_RE = re.compile(
    r"(?<![a-z0-9])(?:"
    r"ready|available|waiting\s+for\s+you"
    r"|pront[ao]s?|disponive(?:l|is)|a\s+sua\s+espera"
    r"|listos?|lista\s+para|disponibles?"
    r"|abholbereit|bereit|wartet"
    r"|prete?s?|vous\s+attend"
    r"|disponibil[ei]|ti\s+aspetta"
    r"|klaar|beschikbaar|wacht\s+op"
    r")(?![a-z0-9])"
)
# Words that put a delivery ahead ("will be delivered", "vai ser entregue",
# "wird zugestellt"). Dutch "worden" only: German "worden" is past.
_FUTURE_RE = re.compile(
    r"(?<![a-z])(?:"
    r"will|won'?t|(?:is|are)\s+(?:expected|scheduled|due|going|set)\s+to\s+be"
    r"|sera|serao|seran|seront|(?:vai|vao|ira|irao)\s+ser|(?:va|van)\s+a\s+ser"
    r"|wird|werden|sara|saranno|verra|verranno"
    r"|zal|zullen|wordt"
    r")(?![a-z])"
)
_DUTCH_FUTURE_RE = re.compile(r"(?<![a-z])worden(?![a-z])")


@dataclass(frozen=True, slots=True)
class _Sentence:
    """A sentence of the body, with the dates written in it."""

    text: str
    folded: str
    dates: tuple[eta.DateExpression, ...]
    survey: bool
    done: bool
    ready: bool
    future: bool


def news(result: ParseResult, message: MailMessage, tz: tzinfo) -> str | None:
    """Return what an e-mail says besides naming the delivery a survey rates.

    ``NEWS_LIVE`` for a status other than delivered or waiting at its point
    (one a parser fell back to doesn't count), a pickup code or a last day
    to collect; ``NEWS_DATE`` for only a day to come, within
    ``MAX_NEWS_DAYS``, outside the survey's own sentences (in a sentence
    saying the parcel was delivered, the day must be written with its date
    or come with words that put it ahead, "will be delivered"); None when
    the e-mail only names the delivery.
    """
    if any(shipment.pickup_code for shipment in result.shipments):
        return NEWS_LIVE
    kinds = {s.kind or result.kind for s in result.shipments} or {result.kind}
    kinds -= _NAMING_KINDS
    if not _DEFAULT_NOTES.isdisjoint(result.notes):
        kinds -= _DEFAULT_KINDS
    if kinds:
        return NEWS_LIVE
    text = message.text[:SCAN_CHARS]
    lang = _language(result, message)
    if eta.find_collect_by(text, message.date, tz, lang) is not None:
        return NEWS_LIVE
    day = local_date(message.date, tz)
    last = day + timedelta(days=MAX_NEWS_DAYS)
    for sentence in _sentences(text, message, tz, lang):
        if sentence.survey:
            continue
        for found in sentence.dates:
            if found.deadline or found.other or not day < found.start <= last:
                continue
            if sentence.done and not (sentence.future or found.named):
                continue
            return NEWS_DATE
    return None


def old_delivery(result: ParseResult, message: MailMessage, tz: tzinfo) -> bool:
    """Return True when the delivery a survey's body names is an old one.

    Old: the parser read an event before the day of the e-mail, the subject
    names another day ("A sua entrega de 4 de novembro"), or the body says
    the parcel was delivered on another day, written with its date or its
    weekday ("was delivered on Friday", a week ago in a Friday's e-mail), or
    yesterday. Fresh, which wins: an event on the day of the e-mail, a
    pickup code, or a day to collect, a parcel waiting or a delivery on
    that day or later. Nothing said either way isn't old.
    """
    day = local_date(message.date, tz)
    old = False
    for shipment in result.shipments:
        if shipment.event_time is not None:
            if local_date(shipment.event_time, tz) >= day:
                return False
            old = True
        if (
            shipment.pickup_code
            and (shipment.kind or result.kind) is MailKind.READY_FOR_PICKUP
        ):
            return False
    lang = _language(result, message)
    for found in eta.date_expressions(message.subject, message.date, tz, lang):
        if found.other:
            continue
        if _includes(found, day) or (found.deadline and found.end >= day):
            return False
        if not found.deadline:
            old = True
    for sentence in _sentences(message.text[:SCAN_CHARS], message, tz, lang):
        for found in sentence.dates:
            # Unless words put it ahead, a weekday alone in such a sentence
            # is a past one ("was delivered on Friday"), though read as the
            # next, and the e-mail's own weekday is a week ago: a carrier
            # would say "today".
            past = found.weekday and sentence.done and not sentence.future
            today = _includes(found, day) and not past
            if not sentence.survey and (
                (found.deadline and found.end >= day)
                or (sentence.ready and found.end >= day)
                or (sentence.done and not found.deadline and today)
            ):
                return False
            if (
                sentence.done
                and (found.named or not sentence.future)
                and not (found.deadline or found.other or today)
            ):
                old = True
        if sentence.done and says_yesterday(sentence.folded, lang):
            old = True
    return old


def _includes(found: eta.DateExpression, day: date) -> bool:
    return found.start <= day <= found.end


def _language(result: ParseResult, message: MailMessage) -> str | None:
    """Return the e-mail's language, as a parser or the e-mail told it."""
    return (
        result.language
        or message.language
        or detect_language(f"{message.subject}\n{message.text[:_LANGUAGE_CHARS]}")
    )


def _sentences(
    text: str, message: MailMessage, tz: tzinfo, lang: str | None
) -> Iterator[_Sentence]:
    """Split the body into sentences, each with its dates and its words."""
    located = eta.located_date_expressions(text, message.date, tz, lang)
    spans = [(start, end) for _, start, end in located]
    cuts = [0]
    for match in _BOUNDARY_RE.finditer(text):
        if not any(start <= match.start() < end for start, end in spans):
            cuts.append(match.end())
    cuts.append(len(text))
    folded = fold_text(text)
    for start, end in pairwise(cuts):
        if not text[start:end].strip():
            continue
        part = folded[start:end]
        yield _Sentence(
            text=text[start:end],
            folded=part,
            dates=tuple(found for found, at, _ in located if start <= at < end),
            survey=prefilter.survey_sentence(text[start:end]),
            done=bool(
                _DONE_RE.search(part)
                or (lang in ("fr", None) and _LIVRE_RE.search(part))
            ),
            ready=_READY_RE.search(part) is not None,
            future=bool(
                _FUTURE_RE.search(part)
                or (lang == "nl" and _DUTCH_FUTURE_RE.search(part))
            ),
        )
