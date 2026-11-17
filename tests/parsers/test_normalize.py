"""Tests for turning raw e-mails and Graph messages into MailMessage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
import json

import pytest

from custom_components.parcels.parsers.auth import verify_sender
from custom_components.parcels.parsers.base import Link
from custom_components.parcels.parsers.normalize import (
    MAX_LINKS,
    MAX_TEXT_CHARS,
    MAX_URL_CHARS,
    html_to_text,
    links_from_text,
    message_from_bytes,
    message_from_graph,
)

from .conftest import GRAPH_FIXTURES


def _raw(headers: str, body: str = "Hello", content_type: str = "text/plain") -> bytes:
    """Build a single-part message from header lines and a body."""
    return (
        f"{headers}MIME-Version: 1.0\n"
        f"Content-Type: {content_type}; charset=UTF-8\n\n{body}\n"
    ).encode()


def _parse(raw: bytes, provider: str = "google"):
    return message_from_bytes(
        raw, mailbox="alex@example.com", provider_id="id-1", provider=provider
    )


def _graph(name: str) -> dict:
    return json.loads((GRAPH_FIXTURES / name).read_text(encoding="utf-8"))


def test_html_drops_invisible_elements() -> None:
    """Scripts, styles, the head and similar elements are dropped."""
    text, links = html_to_text(
        "<html><head><title>Title</title><style>p{color:red}</style>"
        "<script>var secret = 1;</script></head><body>"
        "<noscript>Enable JS</noscript><template><p>Hidden</p></template>"
        "<svg><text>Vector</text></svg><p>Visible</p>"
        "<script>document.write('x')</script></body></html>"
    )
    assert text == "Visible"
    assert links == ()


def test_html_blocks_cells_and_entities() -> None:
    """Blocks break lines, cells are spaced and entities are decoded."""
    text, _ = html_to_text(
        "<h1>Encomenda&nbsp;enviada</h1><div>Linha&#160;1</div><p>Linha 2</p>"
        "<table><tr><td>N.&ordm;</td><td>1042</td></tr>"
        "<tr><th>Total</th><td>24,90&nbsp;&euro;</td></tr></table>"
        "<ul><li>Um</li><li>Dois</li></ul>A<br>B<br><br><br><br>C &amp; D"
    )
    assert text == (
        "Encomenda enviada\nLinha 1\nLinha 2\nN.º 1042\nTotal 24,90 €\n"
        "Um\nDois\nA\nB\n\nC & D"
    )


def test_html_unclosed_head() -> None:
    """Text after an unclosed head is still read."""
    text, _ = html_to_text("<head><title>Ignored</title><p>Shown</p>")
    assert text == "Shown"


def test_html_links() -> None:
    """Only http(s) links are kept, with their visible text or image alt."""
    _, links = html_to_text(
        '<a href="https://www.ctt.pt/track?objects=RR123456785PT">Seguir <b>'
        'encomenda</b></a> <a href="mailto:alex@example.com">Mail</a>'
        '<a href="tel:+351210000000">Call</a><a href="javascript:alert(1)">JS</a>'
        '<a href="data:text/html,x">Data</a><a href="cid:logo">Cid</a>'
        '<a href="http://example.com/a&amp;b">Plain</a>'
        '<a href=" https://example.com/\n spaced ">Spaced</a>'
        '<a href="https://example.com/img"><img src="https://example.com/x.png"'
        ' alt="Track parcel"></a><a href="https://">Empty</a><a>No href</a>'
    )
    assert links == (
        Link("https://www.ctt.pt/track?objects=RR123456785PT", "Seguir encomenda"),
        Link("http://example.com/a&b", "Plain"),
        Link("https://example.com/spaced", "Spaced"),
        Link("https://example.com/img", "Track parcel"),
    )


def test_html_limits() -> None:
    """URLs, link counts and the text size are capped."""
    long_url = "https://example.com/" + "a" * 5000
    many = "".join(f'<a href="https://example.com/{i}">{i}</a>' for i in range(400))
    _, links = html_to_text(f'<a href="{long_url}">Long</a>{many}')
    assert len(links[0].url) == MAX_URL_CHARS
    assert len(links) == MAX_LINKS
    text, _ = html_to_text("<p>" + "word " * 100_000 + "</p>")
    assert len(text) <= MAX_TEXT_CHARS


@pytest.mark.parametrize(
    "html",
    [
        "<p>Unclosed <b>bold <i>italic",
        "<<<>>> <p <a href='https://example.com'>x</a",
        "</p></div></td>Stray end tags",
        "<a href='https://example.com/1'>One<a href='https://example.com/2'>Two",
        "<![CDATA[x]]><!-- comment <p>hidden</p> --><p>After</p>",
        "<script>never closed",
        "",
    ],
)
def test_html_malformed(html: str) -> None:
    """Malformed HTML never raises."""
    text, links = html_to_text(html)
    assert isinstance(text, str)
    assert all(link.url.startswith("https://") for link in links)


def test_links_from_text() -> None:
    """URLs in plain text are found, cleaned and deduplicated."""
    links = links_from_text(
        "Track: https://www.ups.com/track?tracknum=1Z999AA10123456784. "
        "(see https://example.com/a) again https://www.ups.com/track?tracknum="
        "1Z999AA10123456784, mailto:alex@example.com ftp://example.com/x"
    )
    assert links == (
        Link("https://www.ups.com/track?tracknum=1Z999AA10123456784"),
        Link("https://example.com/a"),
    )


def test_fixture_quoted_printable(load_eml) -> None:
    """A quoted-printable multipart e-mail is decoded from its HTML part."""
    message = load_eml("common/small_shop_ctt.eml")
    assert message.provider == "google"
    assert message.provider_id == "small_shop_ctt.eml"
    assert message.mailbox == "alex@example.com"
    assert message.message_id == "<20261117091200.1042@mail.loja-exemplo.example>"
    assert message.sender == "encomendas@loja-exemplo.example"
    assert message.sender_domain == "loja-exemplo.example"
    assert message.sender_name == "Loja Exemplo"
    assert message.subject == "A sua encomenda n.º 1042 foi enviada"
    assert message.date == datetime(2026, 11, 17, 9, 12, tzinfo=UTC)
    assert message.received is None
    assert message.reply_to is None
    assert "Número de objeto: RR123456785PT" in message.text
    assert "Entrega prevista: quinta-feira, 19 de novembro" in message.text
    assert "trackOpen" not in message.text
    assert "color" not in message.text
    assert message.links == (
        Link(
            "https://www.ctt.pt/feapl_2/app/open/objectSearch/objectSearch.jspx"
            "?objects=RR123456785PT",
            "Seguir encomenda",
        ),
    )
    assert set(message.headers) == {"return-path", "authentication-results"}
    assert message.auth is not None
    assert message.auth.authserv_id == "mx.google.com"
    assert message.language == "pt"


def test_fixture_8bit_with_content_language(load_eml) -> None:
    """An 8-bit UTF-8 e-mail keeps its Content-Language."""
    message = load_eml("common/german_shop_dhl.eml", provider="microsoft")
    assert message.provider == "microsoft"
    assert message.sender_name == "Beispiel Shop | Versand"
    assert message.date == datetime(2026, 11, 17, 10, 30, tzinfo=UTC)
    assert message.date.utcoffset() == timedelta(hours=1)
    assert "Musterstraße" in message.text
    assert message.headers["content-language"] == "de-DE"
    assert message.language == "de"


def test_headers_kept() -> None:
    """Only the topmost Authentication-Results and a few headers are kept."""
    message = _parse(
        _raw(
            "Authentication-Results: mx.google.com; dkim=pass header.d=shop.example\n"
            "Authentication-Results: mx.google.com; dkim=pass header.d=ctt.pt\n"
            "From: =?UTF-8?B?TG9qYSDDgWd1aWE=?= <Loja@Shop.example>\n"
            "Reply-To: Apoio <Apoio@Shop.example>\n"
            "Subject: =?ISO-8859-1?Q?Encomenda_n=BA_7_enviada?=\n"
            "Date: Tue, 17 Nov 2026 09:12:00 +0000\n"
            "Content-Language: ja\n"
            "List-Id: <news.shop.example>\n"
            "X-Mailer: Example Mailer\n"
            "X-Shopify-Shop-Id: 123\n"
            "X-Shopify-Email-Type: shipping\n"
            "X-Other: dropped\n"
            "DKIM-Signature: v=1; d=shop.example\n"
        )
    )
    assert message.sender == "loja@shop.example"
    assert message.sender_name == "Loja Águia"
    assert message.reply_to == "apoio@shop.example"
    assert message.subject == "Encomenda nº 7 enviada"
    assert message.message_id == ""
    assert message.headers == {
        "authentication-results": "mx.google.com; dkim=pass header.d=shop.example",
        "content-language": "ja",
        "list-id": "<news.shop.example>",
        "x-mailer": "Example Mailer",
        "x-shopify-shop-id": "123",
        "x-shopify-email-type": "shipping",
    }
    assert message.auth is not None
    assert message.auth.dkim_pass_domains == ("shop.example",)
    # "ja" is not supported, so the language is detected from the subject.
    assert message.language == "pt"


def test_raw_utf8_headers() -> None:
    """Raw UTF-8 bytes in headers are decoded."""
    message = _parse(
        _raw(
            "From: Serviços Exemplo <geral@servicos.example>\n"
            "Subject: A sua encomenda está a caminho\n"
            "Date: Tue, 17 Nov 2026 09:12:00 +0000\n"
        )
    )
    assert message.sender_name == "Serviços Exemplo"
    assert message.subject == "A sua encomenda está a caminho"


def test_plain_text_body() -> None:
    """A plain text e-mail gets links from its URLs."""
    message = _parse(
        _raw(
            "From: Example Store <orders@example-store.example>\n"
            "Subject: Your order is on its way\n"
            "Date: Tue, 17 Nov 2026 09:12:00 +0000\n",
            "Hi Alex,\n\n\n\nTrack it: https://www.ups.com/track?tracknum="
            "1Z999AA10123456784.\nThank you for your order!",
        )
    )
    assert message.text == (
        "Hi Alex,\n\nTrack it: https://www.ups.com/track?tracknum="
        "1Z999AA10123456784.\nThank you for your order!"
    )
    assert message.links == (
        Link("https://www.ups.com/track?tracknum=1Z999AA10123456784"),
    )
    assert message.language == "en"


def test_lenient_charsets() -> None:
    """Wrong or unknown charsets are decoded without errors."""
    raw = (
        b"From: shop@shop.example\nSubject: Test\n"
        b"Date: Tue, 17 Nov 2026 09:12:00 +0000\nMIME-Version: 1.0\n"
        b"Content-Type: text/plain; charset=x-unknown-charset\n\nEntrega: ter\xc3\xa7a\n"
    )
    assert _parse(raw).text == "Entrega: terça"
    raw = raw.replace(b"x-unknown-charset", b"us-ascii").replace(
        b"ter\xc3\xa7a", b"ter\xe7a"
    )
    assert _parse(raw).text.startswith("Entrega: ter")


@pytest.mark.parametrize(
    ("date_header", "expected"),
    [
        (
            "Date: Tue, 17 Nov 2026 09:12:00 +0100\n",
            datetime(2026, 11, 17, 9, 12, tzinfo=timezone(timedelta(hours=1))),
        ),
        (
            "Date: Tue, 17 Nov 2026 09:12:00\n",
            datetime(2026, 11, 17, 9, 12, tzinfo=UTC),
        ),
        (
            "Date: Tue, 17 Nov 2026 09:12:00 -0000\n",
            datetime(2026, 11, 17, 9, 12, tzinfo=UTC),
        ),
        ("Date: not a date\n", datetime(2026, 11, 17, 9, 10, 45, tzinfo=UTC)),
        ("", datetime(2026, 11, 17, 9, 10, 45, tzinfo=UTC)),
    ],
)
def test_dates(date_header: str, expected: datetime) -> None:
    """Dates are aware; a missing Date falls back to the topmost Received."""
    message = _parse(
        _raw(
            "Received: from mx.example.net by mx.google.com with ESMTPS id x1\n"
            "        for <alex@example.com>; Tue, 17 Nov 2026 01:10:45 -0800 (PST)\n"
            "Received: from relay.example.net by mx.example.net;"
            " Mon, 16 Nov 2026 01:00:00 +0000\n"
            f"From: shop@shop.example\n{date_header}"
        )
    )
    assert message.date == expected
    assert message.date.tzinfo is not None


def test_date_defaults_to_now() -> None:
    """Without Date and Received headers the date is now, in UTC."""
    before = datetime.now(UTC)
    message = _parse(_raw("From: shop@shop.example\n"))
    assert before <= message.date <= datetime.now(UTC)
    assert message.date.utcoffset() == timedelta(0)


def test_empty_and_odd_messages() -> None:
    """Messages without a body or From never raise."""
    message = _parse(b"Subject: Only a subject\n\n")
    assert message.sender == ""
    assert message.subject == "Only a subject"
    assert message.text == ""
    message = _parse(
        b"From: not an address\nMIME-Version: 1.0\n"
        b'Content-Type: multipart/mixed; boundary="b"\n\n--b\n'
        b"Content-Type: application/pdf\n\n%PDF\n--b--\n"
    )
    assert message.sender == ""
    assert message.text == ""
    assert message.links == ()


def test_graph_html_message() -> None:
    """A Graph message keeps the topmost Authentication-Results only."""
    message = message_from_graph(
        _graph("message_html.json"), mailbox="alex@example.com"
    )
    assert message.provider == "microsoft"
    assert message.provider_id == "AAMkAGExampleMessageId0001AAA="
    assert message.message_id == "<20261117091200.2001@mail.loja-exemplo.example>"
    assert message.sender == "encomendas@loja-exemplo.example"
    assert message.sender_name == "Loja Exemplo"
    assert message.reply_to == "apoio@loja-exemplo.example"
    assert message.subject == "A sua encomenda n.º 2001 foi enviada"
    assert message.date == datetime(2026, 11, 17, 9, 12, tzinfo=UTC)
    assert message.received == datetime(2026, 11, 17, 9, 12, 7, tzinfo=UTC)
    assert "Número de objeto: RR123456785PT" in message.text
    assert [link.text for link in message.links] == ["Seguir encomenda"]
    assert set(message.headers) == {
        "authentication-results",
        "content-language",
        "x-mailer",
        "list-id",
    }
    assert message.auth is not None
    assert message.auth.authserv_id is None
    assert message.auth.dkim_pass_domains == ("loja-exemplo.example",)
    assert message.language == "pt"
    verdict = verify_sender(message)
    assert verdict.authenticated
    assert verdict.method == "dmarc"
    assert verdict.reason == "unknown_sender"


def test_graph_text_message() -> None:
    """A Graph text message without headers uses receivedDateTime."""
    message = message_from_graph(
        _graph("message_text.json"), mailbox="alex@example.com"
    )
    assert (
        message.date == message.received == datetime(2026, 11, 17, 10, 15, tzinfo=UTC)
    )
    assert message.headers == {}
    assert message.auth is None
    assert message.reply_to is None
    assert message.text.startswith("Hi Alex,\n\nYour order #1001 is on its way.")
    assert message.links == (
        Link("https://www.ups.com/track?tracknum=1Z999AA10123456784"),
    )
    assert message.language == "en"
    assert verify_sender(message).reason == "no_auth_header"


def test_graph_odd_values() -> None:
    """Missing or wrongly typed Graph fields never raise."""
    message = message_from_graph(
        {
            "id": "x",
            "from": None,
            "replyTo": [{"emailAddress": None}, "bad"],
            "body": None,
            "sentDateTime": "not a date",
            "receivedDateTime": "2026-11-17T10:15:00Z",
            "internetMessageHeaders": [{"name": 1}, None, {"name": "X-Mailer"}],
        },
        mailbox="alex@example.com",
    )
    assert message.sender == ""
    assert message.text == ""
    assert message.headers == {}
    assert message.date == datetime(2026, 11, 17, 10, 15, tzinfo=UTC)
