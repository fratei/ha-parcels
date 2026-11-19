"""Tests for the AI benchmark script and its synthetic evaluation set.

The script is run on canned answers; no model and no network are used.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import importlib.util
import io
import json
from pathlib import Path
import types
from typing import Any

import pytest

from custom_components.parcels.ai.prompt import (
    SERVICE_STRUCTURE,
    build_prompt,
    json_schema,
)
from custom_components.parcels.ai.validate import validate_output
from custom_components.parcels.const import CARRIER_NAMES, MailKind
from custom_components.parcels.parsers.base import MailMessage

from .common import make_message

ROOT = Path(__file__).resolve().parents[2]
LANGUAGES = {"pt", "es", "en", "de", "fr", "it", "nl"}


def _load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        "parcels_ai_eval", ROOT / "scripts" / "ai_eval.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ai_eval = _load_script()

EvalSet = tuple[dict[str, dict[str, Any]], dict[str, MailMessage]]


@pytest.fixture(scope="module")
def eval_set() -> EvalSet:
    """Return the expected answers and the parsed e-mails of the set."""
    return ai_eval.load_expected(), ai_eval.load_messages()


def perfect_answer(want: Mapping[str, Any]) -> dict[str, Any]:
    """Return the answer a perfect model gives, in the model's own format."""
    carrier = want.get("carrier")
    data: dict[str, Any] = {
        field: want.get(field) or ""
        for field in ai_eval.SCORED_FIELDS
        if field not in ("carrier", "tracking_numbers", "order_numbers", "items")
    }
    data.update(
        carrier=CARRIER_NAMES[carrier] if carrier else "",
        tracking_numbers=list(want.get("tracking_numbers") or ()),
        order_numbers=list(want.get("order_numbers") or ()),
        items=list(want.get("items") or ()),
    )
    return data


def perfect_answers(
    expected: Mapping[str, Mapping[str, Any]], seconds: float = 7.0
) -> list[dict[str, Any]]:
    """Return perfect answer lines for the whole set."""
    return [
        {"id": email_id, "data": perfect_answer(want), "seconds": seconds}
        for email_id, want in expected.items()
    ]


def test_eval_set_is_complete(eval_set: EvalSet) -> None:
    """Every e-mail has an expected answer, and the set covers every kind."""
    expected, messages = eval_set
    assert set(messages) == set(expected)
    assert len(expected) >= 40
    assert {want["language"] for want in expected.values()} == LANGUAGES
    assert {want["kind"] for want in expected.values()} == {
        kind.value
        for kind in MailKind
        if kind not in (MailKind.UNKNOWN, MailKind.CODE, MailKind.CUSTOMER_RETURN)
    }
    for email_id, want in expected.items():
        assert messages[email_id].language == want["language"]
        assert want.get("carrier") is None or want["carrier"] in CARRIER_NAMES


def test_perfect_answers_pass_the_checks(eval_set: EvalSet) -> None:
    """Parcels keeps every expected value, so the expected answers agree."""
    expected, messages = eval_set
    answers = perfect_answers(expected)
    for answer in answers:
        validation = validate_output(
            answer["data"], messages[answer["id"]], ai_eval.EVAL_TZ
        )
        assert validation.errors == (), answer["id"]

    report = ai_eval.score(answers, expected, messages)

    assert report["wrong"] == []
    assert report["unusable"] == []
    assert report["missing"] == []
    for field, values in report["fields"].items():
        assert values["model"] == values["final"] == 1.0, field
    assert report["bar"] == {
        "tracking": True,
        "dates": True,
        "kinds": True,
        "passed": True,
    }
    assert report["seconds"]["n"] == len(expected)
    assert report["seconds"]["median"] == 7.0


def test_missed_number_is_recovered_after_checks(eval_set: EvalSet) -> None:
    """A number the model missed counts only against the model column."""
    expected, messages = eval_set
    answers = perfect_answers(expected)
    missed = next(a for a in answers if a["id"] == "pt05")
    missed["data"]["tracking_numbers"] = []

    report = ai_eval.score(answers, expected, messages)

    tracking = report["tracking"]
    assert tracking["final"] == tracking["scored"]
    assert tracking["model"] == tracking["scored"] - 1
    assert report["bar"]["passed"]


def test_missing_answer_fails_the_bar(eval_set: EvalSet) -> None:
    """An e-mail without an answer counts as wrong in every field."""
    expected, messages = eval_set
    answers = [a for a in perfect_answers(expected) if a["id"] != "pt02"]

    report = ai_eval.score(answers, expected, messages)

    assert report["missing"] == ["pt02"]
    assert not report["bar"]["tracking"]
    assert not report["bar"]["passed"]
    assert {(entry["id"], entry["field"]) for entry in report["wrong"]} == {
        ("pt02", field) for field in ai_eval.SCORED_FIELDS if field in expected["pt02"]
    }


def test_wrong_kinds_fail_the_bar(eval_set: EvalSet) -> None:
    """More than 10% wrong kinds fails the bar."""
    expected, messages = eval_set
    answers = perfect_answers(expected)
    for answer in answers[:5]:
        answer["data"]["kind"] = (
            "order" if answer["data"]["kind"] == "not_parcel" else "not_parcel"
        )

    report = ai_eval.score(answers, expected, messages)

    assert report["kinds"]["right"] == len(expected) - 5
    assert not report["bar"]["kinds"]
    assert not report["bar"]["passed"]


