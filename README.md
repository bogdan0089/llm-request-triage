# LLM Request Triage

Batch service that reads internal team requests from a CSV file, classifies each one via Google Gemini, and produces a structured JSON result and a Markdown report.

## How to run

### Prerequisites

- Python 3.11+
- A Google Gemini API key (free tier is enough)

### Setup

```bash
git clone https://github.com/bogdan0089/llm-request-triage.git
cd llm-request-triage

python -m venv .venv
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
```

### Environment variables

Copy the template and fill in your key (`.env` is gitignored and must stay that way):

```bash
cp .env.example .env           # Linux / macOS
# Copy-Item .env.example .env  # Windows
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | yes | — | Google Gemini API key |
| `GEMINI_MODEL` | no | `gemini-3.5-flash-lite` | Model used for classification |
| `TEMPERATURE` | no | `0.1` | Sampling temperature |
| `MAX_RETRIES` | no | `2` | Retry attempts on invalid output |
| `RETRY_BACKOFF_SECONDS` | no | `5.0` | Base delay for exponential backoff |

`GEMINI_API_KEY` has no default on purpose: the application fails on startup rather than
halfway through a run if the key is missing.

### Run

```bash
python -m app.main
```

Writes `output/output.json` and `output/report.md`.

### Run in Docker

```bash
docker build -t llm-request-triage .

# Linux / macOS
docker run --rm --env-file .env -v "$(pwd)/output:/app/output" llm-request-triage

