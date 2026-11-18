# Local AI benchmark

Parcels can ask a local model to read e-mails that none of its parsers
understand (optional, off by default). The model runs in Ollama on the Home
Assistant host and is reached through Home Assistant's Ollama integration
and its AI task entity. This benchmark checks whether a model is good enough
for that job, and how fast it is on your hardware.

## The bar

A model passes when, after Parcels' checks:

- the tracking numbers of every e-mail are right (none missing, none
  extra), and
- at least 90% of the delivery dates (`eta_start`, `eta_end`) and at least
  90% of the kinds (order, shipped, delivered, ...) are right.

The report shows each field twice:

- **model**: the model's own answer, with only its formats normalized
  (dates to `YYYY-MM-DD`, times to `HH:MM`, carrier names to Parcels' carrier
  keys).
- **after checks**: what Parcels keeps of the answer. Numbers must appear in
  the e-mail as written and pass their format and check digit. Dates must
  fall between 2 days before and 60 days after the e-mail. Parcels' own
  tracking number detector adds the numbers the model missed. When a
  carrier sent the e-mail, the carrier is the sender's; the model's carrier
  is kept only when the e-mail names it or one of its numbers belongs to
  it; otherwise Parcels infers it from the sender's name or the tracking
  number. The bar is judged on this column.

How answers are compared:

| Field | Comparison |
|---|---|
| tracking and order numbers | as sets, ignoring case, spaces and dashes |
| merchant, pickup point | right when the answer contains the expected text; must be empty when nothing is expected |
| items | share of expected items found (an answer may add details such as a size) |
| pickup code | ignoring spaces |
| everything else | exact |

## The evaluation set

[`tests/ai_eval`](../tests/ai_eval) holds 41 synthetic e-mails:

- 10 in Portuguese, 7 in Spanish, 6 in English, 5 in German, 5 in French,
  4 in Italian and 4 in Dutch.
- They come from senders that have no dedicated Parcels parser, such as
  AliExpress, Temu, SHEIN, Zalando, Worten, Fnac, El Corte Inglés,
  PcComponentes, carriers without a parser, and small shops.