@pytest.mark.parametrize(
    ("field", "expected", "got", "right"),
    [
        ("tracking_numbers", ["RR482137560PT"], ["rr 482 137 560 pt"], True),
        ("tracking_numbers", ["RR482137560PT"], ["RR482137560PT", "X1"], False),
        ("tracking_numbers", [], [""], True),
        ("merchant", "Decathlon", "Decathlon España", True),
        ("merchant", None, "FedEx", False),
        ("merchant", None, None, True),
        ("pickup_code", "739 215", "739215", True),
        ("items", ["Luzes LED de fada"], ["Luzes LED de fada 10 m"], True),
        ("items", ["Pasta di Gragnano"], ["Pasta"], False),
        ("eta_start", "2026-11-19", "2026-11-20", False),
        ("window_end", None, None, True),
    ],
)
def test_field_correct(field: str, expected: Any, got: Any, right: bool) -> None:
    """Fields are compared the way the benchmark documents."""
    assert ai_eval.field_correct(field, expected, got) is right


def test_model_view_normalizes_formats_only() -> None:
    """The model column reads the model's formats but checks nothing."""
    message = make_message("Entrega amanhã entre as 9h e as 13h.")
    data = {
        "kind": "Shipped",
        "carrier": "DPD Portugal",
        "eta_start": "19/11",
        "eta_end": "2026-11-19T00:00:00.000Z",
        "window_start": "9h",
        "window_end": "13:00:00.000Z",
        "tracking_numbers": ["99999999999999"],
        "merchant": "",
    }

    view = ai_eval.model_view(data, message)

    assert view is not None
    assert view["kind"] == "shipped"
    assert view["carrier"] == "dpd"
    assert (view["eta_start"], view["eta_end"]) == ("2026-11-19", "2026-11-19")
    assert (view["window_start"], view["window_end"]) == ("09:00", "13:00")
    assert view["tracking_numbers"] == ["99999999999999"]
    assert view["merchant"] is None


def test_cli_build_and_score(
    eval_set: EvalSet,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``build`` writes the action data and ``score`` judges canned answers."""
    expected, messages = eval_set

    assert ai_eval.main(["build", "--entity-id", "ai_task.ollama"]) == 0
    lines = capsys.readouterr().out.splitlines()

    payloads = [json.loads(line) for line in lines]
    assert [payload["id"] for payload in payloads] == list(messages)
    structure = json.loads(json.dumps(SERVICE_STRUCTURE))
    for payload in payloads:
        message = messages[payload["id"]]
        assert payload["data"] == {
            "task_name": "parcels",
            "entity_id": "ai_task.ollama",
            "instructions": build_prompt(message, ai_eval.EVAL_TZ),
            "structure": structure,
        }

    canned = "".join(
        json.dumps(answer, ensure_ascii=False) + "\n"
        for answer in perfect_answers(expected)
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(canned))
    assert ai_eval.main(["score", "-"]) == 0
    assert "Bar (every tracking number right" in capsys.readouterr().out

    wrong = canned.replace('"kind": "', '"kind": "x')
    monkeypatch.setattr("sys.stdin", io.StringIO(wrong))
    assert ai_eval.main(["score", "-", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["unusable"] == list(expected)
    assert not report["bar"]["passed"]


def test_ollama_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Ollama runner sends what Home Assistant's Ollama AI task sends."""
    calls: list[tuple[str, dict[str, Any]]] = []

    def post_json(url: str, body: Any, headers: Any, timeout: float) -> Any:
        calls.append((url, body))
        return {"message": {"content": '{"kind": "order"}'}}

    monkeypatch.setattr(ai_eval, "post_json", post_json)
    call = ai_eval.ollama_caller(
        "http://localhost:11434/",
        "qwen3:4b-instruct",
        now=lambda: datetime(2026, 11, 18, 9, 30, 5),
    )

    assert call({"instructions": "the prompt"}) == {"kind": "order"}
    url, body = calls[0]
    assert url == "http://localhost:11434/api/chat"
    assert body == {
        "model": "qwen3:4b-instruct",
        "messages": [
            {
                "role": "system",
                "content": ai_eval.HA_SYSTEM_PROMPT
                + "\nCurrent time is 09:30:05. Today's date is 2026-11-18.\n",
            },
            {"role": "user", "content": "the prompt"},
        ],
        "stream": False,
        "format": json_schema(),
        "options": {"num_ctx": 8192},
        "think": False,
        "keep_alive": -1,
    }


def test_ha_request_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Home Assistant runner calls the action; failures are recorded."""
    calls: list[tuple[str, Any, Any]] = []

    def post_json(url: str, body: Any, headers: Any, timeout: float) -> Any:
        calls.append((url, body, headers))
        if body["entity_id"] == "ai_task.down":
            raise OSError("connection refused")
        return {"changed_states": [], "service_response": {"data": {"kind": "order"}}}

    monkeypatch.setattr(ai_eval, "post_json", post_json)
    call = ai_eval.ha_caller("http://ha.local:8123/", "secret")
    out = io.StringIO()

    answers = ai_eval.run_set(
        call,
        [
            {"id": "a", "data": {"entity_id": "ai_task.ollama"}},
            {"id": "b", "data": {"entity_id": "ai_task.down"}},
        ],
        out,
    )

    url, _, headers = calls[0]
    assert url == (
        "http://ha.local:8123/api/services/ai_task/generate_data?return_response"
    )
    assert headers == {"Authorization": "Bearer secret"}
    assert answers[0]["data"] == {"kind": "order"}
    assert answers[1]["data"] is None
    assert answers[1]["error"] == "OSError: connection refused"
    assert ai_eval.read_answers(io.StringIO(out.getvalue())) == answers
