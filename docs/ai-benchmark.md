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
  number. The kind, the delivery dates, the merchant and the pickup point
  are also checked against the e-mail's own wording (see
  [below](#what-the-first-full-run-showed)). The bar is judged on this
  column.

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
  a tracking number. Parcels leaves hidden HTML out of the text it reads
  (see [below](#what-the-held-out-set-showed)), so the model no longer sees
  it.

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

The action's structure can't carry the caps that Parcels puts on lists and
text (see [below](#what-the-output-structure-looks-like-and-why)), so this
run goes without them. They only stop an answer that runs away.

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
- the output structure as a JSON schema in `format`, with the caps that
  Parcels sends;
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
| A long e-mail can keep a small model writing until Home Assistant's 5-minute limit: Ollama doesn't limit an answer's length unless asked. | Every list and text field has a cap, which Ollama turns into a limit on what the model can write: 10 entries per list, 40 characters for a number or code, 100 for a merchant, carrier or item, 200 for a pickup point, 60 for a date and 30 for a time. The caps are well above real values (the longest item in the first full run had 37 characters), so a value as long as its cap was cut off: Parcels drops it, or ends an item with "…". An e-mail whose last try runs out of time goes to review as "The local AI took too long on this e-mail". |

The model never sets the confidence. Parcels computes it:

- 0.8 when no check failed and the answer has a checked identifier: a
  tracking number, Paack's shipment reference, an order number for an order
  confirmation, or nothing for an e-mail that isn't about a parcel;
- 0.5 otherwise, below the 0.7 that Parcels needs to apply an answer
  without review.

### What the first full run showed

The first run of the whole set (`qwen3:4b-instruct`) failed the bar on
dates and kinds. Its mistakes were patterns, not one-offs, so each one has a
short rule in the instructions and a check in code. The checks only drop a
value, move it to another field or take it from the e-mail's own text; they
never invent one.

| Observed | What Parcels does |
|---|---|
| Deadlines came back as delivery dates: the last day to collect a parcel, to pay import duties, or to return an item or get a refund. | The instructions say a deadline is never a delivery date. Parcels reads every date in the e-mail with its parsers' date reader, which tells delivery dates from deadlines (a "deadline", "last day" or "Frist" word, or "until", "by", "até", "hasta", "bis", "jusqu'au", "entro", "tot" with a collect, pay, return or hold wording), order and shipping dates, and replaced dates ("foi adiada", "bisher", "vom … auf …", "was"). A model date the e-mail gives only as one of those is dropped, and so is a model date that had passed when the e-mail arrived or one in an e-mail that mentions no date, weekday or span at all. Ready for pickup, customs, delivered, return, cancelled and not-a-parcel e-mails get no delivery date. |
| Spans such as "3–5 business days" or "quinta a sábado" were counted wrongly. | When the e-mail writes a delivery date or span next to a delivery phrase, Parcels works it out from the received date and uses it instead of a different model date. |
| Kinds jumped a step: an order confirmation came back as shipped, out for delivery as delivered, a missed delivery as out for delivery. | The instructions ask for the latest step the e-mail says has happened. When the parsers' keyword detector finds a kind, the model's kind stays only if the e-mail's wording gives it too and it takes precedence over the detected one; otherwise the detected kind is used. "On its way" alone doesn't decide between shipped and in transit. |
| In carriers' e-mails, the parcel number came back as an order number. | The instructions say a carrier's parcel number is a tracking number. A model order number that Parcels' detector reads as the sending carrier's tracking number, or that a tracking link carries, moves to the tracking numbers unless the e-mail labels it as an order. |
| Long order numbers were copied with a digit missing or changed. | An order number that isn't in the e-mail becomes the e-mail's number when exactly one number is one character away (two from 12 characters on) and the e-mail doesn't give it as a tracking number, code, date, phone or tax number. Otherwise it is dropped. |
| The carrier came back as the merchant when no shop was named, and the sender's domain came back instead of the shop's name. | The instructions say the merchant is never the delivery company or a web domain. The e-mail's carrier is dropped as merchant, unless it is also a shop (Amazon). A domain becomes the shop's name when the sender name or a line of the e-mail spells it. |
| A shop's own address came back as the pickup point. | Unless the parcel waits for pickup or missed its delivery, a pickup point must be written as one: a pickup, locker or collection word on its line or the line before. A kind of place ("eine Filiale", "a post office") isn't a pickup point. |

Scored again with these checks, that run's answers pass the bar (tracking
numbers right in 41 of 41 e-mails, dates 74 of 74, kinds 41 of 41). The
checks were written from that run's mistakes, though, so new runs tested
them on this set and on e-mails from outside it.

### What the held-out set showed

With these instructions and checks, a new run passed the bar on this set.
On a private held-out set of 22 made-up e-mails in 7 languages, kept outside
the repo, it fell short on tracking numbers, right in 21 of 22 e-mails (see
[Results](#results)). Its mistakes, too, were fixed as patterns:

| Observed | What Parcels does |
|---|---|
| Text hidden in the HTML told the model to change the kind, the carrier and the date, and the model did. The hidden words were part of the text, so the checks kept those values. | Parcels leaves out of the text everything a reader doesn't see: an element with `display:none`, the `hidden` attribute, `visibility:hidden` or `collapse`, `font-size:0`, or a zero height or `max-height` with hidden or clipped overflow, and everything inside it. A child that sets `visibility:visible` or a font size shows again, as in a browser. `mso-hide:all` hides nothing: only desktop Outlook honours it, and e-mails put visible buttons, often the tracking link, in it. The parsers read the same text. |
| A carrier's "shipment update" subject and a departure from a sorting centre were read as shipped, which replaced the model's right in transit. | A subject about an update gives no kind. Leaving a carrier's sorting centre, depot, terminal, hub, gateway or airport, or the country of origin, is in transit in the seven languages; only leaving the shop's or seller's own warehouse is shipped. |
| A tracking number written only in a tracking link came back with one character wrong and was dropped, leaving the parcel without one. | As with order numbers, a tracking number that isn't in the e-mail becomes the e-mail's number, from the text or a link, when exactly one number is one character away, passes the carrier's format and check digit, and isn't an order number, a code, a date or a phone or tax number. Otherwise it is dropped. |
| A hyphen-joined order number came back as two parts, and the second part was kept as an order number of its own. | An order number written only as a hyphen- or slash-separated part of a longer number becomes that number when exactly one number contains it, and is dropped otherwise. |

### What the later runs showed

Runs of `f117f4c` on this set and on two more private sets (see
[Results](#results)), and made-up probes, showed these patterns, fixed in
0.1.3:

| Observed | What Parcels does |
|---|---|
| An order number came back with two neighbouring digits swapped and was dropped. | Swapping two neighbouring characters counts as one character away, for order and tracking numbers. A tracking number must still pass the carrier's format and check digit. |
| A number written only in a link, with a carrier parameter the AI's link reader didn't know or inside a link wrapped by a click tracker, never reached the model or the checks, so a right answer was dropped. | The AI's link reader reads links as the parsers do, including the link a click tracker forwards to: carriers' own parameters on any site, generic ones such as `id` or `q` only on carrier sites. |
| The model cut a pickup code short, and the checks dropped it. | When no code is left, the parcel isn't delivered and the e-mail is about a parcel, the e-mail's pickup code or PIN is used if it gives exactly one that isn't a kept number. |
| An item came back as a tracking or order number or a code. | Such an item is dropped. |
| A warning that an uncollected parcel goes back to the sender was read as a return in German and Dutch. | A return-to-sender warning in a pickup or missed-delivery notice isn't a return; a parcel on its way back still is. |
| Delay wordings ("will arrive later than expected", "verzögert sich", "loopt een dag vertraging op") gave no kind. | They are delayed in the seven languages. |
| An arrival at the carrier's depot that announced delivery the next day came back as out for delivery. | Arriving at a carrier's depot, branch, hub, or sorting or distribution centre is in transit. Without an out-for-delivery wording, out for delivery becomes in transit when the delivery date is after the day the e-mail arrived. |
| A shop's e-mail named the carrier next to a number that fits many carriers, and the model gave no carrier. | When the e-mail names exactly one carrier, a kept number takes the carrier named next to it. A carrier named only in a returns footer or an ad isn't taken. |

### What changed in 0.1.5

0.1.5 keeps the instructions and the answer's structure. Every e-mail in
these sets gets the same input as with 0.1.4, byte for byte, and scoring the
saved answers again with 0.1.5 gives the same results on every set. The input
differs only for an e-mail with a link to Paack's tracking page: the link's
order ID is now listed with it, read from the `tracking_number` parameter
alone. What Parcels does with some answers changed:

| Answer | What Parcels does |
|---|---|
| `return` | `customer_return` isn't one of the model's kinds; an answer of it is read as `return`. The e-mail's own wording then sorts the answer, as it sorts the parsers' readings: an item the customer sends back becomes a return pickup linked to its order, and a parcel going back to its sender undelivered stays a return. |
| `return` or `not_parcel` for a refund e-mail | When the subject is about a refund or the e-mail says a refund was made, the answer is dropped and the e-mail is only counted in the diagnostics. When the text only opens with a refund, a `not_parcel` answer must be sure (confidence 0.7 or more) to be dropped; a doubtful one goes to review. |
| A Paack order ID, such as `Ab3Cd4Ef5_1` | In Paack's e-mails it's kept as the e-mail writes it, upper and lower case included, and moved from the order numbers to the tracking numbers, although Paack labels it as an order number. Its first nine characters are never a number of their own. 0.1.4 upper-cased it and dropped it as `tracking_invalid`, which sent the e-mail to review. |

Refund and return e-mails that the parsers recognise never reach the model.

### What changed in 0.1.7

0.1.7 keeps the instructions, the answer's structure and the input: every
e-mail gets the same input as with 0.1.6, byte for byte. The saved answers
weren't scored again. Instead, this set's expected answers and 574 made-up
variants of them (one per kind, one with the tracking and order numbers
swapped, one without a carrier) were checked with 0.1.6 and 0.1.7, with the
same results. None of this set's e-mails is from Paack or Leroy Merlin, the
senders the changes are about:

| Answer | What Parcels does |
|---|---|
| The first part of a Paack order ID, such as `Ab3Cd4Ef5` in `Ab3Cd4Ef5_1`, as an order or tracking number | Paack's e-mails call it the order number. In Paack's own e-mail, a value of that shape that the e-mail writes on its own, with a digit or a capital after its first character, is Paack's shipment reference, kept as the e-mail writes it. It's never the shop's order number, a tracking number or an item, and it counts as a checked identifier. Parcels then joins the e-mail to the parcel with that reference, as it does the parsers' readings. 0.1.6 kept it as an order number, at confidence 0.5, or dropped it as `tracking_is_order`. |
| No carrier, in an e-mail a shop sends in its carrier's name | For a shop that forwards its carrier's notices from its own domain, as Leroy Merlin Portugal does, a sender name that names exactly one carrier gives the carrier, as a carrier's own sender name does. 0.1.6 took the sender name for the shop's and gave no carrier. |
| An answer that fails a check | The item in **Needs review** keeps the codes of the checks it failed, without values (see [Check codes](#check-codes)). |

The parsers now read Paack's delivery notices and Leroy Merlin Portugal's
order and shipment e-mails, which went to the model with 0.1.6. As before,
an e-mail the parsers read with too little confidence still goes to the
model.

### What changed in 0.1.8

0.1.8 keeps the instructions, the answer's structure and the input: every
e-mail gets the same input as with 0.1.7, byte for byte. This set's expected
answers, the 574 variants and one more variant per e-mail, with the carrier
"Amazon", were checked with 0.1.7 and 0.1.8: all 656 gave the same results.
None of this set's e-mails names Amazon, the shop the change is about:

| Answer | What Parcels does |
|---|---|
| The carrier "Amazon", for an e-mail that names Amazon only as the shop | Amazon's name in its own e-mails names the shop, not its delivery service, so the carrier is left empty, with the note `carrier_unproven`. It isn't a failed check: the rest of the answer is used. Only "Amazon Logistics" or one of its numbers (`TBA` and 12 digits) names the carrier. A carrier's e-mail about an Amazon order keeps its own carrier. 0.1.7 took Amazon for the carrier, which kept these parcels apart from their carrier's deliveries. |
| No carrier, in an e-mail from an unknown sender named "Amazon" | The sender name names the shop, so it gives no carrier. "Amazon Logistics" still does. 0.1.7 gave Amazon as the carrier. |

### What changed in 0.1.9

0.1.9 keeps the instructions, the answer's structure, the input and the
checks: every e-mail gets the same input as with 0.1.8, byte for byte, and
the same 656 variants give the same results. Administrators now also see the
[notes](#notes) on an answer in **Needs review**.

### What changed in 0.1.11

0.1.11 keeps the instructions, the answer's structure, the input and the
checks: every e-mail gets the same input as with 0.1.10, byte for byte, and
the same 656 variants give the same results. In **Needs review**,
administrators now also see what each [failed check](#check-codes) means.

## Check codes

An answer that fails a check waits in **Needs review**, as "The local AI's
answer didn't pass the checks". Administrators see the codes of the failed
checks under **Checks the AI answer failed**, each with its meaning from
this table, never the values. "Plain text" below means no link, e-mail
address, HTML or control character.

| Code | The check that failed |
|---|---|
| `not_a_mapping` | The answer isn't a JSON object. Nothing in it is used. |
| `kind_invalid` | The kind is missing, or isn't a kind Parcels knows. Nothing in the answer is used. |
| `merchant_cut`, `carrier_cut`, `tracking_numbers_cut`, `order_numbers_cut`, `eta_start_cut`, `eta_end_cut`, `window_start_cut`, `window_end_cut`, `pickup_point_cut`, `pickup_code_cut` | A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "…". |
| `tracking_numbers_invalid`, `order_numbers_invalid`, `items_invalid` | The field is neither a list nor a text. |
| `tracking_numbers_too_many`, `order_numbers_too_many`, `items_too_many` | More than 20 tracking numbers, 10 order numbers or 10 items. The rest are dropped. |
| `tracking_invalid` | A tracking number isn't text, isn't 4 to 40 letters and digits (spaces, dashes and dots aside), or fails its carrier's format or check digit. |
| `tracking_not_in_email` | A tracking number isn't in the e-mail, nor a miscopy of exactly one number in it. |
| `tracking_is_order` | A tracking number equals an order number, or the e-mail labels it as an order number. |
| `tracking_is_pickup_code` | The e-mail writes a tracking number only as a delivery or pickup code. |
| `tracking_is_other_number` | The e-mail labels a tracking number as a phone, tax or bank number. |
| `order_invalid` | An order number isn't text, has more than 60 characters, or doesn't have 3 to 40 letters and digits, at least one of them a digit. |
| `order_not_in_email` | An order number isn't in the e-mail, nor a miscopy of exactly one number in it. |
| `order_is_part` | An order number is only part of longer, hyphen- or slash-joined numbers, and not exactly one of them can be an order number. |
| `order_is_tracking` | An order number equals a tracking number whose format identifies it. |
| `order_is_pickup_code` | The e-mail writes an order number only as a delivery or pickup code. |
| `pickup_code_invalid` | The pickup code isn't text, has more than 20 characters, or isn't 3 or more letters and digits, spaces and hyphens aside. |
| `pickup_code_not_in_email` | The pickup code isn't in the e-mail. |
| `pickup_code_is_number` | The pickup code equals a tracking or order number. |
| `pickup_point_invalid` | The pickup point isn't plain text, or has more than 120 characters. |
| `merchant_invalid` | The merchant isn't plain text, or has more than 60 characters. |
| `item_invalid` | An item isn't plain text. |
| `carrier_unknown` | The carrier isn't text, or isn't a carrier Parcels knows. |
| `carrier_not_in_email` | The carrier didn't send the e-mail, and the e-mail neither names it nor has a number whose format identifies it as that carrier's. |
| `eta_start_unparsed`, `eta_end_unparsed` | A date can't be read. |
| `eta_start_out_of_range`, `eta_end_out_of_range` | A date isn't between 2 days before and 60 days after the day the e-mail arrived. |
| `eta_end_before_start` | The last delivery day is before the first. |
| `eta_not_delivery_date` | The date overlaps no delivery date in the e-mail, and it had passed when the e-mail arrived or the e-mail gives it as another date: a deadline, or an order, shipping, offer or replaced date. |
| `eta_not_in_text` | The e-mail has no date, weekday or span at all. A delivery today, in an out-for-delivery e-mail, is allowed. |
| `eta_is_mail_day` | In an order or shipping e-mail, the date is the day the e-mail arrived, and no delivery phrase in its subject or text gives that day, nor a sentence saying the customer receives the parcel that day. |
| `window_start_unparsed`, `window_end_unparsed` | A time can't be read. |
| `window_end_before_start` | The time window doesn't end after it starts. |
| `window_without_date` | A time window comes without a date. |
| `not_parcel_has_tracking` | The answer says the e-mail isn't about a parcel, but gives a tracking number, or the e-mail has one whose format identifies it. |

The `tracking_is_*` checks skip numbers whose format identifies them, such
as `EA123456785PT`, and Paack's order IDs.

### Notes

Some checks change an answer they let through: they leave a value out, or
take it from the e-mail's own words. These notes aren't failed checks, and
the rest of the answer is used. On the local AI's answers in **Needs
review**, administrators see them under **Notes on the AI answer**, below
the failed checks, as codes without values, each with its meaning:

| Note | What Parcels changed |
|---|---|
| `tracking_added_by_detector` | Parcels' own detector added a tracking number that the e-mail writes. |
| `pickup_code_from_text` | The e-mail's only delivery or pickup code was used, as the answer gave none that the e-mail writes. |
| `item_recommended` | Products the e-mail lists only under Buy again or Recommended for you were dropped. |
| `item_is_number` | An item that was the parcel's tracking or order number, code or reference was dropped. |
| `kind_from_text` | The e-mail's words give a different status from the answer's, and theirs was used. |
| `out_for_delivery_not_today` | Out for delivery, with a later delivery date and no such words in the e-mail, was read as in transit. |
| `eta_dropped_for_kind` | A date was dropped, as no delivery is pending in e-mails of this kind. |
| `eta_from_text` | The date by the e-mail's delivery words was used, as the answer gave another date or none. |
| `order_moved_to_tracking` | An order number in a carrier's e-mail was the parcel's tracking number. |
| `order_from_text` | An order number was taken as the e-mail writes it: the whole joined number, or a miscopy repaired. |
| `tracking_from_text` | A miscopied tracking number was replaced by the e-mail's own. |
| `merchant_is_carrier` | The shop given was this e-mail's carrier, so it was dropped. |
| `carrier_unproven` | The shop, such as Amazon, was given as the carrier without proof that it delivers, so the carrier was left empty. |
| `merchant_from_sender_name` | A shop given as a domain was named from the sender's name. |
| `merchant_from_text` | A shop given as a domain was named from a line of the e-mail. |
| `pickup_point_not_pickup` | An address the e-mail doesn't give as a pickup point was dropped. |
| `pickup_point_generic` | A generic pickup point, such as a branch, was dropped. |

## Results

Fill in one row per run. Record the host's hardware (CPU, GPU, RAM), the
Home Assistant and Ollama versions, the date, and the Parcels version or
commit whose instructions and checks were used.

*This set* is the evaluation set above. *Held-out* is a private held-out set
of 22 made-up e-mails in 7 languages, kept outside the repo; it shows how
the checks hold on e-mails they weren't written from. *Second private set*
(13) and *third private set* (15): made-up e-mails in 7 languages, written
after `2ed6a52`, independently of the checks, and kept outside the repo. All
runs so far used `qwen3:4b-instruct` on the same Home Assistant host. The runs
of `f117f4c` and 0.1.3 went through `ai_task` on Home Assistant 2026.11.2, CPU
only (the Ollama version wasn't recorded), each only while Parcels' own AI
worker was idle.

| Date | Model | E-mails | Parcels version | Host | Tracking, e-mails right (model / after checks) | Dates right | Kinds right | Bar | Median s | p90 s | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-18 | qwen3:4b-instruct | this set (41) | 0.1.2 | CPU only | 32 / 38 of 41 | 53 of 74 (71.6%) | 31 of 41 (75.6%) | Fail | 37.7 | 43.5 | The first full run. Mean 37.9 s, max 48.3 s. |
| 2026-11-18 | qwen3:4b-instruct | this set (41) | `2ed6a52` | CPU only, Home Assistant 2026.11.2, Ollama 0.40.16 | 31 / 41 of 41 | 74 of 74 (100%) | 41 of 41 (100%) | Pass | 36.6 | 39.4 | Nothing else running on Ollama. Mean 35.2 s, max 40.9 s. |
| 2026-11-18 | qwen3:4b-instruct | held-out (22) | `2ed6a52` | as above | 17 / 21 of 22 | 38 of 40 (95.0%) | 20 of 22 (90.9%) | Fail (tracking) | 33.2 | 75.0 | Some calls waited behind Parcels' own AI calls on the host: mean 40.8 s, max 89.3 s. |
| 2026-11-18 | qwen3:4b-instruct | held-out (22) | 0.1.2 | as above | – / 19 of 22 | 26 of 40 (65.0%) | 17 of 22 (77.3%) | Fail | – | – | For comparison; only the scores after checks were recorded. |
| 2026-11-18 | qwen3:4b-instruct | this set (41) | `f117f4c` | CPU only, Home Assistant 2026.11.2 | 34 / 41 of 41 | 74 of 74 (100%) | 41 of 41 (100%) | Pass | 32.2 | 38.3 | Mean 32.3 s, max 39.9 s. One order number came back with two neighbouring digits swapped and was dropped; 0.1.3 repairs it. |
| 2026-11-18 | qwen3:4b-instruct | held-out (22) | `f117f4c` | as above | 17 / 22 of 22 | 40 of 40 (100%) | 21 of 22 (95.5%) | Pass | 35.8 | 40.1 | Mean 35.6 s, max 41.4 s. The kind miss is an "on its way" e-mail, which is left to the model. |
| 2026-11-18 | qwen3:4b-instruct | second private set (13) | `2ed6a52` | as above | 10 / 13 of 13 | 26 of 26 (100%) | 13 of 13 (100%) | Pass | 31.6 | 47.6 | Mean 33.0 s, max 54.1 s. |
| 2026-11-18 | qwen3:4b-instruct | second private set (13) | `f117f4c` | as above | 10 / 13 of 13 | 26 of 26 (100%) | 13 of 13 (100%) | Pass | 38.2 | 44.5 | Mean 38.7 s, max 62.8 s. Calls slowed as the hour-long run went on, with the same instructions: host load, not the code. |
| 2026-11-18 | qwen3:4b-instruct | third private set (15) | `2ed6a52` | as above | 12 / 13 of 15 | 30 of 30 (100%) | 12 of 15 (80.0%) | Fail | 33.6 | 37.9 | Mean 32.6 s, max 38.2 s. The model followed text hidden in one e-mail's HTML. |
| 2026-11-18 | qwen3:4b-instruct | third private set (15) | `f117f4c` | as above | 13 / 14 of 15 | 30 of 30 (100%) | 12 of 15 (80.0%) | Fail (tracking, kinds) | 37.9 | 42.1 | Mean 37.7 s, max 43.3 s. The hidden text no longer reached the model. |
| 2026-11-19 | qwen3:4b-instruct | this set (41) | 0.1.3 (`5037b40`) | as above | 34 / 40 of 41 | 74 of 74 (100%) | 40 of 41 (97.6%) | Fail (tracking) | 30.9 | 36.1 | Mean 30.7 s, max 36.7 s. The only miss: the model answered "not a parcel" for the PostNL customs e-mail (`nl04`). The checks keep that kind and record `not_parcel_has_tracking`, so the e-mail goes to review. The three earlier runs got it right. |
| 2026-11-19 | qwen3:4b-instruct | held-out (22) | 0.1.3 (`5037b40`) | as above | 18 / 22 of 22 | 40 of 40 (100%) | 21 of 22 (95.5%) | Pass | 34.0 | 36.8 | Mean 33.6 s, max 38.7 s. |
| 2026-11-19 | qwen3:4b-instruct | second private set (13) | 0.1.3 (`5037b40`) | as above | 9 / 13 of 13 | 26 of 26 (100%) | 12 of 13 (92.3%) | Pass | 36.0 | 41.7 | Mean 36.8 s, max 60.0 s. |
| 2026-11-19 | qwen3:4b-instruct | third private set (15) | 0.1.3 (`5037b40`) | as above | 13 / 15 of 15 | 29 of 30 (96.7%) | 14 of 15 (93.3%) | Pass | 36.3 | 40.1 | Mean 36.3 s, max 41.7 s. The first pass on this set. |

Per field, after checks (model in parentheses):

| Field | 0.1.2, this set | `2ed6a52`, this set | `2ed6a52`, held-out |
|---|---|---|---|
| kind | 75.6% (75.6%) | 100% (80.5%) | 90.9% (81.8%) |
| merchant | 94.4% (94.4%) | 100% (97.2%) | 100% (100%) |
| carrier | 100% (90.2%) | 100% (95.1%) | 95.5% (95.5%) |
| tracking_numbers | 92.7% (78.0%) | 100% (75.6%) | 95.5% (77.3%) |
| order_numbers | 87.8% (87.8%) | 100% (78.0%) | 95.5% (81.8%) |
| eta_start | 70.3% (67.6%) | 100% (73.0%) | 95.0% (65.0%) |
| eta_end | 73.0% (70.3%) | 100% (73.0%) | 95.0% (75.0%) |
| window_start | 100% (97.3%) | 100% (97.3%) | 100% (100%) |
| window_end | 100% (97.3%) | 100% (97.3%) | 100% (100%) |
| pickup_point | 97.6% (97.6%) | 100% (97.6%) | 100% (100%) |
| pickup_code | 100% (100%) | 100% (100%) | 100% (100%) |
| items (recall) | 100% (100%) | 100% (100%) | 100% (100%) |

Per field for `f117f4c` and the private sets, after checks (model in parentheses):

| Field | `f117f4c`, this set | `f117f4c`, held-out | `2ed6a52`, second set | `f117f4c`, second set | `2ed6a52`, third set | `f117f4c`, third set |
|---|---|---|---|---|---|---|
| kind | 100% (80.5%) | 95.5% (77.3%) | 100% (76.9%) | 100% (76.9%) | 80.0% (73.3%) | 80.0% (80.0%) |
| merchant | 100% (97.2%) | 100% (100%) | 100% (100%) | 100% (100%) | 92.9% (92.9%) | 92.9% (92.9%) |
| carrier | 100% (95.1%) | 100% (100%) | 100% (100%) | 100% (100%) | 85.7% (92.9%) | 100% (100%) |
| tracking_numbers | 100% (82.9%) | 100% (77.3%) | 100% (76.9%) | 100% (76.9%) | 86.7% (80.0%) | 93.3% (86.7%) |
| order_numbers | 97.6% (85.4%) | 100% (81.8%) | 100% (76.9%) | 100% (69.2%) | 100% (66.7%) | 100% (73.3%) |
| eta_start | 100% (67.6%) | 100% (65.0%) | 100% (69.2%) | 100% (76.9%) | 100% (60.0%) | 100% (60.0%) |
| eta_end | 100% (70.3%) | 100% (70.0%) | 100% (76.9%) | 100% (76.9%) | 100% (66.7%) | 100% (60.0%) |
| window_start | 100% (97.3%) | 100% (100%) | 100% (84.6%) | 100% (84.6%) | 100% (93.3%) | 100% (100%) |
| window_end | 100% (97.3%) | 100% (100%) | 100% (84.6%) | 100% (84.6%) | 100% (93.3%) | 100% (100%) |
| pickup_point | 100% (100%) | 100% (100%) | 100% (100%) | 100% (100%) | 100% (86.7%) | 100% (86.7%) |
| pickup_code | 100% (100%) | 100% (100%) | 92.3% (92.3%) | 100% (100%) | 100% (100%) | 100% (100%) |
| items (recall) | 100% (100%) | 100% (100%) | 100% (100%) | 100% (100%) | 100% (100%) | 100% (100%) |

A private set stops being held out once its misses feed a fix. The held-out
set's misses fed `f117f4c`. The second set's misses fed 0.1.3's pickup-code
fallback and item-noise check. The third set's e-mails were never given to the
checks' author; its misses feed 0.1.3's link reader, return-warning, delay and
depot-arrival fixes. So no set here measures 0.1.3 untouched; live use is the
next honest measure.

### Known limits

- An "on its way" e-mail is left to the model, which may answer shipped or in
  transit.
- A shop named only mid-sentence after a "sent by" phrase (pt
  `enviado por <shop>`) isn't read as the merchant.
- The carrier detector doesn't know Colis Privé, so only the model can name it.
- A date that the model gives itself is kept when the e-mail writes it, even
  in an advert's promise to whoever orders now ("order today and get it
  tomorrow"), unless it's the day an order or shipping e-mail arrived. Only
  Parcels' own reading of the delivery words skips adverts.