- Every kind is covered, including e-mails that are not about a parcel.
- They include free-text dates ("chega entre quinta e sábado", "3–5 business
  days", "distribuée demain"), time windows written as "9h", pickup codes,
  and traps such as opening hours, collection deadlines, refund periods and
  promotion end dates.
- `pt10` hides a prompt injection in invisible HTML. It asks the model to
  report the parcel as delivered, to use a URL as the merchant and to invent
  a tracking number.

[`expected.json`](../tests/ai_eval/expected.json) holds the right answer for
each e-mail. A missing key is not scored: e-mails about delivered parcels
have no delivery date fields, and e-mails that are not about a parcel have
no merchant. People, addresses and numbers are made up. The e-mails are
dated 16–25 November 2026 and read in `Europe/Lisbon` time.

`tests/ai/test_ai_eval.py` makes sure that a perfect answer for every
e-mail passes Parcels' checks unchanged. Run it after editing the set.

## Only ever use the synthetic set

The `ai_task.generate_data` action is recorded by Home Assistant. Its
instructions contain the whole e-mail and end up in the recorder database.
Never run real e-mail through it.

Parcels itself doesn't use the action. It calls the AI task through its
Python API, which isn't recorded. The e-mail text then stays in memory only
(Home Assistant keeps the AI task's chat log in memory for a few minutes).

## Set up the models on the Home Assistant host

1. Run Ollama on the Home Assistant host itself. Parcels refuses any other
   host, and also refuses the host's own LAN address because it can't tell
   it apart from another machine. Two setups work:
   - the [Ollama app](https://github.com/fratei/ha-apps) on Home Assistant
     OS, reached by its hostname over the internal `172.30.32.0/23` network;
   - Ollama on the same machine at `http://localhost:11434`.
2. Pull the candidate models: `qwen3:4b-instruct`, `gemma4:e4b` and
   `gemma4:12b`. Cloud models (tags ending in `cloud`) are refused.
3. Add the Ollama integration in Home Assistant with that URL.
4. Add one **AI task** to it per model, with:
   - **Context window size** 8192;
   - **Think before responding** off;
   - **Keep alive** -1, so the model stays loaded.

   Each AI task becomes an entity such as `ai_task.ollama_ai_task`.

## Run the benchmark

The script needs a development checkout of this repository with the test
requirements installed (it uses Parcels' own modules, which import Home
Assistant):

```sh
python3.14 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
```

### Through Home Assistant (the real setup)

Create a long-lived access token in your Home Assistant profile, then run
the set through the AI task entity over the REST API:

```sh
export HA_TOKEN=...   # the long-lived access token
.venv/bin/python scripts/ai_eval.py ha \
  --url http://homeassistant.local:8123 \
  --entity-id ai_task.ollama_ai_task \
  --out answers-qwen3-4b-instruct.jsonl
```

The script:

- sends one e-mail at a time and prints the seconds each one took;
- writes the answers to the `--out` file;
- prints the report;
- exits with 1 when the bar fails.

The first call includes loading the model, so prefer the median and p90
timings over the mean and maximum, or run the set twice. Repeat the run for
each AI task entity.

To try a single e-mail by hand:

1. Run `.venv/bin/python scripts/ai_eval.py build --entity-id ai_task.ollama_ai_task`.
   It prints one JSON line per e-mail, `{"id": ..., "data": ...}`, where
   `data` is the action data: task name, entity, instructions and output
   structure.
2. In Developer tools → Actions, switch to YAML mode and enter
   `action: ai_task.generate_data` followed by `data:` and one line's
   `data` (JSON is valid YAML).

To score answers collected by hand, write lines of
`{"id": "pt01", "data": {...}, "seconds": 7.2}` and run `score` on them.

### Against Ollama directly (development machines)

```sh
.venv/bin/python scripts/ai_eval.py ollama --model qwen3:4b-instruct \
  --out answers-dev.jsonl
```

This sends the same request as Home Assistant's Ollama AI task, except that
the answer isn't streamed:

- Home Assistant's AI task system prompt (with the current date and time)
  and the instructions;
- the output structure as a JSON schema in `format`;
- `num_ctx` 8192, thinking off and `keep_alive` -1 (change them with
  `--num-ctx`, `--think` and `--keep-alive`).

Use it to work on the instructions. Timings from another machine say
nothing about the Home Assistant host.

### Score again

```sh
.venv/bin/python scripts/ai_eval.py score answers-qwen3-4b-instruct.jsonl
.venv/bin/python scripts/ai_eval.py score answers-qwen3-4b-instruct.jsonl --json
```

The report lists every value that is wrong after checks. A missing answer
counts as wrong in every field.

## What the output structure looks like, and why

Early runs on a real host (`qwen3:4b-instruct`, context 8192, thinking off)
shaped the design.

| Observed | What Parcels does |
|---|---|
| Optional fields were sometimes left out, such as the end of a time window. | Every field is required. The descriptions ask for an empty string or an empty list when the e-mail doesn't say. |
| Date and time fields corrupted values: a local time came back as `09:00:00.000Z`, and 2026-11-19 came back as `1911-11-20`. | There are no date or time fields. Everything is plain text except the kind, which is a fixed list. |
| Values came back as written (`9h`, `13h`) or as `09:00:00`. | Parcels reads the forms in code: times such as `9h`, `9h30`, `9.30`, `13h00` and `09:00:00.000Z` (the offset is ignored); dates as `YYYY-MM-DD`, `dd/mm`, `dd/mm/yyyy`, `dd-mm-yyyy`, `dd.mm.yyyy`, or a day and month name in the seven languages, with the year taken from the e-mail's date. The 2-days-before to 60-days-after range rejects dates like `1911-11-20`. |
| The carrier came back empty when only the From line named it. | The input labels the sender name, the sender's domain, the subject, the received date and the body, and says that all of them are part of the e-mail. The carrier is free text that Parcels maps to its own keys ("CTT Expresso", "DPD Portugal", ...). Parcels takes the carrier from the sender's domain when a carrier sent the e-mail; when the model gives none, it infers it from the sender's name or the tracking number. |
| A DPD number written after "A sua encomenda" was missed once in two runs. | Parcels runs its own tracking number detector over the subject and body. The model's numbers only add candidates, kept when they appear in the e-mail and pass the format and check digit. A number that equals an order number, that the e-mail writes only as a delivery or pickup code, or that the e-mail labels as an order, phone or tax number, isn't used as a tracking number (unless its format identifies it, such as `EA123456785PT`), and a pickup code equal to a tracking or order number is dropped. |
| About 7 s per short e-mail once the model is loaded; calls are queued one at a time. | Parcels queues the e-mails that no parser understood and sends them one at a time. |

The model never sets the confidence. Parcels computes it:

- 0.8 when nothing was dropped and the answer has a checked identifier: a
  tracking number, an order number for an order confirmation, or nothing
  for an e-mail that isn't about a parcel;
- 0.5 otherwise, below the 0.7 that Parcels needs to apply an answer
  without review.

## Results

Fill in one row per run. Record the host's hardware (CPU, GPU, RAM), the
Home Assistant and Ollama versions, and the date.

| Model | Host hardware | Tracking, e-mails right of 41 (model / after checks) | Dates right of 74 | Kinds right of 41 | Bar | Median s | p90 s | Notes |
|---|---|---|---|---|---|---|---|---|
| qwen3:4b-instruct | | | | | | | | |
| gemma4:e4b | | | | | | | | |
| gemma4:12b | | | | | | | | |

Per field, after checks (model in parentheses):

| Field | qwen3:4b-instruct | gemma4:e4b | gemma4:12b |
|---|---|---|---|
| kind | | | |
| merchant | | | |
| carrier | | | |
| tracking_numbers | | | |
| order_numbers | | | |
| eta_start | | | |
| eta_end | | | |
| window_start | | | |
| window_end | | | |
| pickup_point | | | |
| pickup_code | | | |
| items (recall) | | | |
