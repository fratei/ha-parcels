"""Benchmark the local AI extraction on the synthetic evaluation set.

The set in ``tests/ai_eval`` holds synthetic e-mails (``<id>.eml``) and the
expected answer for each of them (``expected.json``; a missing key is not
scored). Commands:

``build``
    Write one JSON line per e-mail with the data for Home Assistant's
    ``ai_task.generate_data`` action: the task name, an entity ID, the
    instructions Parcels sends (fixed rules plus the e-mail) and the output
    structure in the action's format.
``ha``
    Run the set through an AI task entity of a Home Assistant instance over
    its REST API, one e-mail at a time, and write the answers.
``ollama``
    Run the set directly against an Ollama server, the way Home Assistant's
    Ollama integration calls it (for development machines).
``score``
    Score a JSON Lines file of answers (``{"id", "data", "seconds"}``).

The ``ai_task.generate_data`` action is recorded by Home Assistant (the
instructions, which contain the e-mail, end up in the recorder database), so
only ever run it with this synthetic set, never with real e-mail. Parcels
itself calls the AI task through its Python API, which isn't recorded.

Scores are given twice: "model" is the model's own answer with only its
formats normalized, "after checks" is what Parcels keeps after validating
the answer (verbatim checks, check digits, date range, its own tracking
number detector, carrier inference). The bar is judged after checks.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime, time
import json
import os
from pathlib import Path
import statistics
import sys
import time as clock
from typing import Any, TextIO
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from custom_components.parcels.ai.prompt import (  # noqa: E402
    SERVICE_STRUCTURE,
    build_prompt,
    json_schema,
    received_at,
)
from custom_components.parcels.ai.validate import (  # noqa: E402
    Validation,
    map_carrier,
    normalize_date,
    normalize_time,
    validate_output,
)
from custom_components.parcels.parsers.base import MailMessage  # noqa: E402
from custom_components.parcels.parsers.lang import fold  # noqa: E402
from custom_components.parcels.parsers.normalize import (  # noqa: E402
    message_from_bytes,
)

EVAL_DIR = ROOT / "tests" / "ai_eval"
EVAL_TZ = ZoneInfo("Europe/Lisbon")
MAILBOX = "alex@example.com"
TASK_NAME = "parcels"
PLACEHOLDER_ENTITY_ID = "ai_task.your_ollama_ai_task"
DEFAULT_TIMEOUT = 300.0

# The system prompt Home Assistant's AI task sends before the instructions:
# ai_task.const.DEFAULT_SYSTEM_PROMPT plus helpers.llm.DATE_TIME_PROMPT
# (Home Assistant 2026.11). It holds the host's date, not the e-mail's.
HA_SYSTEM_PROMPT = "You are a Home Assistant expert and help users with their tasks."

SCORED_FIELDS: tuple[str, ...] = (
    "kind",
    "merchant",
    "carrier",
    "tracking_numbers",
    "order_numbers",
    "eta_start",
    "eta_end",
    "window_start",
    "window_end",
    "pickup_point",
    "pickup_code",
    "items",
)
DATE_FIELDS: tuple[str, ...] = ("eta_start", "eta_end")
TIME_FIELDS: tuple[str, ...] = ("window_start", "window_end")
NUMBER_FIELDS: tuple[str, ...] = ("tracking_numbers", "order_numbers")
CONTAINED_FIELDS: tuple[str, ...] = ("merchant", "pickup_point")
BAR_SHARE = 0.9

Caller = Callable[[Mapping[str, Any]], Any]


# --- the evaluation set ---------------------------------------------------


def load_expected(directory: Path = EVAL_DIR) -> dict[str, dict[str, Any]]:
    """Return the expected answer for every e-mail, by e-mail ID."""
    with (directory / "expected.json").open(encoding="utf-8") as file:
        expected: dict[str, dict[str, Any]] = json.load(file)
    return dict(sorted(expected.items()))


def load_message(email_id: str, directory: Path = EVAL_DIR) -> MailMessage:
    """Load one e-mail of the set the way Parcels reads a Gmail message."""
    path = directory / f"{email_id}.eml"
    return message_from_bytes(
        path.read_bytes(), mailbox=MAILBOX, provider_id=path.name, provider="google"
    )


def load_messages(directory: Path = EVAL_DIR) -> dict[str, MailMessage]:
    """Return every e-mail of the set, by e-mail ID in ID order."""
    return {
        path.stem: load_message(path.stem, directory)
        for path in sorted(directory.glob("*.eml"))
    }


def build_payloads(
    entity_id: str = PLACEHOLDER_ENTITY_ID,
    messages: Mapping[str, MailMessage] | None = None,
) -> list[dict[str, Any]]:
    """Return the ``ai_task.generate_data`` action data for every e-mail."""
    if messages is None:
        messages = load_messages()
    return [
        {
            "id": email_id,
            "data": {
                "task_name": TASK_NAME,
                "entity_id": entity_id,
                "instructions": build_prompt(message, EVAL_TZ),
                "structure": SERVICE_STRUCTURE,
            },
        }
        for email_id, message in messages.items()
    ]


# --- views of an answer ---------------------------------------------------


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return " ".join(value.split()) or None


def _texts(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _text(item))]


def _hhmm(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def model_view(data: Any, message: MailMessage) -> dict[str, Any] | None:
    """Return the model's own answer with only its formats normalized.

    Dates become ``YYYY-MM-DD`` and times ``HH:MM`` when they can be read
    (otherwise the text is kept, so it counts as wrong), and carrier names
    are mapped to Parcels' carrier keys. Nothing is checked or inferred.
    """
    if not isinstance(data, Mapping):
        return None
    reference = received_at(message, EVAL_TZ).date()
    kind = _text(data.get("kind"))
    carrier = _text(data.get("carrier"))
    view: dict[str, Any] = {
        "kind": kind.lower() if kind else None,
        "merchant": _text(data.get("merchant")),
        "carrier": (map_carrier(carrier) or carrier) if carrier else None,
        "tracking_numbers": _texts(data.get("tracking_numbers")),
        "order_numbers": _texts(data.get("order_numbers")),
        "pickup_point": _text(data.get("pickup_point")),
        "pickup_code": _text(data.get("pickup_code")),
        "items": _texts(data.get("items")),
    }
    for field in DATE_FIELDS:
        text = _text(data.get(field))
        found = normalize_date(text, reference) if text else None
        view[field] = found.isoformat() if found else text
    for field in TIME_FIELDS:
        text = _text(data.get(field))
        found_time = normalize_time(text) if text else None
        view[field] = _hhmm(found_time) or text
    return view


def final_view(validation: Validation) -> dict[str, Any] | None:
    """Return what Parcels keeps of an answer after validating it."""
    result = validation.result
    if result is None:
        return None
    shipments = result.shipments
    eta = next((s.eta for s in shipments if s.eta is not None), None)
    return {
        "kind": result.kind.value,
        "merchant": result.merchant,
        "carrier": next((s.carrier for s in shipments if s.carrier), None),
        "tracking_numbers": [s.tracking_number for s in shipments if s.tracking_number],
        "order_numbers": list(result.order_numbers),
        "eta_start": eta.start.isoformat() if eta else None,
        "eta_end": eta.end.isoformat() if eta else None,
        "window_start": _hhmm(eta.window_start) if eta else None,
        "window_end": _hhmm(eta.window_end) if eta else None,
        "pickup_point": next(
            (s.pickup_point for s in shipments if s.pickup_point), None
        ),
        "pickup_code": next((s.pickup_code for s in shipments if s.pickup_code), None),
        "items": list(result.items),
    }


# --- scoring --------------------------------------------------------------


def _compact(value: str) -> str:
    return "".join(char for char in value.upper() if char.isalnum())


def _folded(value: str | None) -> str:
    return " ".join(fold(value or "").split())


def _item_matches(expected: str, got: str) -> bool:
    want, have = _folded(expected), _folded(got)
    if not want or not have:
        return False
    return want in have or (have in want and 2 * len(have) >= len(want))


def items_found(expected: Sequence[str], got: Sequence[str]) -> int:
    """Return how many expected items appear among the answered items.

    An item counts when the answer contains its name, or when the answer is
    a part of the name at least half as long (case and accents ignored).
    """
    return sum(1 for item in expected if any(_item_matches(item, g) for g in got))


def field_correct(field: str, expected: Any, got: Any) -> bool:
    """Return whether one answered field matches the expected value.

    Numbers are compared as sets, ignoring case, spaces and dashes; merchant
    and pickup point are right when the answer contains the expected text
    (and empty when nothing is expected); items are right when every
    expected item was found.
    """
    if field in NUMBER_FIELDS:
        want = {_compact(value) for value in expected or ()}
        have = {_compact(value) for value in got or ()} - {""}
        return want == have
    if field in CONTAINED_FIELDS:
        if not expected:
            return not got
        return bool(got) and _folded(expected) in _folded(got)
    if field == "pickup_code":
        return _compact(expected or "") == _compact(got or "")
    if field == "items":
        return items_found(expected or (), got or ()) == len(expected or ())
    return (expected or None) == (got or None)


def _share(right: int, total: int) -> float | None:
    return right / total if total else None


def _timings(values: Sequence[float]) -> dict[str, float] | None:
    if not values:
        return None
    ordered = sorted(values)
    p90 = statistics.quantiles(ordered, n=10)[-1] if len(ordered) > 1 else ordered[0]
    return {
        "n": len(ordered),
        "mean": statistics.fmean(ordered),
        "median": statistics.median(ordered),
        "p90": p90,
        "max": ordered[-1],
        "total": sum(ordered),
    }


def score(
    answers: Iterable[Mapping[str, Any]],
    expected: Mapping[str, Mapping[str, Any]] | None = None,
    messages: Mapping[str, MailMessage] | None = None,
) -> dict[str, Any]:
    """Score answers against the expected values and return a report.

    ``answers`` are mappings with ``id``, ``data`` (the AI task's answer)
    and optionally ``seconds`` and ``error``. E-mails without an answer
    count as wrong in every field.
    """
    if expected is None:
        expected = load_expected()
    if messages is None:
        messages = {email_id: load_message(email_id) for email_id in expected}
    by_id = {str(answer.get("id")): answer for answer in answers}
    counts = {field: {"model": 0, "final": 0, "scored": 0} for field in SCORED_FIELDS}
    items = {"model": 0, "final": 0, "expected": 0}
    tracking = {"model": 0, "final": 0, "scored": 0}
    dates = {"right": 0, "scored": 0}
    kinds = {"right": 0, "scored": 0}
    missing: list[str] = []
    unusable: list[str] = []
    errors: dict[str, str] = {}
    wrong: list[dict[str, Any]] = []
    seconds: list[float] = []

    for email_id, want in expected.items():
        answer = by_id.get(email_id)
        data: Any = None
        if answer is None:
            missing.append(email_id)
        else:
            data = answer.get("data")
            if answer.get("error"):
                errors[email_id] = str(answer["error"])
            if isinstance(answer.get("seconds"), int | float):
                seconds.append(float(answer["seconds"]))
        message = messages[email_id]
        model = model_view(data, message)
        final = (
            final_view(validate_output(data, message, EVAL_TZ))
            if isinstance(data, Mapping)
            else None
        )
        if answer is not None and final is None:
            unusable.append(email_id)
        for field in SCORED_FIELDS:
            if field not in want:
                continue
            counts[field]["scored"] += 1
            model_ok = model is not None and field_correct(
                field, want[field], model[field]
            )
            final_ok = final is not None and field_correct(
                field, want[field], final[field]
            )
            counts[field]["model"] += model_ok
            counts[field]["final"] += final_ok
            if not final_ok:
                wrong.append(
                    {
                        "id": email_id,
                        "field": field,
                        "expected": want[field],
                        "got": final[field] if final is not None else None,
                    }
                )
            if field == "items":
                items["expected"] += len(want[field] or ())
                if model is not None:
                    items["model"] += items_found(want[field] or (), model[field])
                if final is not None:
                    items["final"] += items_found(want[field] or (), final[field])
            elif field == "tracking_numbers":
                tracking["scored"] += 1
                tracking["model"] += model_ok
                tracking["final"] += final_ok
            elif field in DATE_FIELDS:
                dates["scored"] += 1
                dates["right"] += final_ok
            elif field == "kind":
                kinds["scored"] += 1
                kinds["right"] += final_ok

    fields: dict[str, dict[str, Any]] = {}
    for field, count in counts.items():
        if field == "items":
            fields[field] = {
                "model": _share(items["model"], items["expected"]),
                "final": _share(items["final"], items["expected"]),
                "scored": items["expected"],
            }
        else:
            fields[field] = {
                "model": _share(count["model"], count["scored"]),
                "final": _share(count["final"], count["scored"]),
                "scored": count["scored"],
            }
    dates_share = _share(dates["right"], dates["scored"])
    kinds_share = _share(kinds["right"], kinds["scored"])
    bar = {
        "tracking": tracking["final"] == tracking["scored"],
        "dates": dates_share is not None and dates_share >= BAR_SHARE,
        "kinds": kinds_share is not None and kinds_share >= BAR_SHARE,
    }
    bar["passed"] = all(bar.values())
    return {
        "emails": len(expected),
        "answers": len(expected) - len(missing),
        "missing": missing,
        "unusable": unusable,
        "errors": errors,
        "fields": fields,
        "tracking": tracking,
        "dates": {**dates, "share": dates_share},
        "kinds": {**kinds, "share": kinds_share},
        "bar": bar,
        "seconds": _timings(seconds),
        "wrong": wrong,
    }


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{100 * value:.1f}%"


def format_report(report: Mapping[str, Any]) -> str:
    """Return a score report as plain text."""
    lines = [
        f"E-mails: {report['emails']}, answers: {report['answers']}, "
        f"unusable: {len(report['unusable'])}, errors: {len(report['errors'])}",
        "",
        f"{'field':<20}{'model':>9}{'after checks':>15}{'scored':>9}",
    ]
    for field, values in report["fields"].items():
        name = "items (recall)" if field == "items" else field
        lines.append(
            f"{name:<20}{_percent(values['model']):>9}"
            f"{_percent(values['final']):>15}{values['scored']:>9}"
        )
    tracking = report["tracking"]
    dates = report["dates"]
    kinds = report["kinds"]
    bar = report["bar"]
    lines += [
        "",
        "Tracking numbers right in every e-mail: "
        f"{'yes' if bar['tracking'] else 'no'} "
        f"({tracking['final']}/{tracking['scored']}; "
        f"model alone {tracking['model']}/{tracking['scored']})",
        f"Dates right: {_percent(dates['share'])} ({dates['right']}/{dates['scored']})",
        f"Kinds right: {_percent(kinds['share'])} ({kinds['right']}/{kinds['scored']})",
        "Bar (every tracking number right, at least 90% of dates and kinds): "
        + ("PASS" if bar["passed"] else "FAIL"),
    ]
    if timings := report["seconds"]:
        lines.append(
            f"Seconds per e-mail: n={timings['n']} mean={timings['mean']:.1f} "
            f"median={timings['median']:.1f} p90={timings['p90']:.1f} "
            f"max={timings['max']:.1f} total={timings['total']:.0f}"
        )
    if report["missing"]:
        lines.append(f"Missing answers: {', '.join(report['missing'])}")
    if report["unusable"]:
        lines.append(f"Unusable answers: {', '.join(report['unusable'])}")
    lines += [f"Error {key}: {error}" for key, error in report["errors"].items()]
    if report["wrong"]:
        lines += ["", "Wrong after checks:"]
        lines += [
            f"  {entry['id']} {entry['field']}: expected "
            f"{json.dumps(entry['expected'], ensure_ascii=False)}, got "
            f"{json.dumps(entry['got'], ensure_ascii=False)}"
            for entry in report["wrong"]
        ]
    return "\n".join(lines)


# --- running the set ------------------------------------------------------


def ha_system_prompt(now: datetime) -> str:
    """Return the system prompt Home Assistant's AI task sends with a task."""
    return (
        f"{HA_SYSTEM_PROMPT}\n"
        f"Current time is {now:%H:%M:%S}. Today's date is {now:%Y-%m-%d}.\n"
    )


def post_json(
    url: str, body: Mapping[str, Any], headers: Mapping[str, str], timeout: float
) -> Any:
    """POST a JSON body and return the decoded JSON reply."""
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


def ha_caller(url: str, token: str, *, timeout: float = DEFAULT_TIMEOUT) -> Caller:
    """Return a function that runs one task through Home Assistant's REST API."""
    endpoint = f"{url.rstrip('/')}/api/services/ai_task/generate_data?return_response"
    headers = {"Authorization": f"Bearer {token}"}

    def call(data: Mapping[str, Any]) -> Any:
        reply = post_json(endpoint, data, headers, timeout)
        return reply["service_response"]["data"]

    return call


def ollama_caller(
    url: str,
    model: str,
    *,
    num_ctx: int = 8192,
    keep_alive: int | str = -1,
    think: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
    now: Callable[[], datetime] = datetime.now,
) -> Caller:
    """Return a function that runs one task against Ollama's chat API.

    The request mirrors Home Assistant's Ollama AI task: its system prompt,
    the instructions as the user message, and the output structure as a
    JSON schema in ``format``.
    """
    endpoint = f"{url.rstrip('/')}/api/chat"
    schema = json_schema()

    def call(data: Mapping[str, Any]) -> Any:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": ha_system_prompt(now())},
                {"role": "user", "content": data["instructions"]},
            ],
            "stream": False,
            "format": schema,
            "options": {"num_ctx": num_ctx},
            "think": think,
            "keep_alive": keep_alive,
        }
        reply = post_json(endpoint, body, {}, timeout)
        return json.loads(reply["message"]["content"])

    return call