# Windows PowerShell
docker run --rm --env-file .env -v "${PWD}/output:/app/output" llm-request-triage
```

The key is passed at runtime and never baked into the image (`.dockerignore` excludes `.env`).
The `output/` volume mount is required — without it the results stay inside the container and
are lost when it exits.

### Tests

```bash
pytest tests/ -v
```

---

## Schema

### Required fields (per spec)

| Field | Type | Notes |
|---|---|---|
| `category` | enum | One of the six categories defined in the spec |
| `target_department` | `str \| null` | `null` when the department is not stated |
| `priority` | enum | `low` / `medium` / `high` |
| `short_summary` | `str` | One sentence, max 250 characters |
| `requested_actions` | `list[str]` | Deduplicated, may be empty |
| `needs_clarification` | `bool` | Whether the request is too vague to action |

### Added fields — and why

The spec allows extending the schema. Five fields were added, each solving a concrete
problem that surfaced while looking at the real data:

**`is_actionable: bool`** — some rows are not requests at all (a thank-you note, a stray
comment). Without this flag they land in `поза скоупом` next to genuine out-of-scope work
requests, and the two are not the same thing operationally: one needs routing elsewhere,
the other needs nothing. This separates "not our job" from "not a job".

**`confidence: float`** — the model classifies ambiguous text with the same outward certainty
as obvious text. Asking it to score its own confidence gives a cheap triage signal: anything
below ~0.6 is worth a human glance before it enters a queue. It also makes prompt regressions
visible — if average confidence drops after a prompt change, the change hurt.

**`deadline_mentioned: str | null`** — `priority` is the model's judgement, which is not
auditable. This field is the literal quote from the text ("сьогодні до вечора"). Keeping the
raw evidence separate from the derived verdict means a human can check whether a `high`
priority is justified, instead of trusting it blindly.

**`clarification_question: str | null`** — `needs_clarification: true` alone is a dead end:
someone still has to read the request and work out what is missing. Generating the actual
question turns the flag into something immediately sendable back to the requester.

**`possible_duplicate_of: str | null`** — the input contains near-duplicate requests
(REQ-013 restates REQ-001). This field lives on `TriagedRequest`, not `TriageResult`, and is
set by code rather than the LLM: the model sees one request at a time and cannot know that
another one exists, so asking it for duplicate IDs would produce invented answers.

---

## Where it breaks / limitations

### Invalid LLM output
The model occasionally returns text that does not match the expected schema (wrong category
name, missing field, `"не зрозуміло"` instead of `null`).

**How it is handled:**
- `response_schema` constrains generation at the decoder level, so malformed output is rare
  to begin with.
- Pydantic validates every response strictly on top of that.
- On a validation error the model receives its own bad response plus the list of Pydantic
  errors and is asked to fix them (self-correction loop, up to `MAX_RETRIES` attempts).
- Validators normalize common non-values (`"null"`, `"none"`, `"-"`, `"невідомо"`) to real `None`.
- If every attempt fails, the request is saved with `triage: null` and an `error` field.
  The run continues — one bad request does not cost the other seventeen.

API failures are split into three classes: fatal (`400/401/403/404` — configuration is wrong,
retrying cannot help, fail immediately), transient (`429/5xx` — retry with exponential
backoff), and content errors (schema mismatch or an empty response — retry, with the model
shown its own bad output where there is one).

This was exercised for real, not just in tests: during one run Gemini returned `503 Service
Unavailable` for most of the batch. Each affected request was retried three times with
growing delays, the failures were recorded with `error` and `attempts`, the four requests that
did succeed kept their results, both output files were written, and the process exited `0`.
No input was lost — `raw_text` survives on every failed record, so a rerun is possible.

### Scale
Processing is sequential. 18 requests take roughly 2.5 minutes on `gemini-3.5-flash-lite`.
That is linear: 1000 requests would take over two hours, which is not acceptable.

The fix is `asyncio.gather` with a `Semaphore` capping concurrency at 5–10. It was left out
because the free tier rate-limits aggressively and a concurrent run would spend most of its
time in backoff — it would be slower in practice, not faster, at this volume.

### Non-determinism
`temperature=0.1` keeps output mostly stable, but repeated runs on identical input can still
differ, most visibly on `priority` for borderline requests and on `short_summary` wording.
Low temperature narrows the sampling distribution; it does not collapse it to a single point.

Observed on this dataset: REQ-002 and REQ-011 are near-identical in vagueness yet received
`medium` and `low`. This is not a bug that a prompt fix would close — tightening the prompt
around 18 known rows is overfitting to the sample, and the next 18 rows would break differently.
Caching responses by input hash would make reruns reproducible, which is the honest fix.

### Token cost
Ukrainian text costs roughly 2–3× more tokens than equivalent English, because tokenizers are
trained predominantly on English corpora — Ukrainian words fragment into more subword pieces.
One request runs ~300–600 input tokens and ~150 output tokens.

The system instruction is the largest fixed cost: it is resent with every request (~700 tokens
× 18 = ~12,600 tokens spent on the same text). At this volume it is irrelevant. At scale,
context caching would cut it to a single charge.

`response_schema` also lowers output cost — the model emits fields directly rather than
prose scaffolding around them.

---

## What I would do next

- **Async batch processing** — `asyncio.gather` + `Semaphore`, once a paid tier removes the
  rate-limit ceiling that currently makes concurrency pointless.
- **LLM judge for duplicates** — the current difflib filter is character-level and catches
  only textual overlap. Two requests that describe the same need in different words would slip
  through. Using difflib as a cheap pre-filter and an LLM call to judge the surviving pairs
  would catch semantic duplicates at a fraction of the cost of comparing all pairs.
- **Resume failed requests only** — a run that hits a provider outage currently has to be
  repeated in full, re-paying for the requests that already succeeded. Reading the previous
  `output.json` and reprocessing only records where `triage` is `null` would make recovery
  cheap. The outage described above is what makes this the first thing worth adding.
- **Response caching** — hash the input text, skip the API call on a hit. Makes reruns free
  and deterministic, which matters for testing prompt changes.
- **Persistent storage** — swap flat JSON for SQLite so results can be queried and updated
  incrementally instead of re-running the whole pipeline.
- **CI** — GitHub Actions running `pytest` on every push.