def run_set(
    call: Caller,
    payloads: Iterable[Mapping[str, Any]],
    out: TextIO,
    *,
    progress: TextIO | None = None,
) -> list[dict[str, Any]]:
    """Run every payload, one at a time, and write one answer line each."""
    answers = []
    for payload in payloads:
        started = clock.monotonic()
        error = None
        try:
            data = call(payload["data"])
        except (OSError, ValueError, KeyError, TypeError) as err:
            data, error = None, f"{type(err).__name__}: {err}"
        answer: dict[str, Any] = {
            "id": payload["id"],
            "data": data,
            "seconds": round(clock.monotonic() - started, 3),
        }
        if error:
            answer["error"] = error
        out.write(json.dumps(answer, ensure_ascii=False) + "\n")
        out.flush()
        if progress is not None:
            status = f" ({error})" if error else ""
            progress.write(f"{answer['id']}: {answer['seconds']:.1f} s{status}\n")
        answers.append(answer)
    return answers


def read_answers(file: TextIO) -> list[dict[str, Any]]:
    """Read answers from JSON Lines, skipping empty lines."""
    return [json.loads(line) for line in file if line.strip()]


def _keep_alive(value: str) -> int | str:
    try:
        return int(value)
    except ValueError:
        return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark Parcels' local AI extraction on the synthetic set."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="write ai_task.generate_data data")
    build.add_argument("--entity-id", default=PLACEHOLDER_ENTITY_ID)
    build.add_argument("--out", type=Path, help="JSON Lines file (default: stdout)")

    score_cmd = commands.add_parser("score", help="score a JSON Lines answer file")
    score_cmd.add_argument("answers", help="answer file, or - for stdin")
    score_cmd.add_argument("--json", action="store_true", help="print JSON")

    ha = commands.add_parser("ha", help="run the set through Home Assistant")
    ha.add_argument("--url", required=True, help="e.g. http://homeassistant.local:8123")
    ha.add_argument("--entity-id", required=True, help="the Ollama AI task entity")
    ha.add_argument(
        "--token-env",
        default="HA_TOKEN",
        help="environment variable holding a long-lived access token",
    )
    ha.add_argument("--out", type=Path, required=True, help="answer file to write")
    ha.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)

    ollama = commands.add_parser("ollama", help="run the set against Ollama")
    ollama.add_argument("--url", default="http://localhost:11434")
    ollama.add_argument("--model", required=True, help="e.g. qwen3:4b-instruct")
    ollama.add_argument("--num-ctx", type=int, default=8192)
    ollama.add_argument("--keep-alive", type=_keep_alive, default=-1)
    ollama.add_argument("--think", action="store_true", help="let the model think")
    ollama.add_argument("--out", type=Path, required=True, help="answer file to write")
    ollama.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    return parser


def _write_lines(rows: Iterable[Mapping[str, Any]], out: TextIO) -> None:
    for row in rows:
        out.write(json.dumps(row, ensure_ascii=False) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line; return the exit code (1 when the bar fails)."""
    args = _parser().parse_args(argv)
    if args.command == "build":
        payloads = build_payloads(args.entity_id)
        if args.out is None:
            _write_lines(payloads, sys.stdout)
        else:
            with args.out.open("w", encoding="utf-8") as file:
                _write_lines(payloads, file)
        return 0

    if args.command == "score":
        if args.answers == "-":
            answers = read_answers(sys.stdin)
        else:
            with Path(args.answers).open(encoding="utf-8") as file:
                answers = read_answers(file)
        report = score(answers)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(format_report(report))
        return 0 if report["bar"]["passed"] else 1

    if args.command == "ha":
        token = os.environ.get(args.token_env)
        if not token:
            print(
                f"Set {args.token_env} to a long-lived access token.", file=sys.stderr
            )
            return 2
        call = ha_caller(args.url, token, timeout=args.timeout)
        payloads = build_payloads(args.entity_id)
    else:
        call = ollama_caller(
            args.url,
            args.model,
            num_ctx=args.num_ctx,
            keep_alive=args.keep_alive,
            think=args.think,
            timeout=args.timeout,
        )
        payloads = build_payloads()
    with args.out.open("w", encoding="utf-8") as file:
        answers = run_set(call, payloads, file, progress=sys.stderr)
    report = score(answers)
    print(format_report(report))
    return 0 if report["bar"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
