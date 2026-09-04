# Architecture

The rules the code actually follows. For setup, limitations and the schema
rationale, see the [README](README.md).

## Flow

```
input_requests.csv
        ↓
   csv_repository        →  InboxRequest        (validate every row)
        ↓
   TriageService         →  one request at a time
        ↓
   GeminiTriageClient    →  prompts + Gemini + retry
        ↓
   TriageResult          →  validate the model's answer
        ↓
   TriagedRequest        →  input + output + metadata
        ↓
   dedup_service         →  possible_duplicate_of   (code, not the model)
        ↓
   report_service        →  aggregates as Markdown
        ↓
   output_repository     →  output.json + report.md
```

One process, one direction. No database, no HTTP, no queue: a batch job that
reads files, calls one external API and writes files.

`main.py` is the only place where these pieces are wired together. Every module
below it can be imported and tested on its own.

## Layers and their rules

### `app/repositories/` — file I/O
- The only code that touches the filesystem.
- `load_requests` validates each CSV row and **skips** malformed ones with a
  warning. A bad row never aborts the run; the warning carries the file line
  number so it can be found by eye.
- `write_json` / `write_text` create the output directory if it is missing.
- No business rules. No decisions about what the data means.

### `app/schemas/` — contracts
- `input/` is what we accept from outside, `output/` is what we produce.
- `InboxRequest` is deliberately permissive: `channel` is `str`, not an enum, so
  a new channel in the CSV does not break the run.
- `TriageResult` is deliberately strict: it is the contract the LLM must satisfy.
  Enums for `category` and `priority`, a range on `confidence`, a length cap on
  `short_summary`.
- Field validators normalise the model's non-answers (`"не зрозуміло"`, `"null"`,
  `"-"`) into real `None`, and strip duplicates and blanks from
  `requested_actions`.
- Schemas contain no I/O and no service imports. Nothing above them is imported
  from here.

### `app/prompts/` — text, and only text
- Two constants and one formatting function. The module imports `InboxRequest`
  and nothing else — it has no way to reach the network.
- `build_user_prompt` returns a `str`. It sends nothing.
- The user's raw text is fenced in triple quotes so the model can see where the
  instruction ends and untrusted input begins.
- This is the file to edit when the model classifies badly. It is never the file
  to edit when the API misbehaves.

### `app/services/` — the work
- `TriageService` orchestrates: iterate, log progress, collect results. It takes
  its client through the constructor, so tests pass a fake and never touch the
  network.
- `GeminiTriageClient` owns everything about the provider: the SDK, the model
  name, retries, backoff, status codes. It is the only module that imports
  `google.genai`.
- `dedup_service` and `report_service` are pure functions over records. No I/O.

### `app/core/` — the shared floor
- `config.py` — one `Settings` instance, built once at import. Every path and
  every knob lives here; nothing else reads the environment.
- `logging.py` — one `basicConfig`, called once from `main.py`. Library modules
  take `logging.getLogger(__name__)` and never configure logging themselves, so
  the layer is visible in every line of output.
- `exceptions.py` — `TriageError` as the base, `LLMResponseError` carrying the
  attempt count so the failure ends up in the output file rather than in a
  traceback.

## Failures are split into three kinds

`GeminiTriageClient.classify` treats them differently on purpose:

| Kind | Trigger | Response |
| --- | --- | --- |
| Fatal | `400 / 401 / 403 / 404` | raise immediately — the key or the model name is wrong and a retry cannot fix it |
| Transient | `429`, `5xx`, empty response | wait and retry, delay doubling each attempt |
| Content | the JSON does not satisfy `TriageResult` | retry with the model shown its own answer plus the Pydantic errors |

The content case is the interesting one. The retry is not "try again" — the next
request contains the original prompt, the rejected output, and a list of exactly
what was wrong with it:

```python
contents = [
    build_user_prompt(request),
    raw,
    REPAIR_TEMPLATE.format(errors=last_error),
]
```

When every attempt is spent, `classify` raises `LLMResponseError`.
`TriageService._process` catches it and returns a record with `triage=None`, an
`error` string and the attempt count. **The run continues.** One failed request
costs one record, not the batch.

This was verified against a real provider outage, not only in tests: during one
run Gemini answered `503` for most of the batch. Every affected request was
retried three times, the failures were recorded, the successes were kept, both
output files were written, and the process exited `0`.

## Two levels of validation, not one

`response_schema=TriageResult` is passed to the Gemini SDK, which constrains
generation at the decoder level — the model is not free to emit a seventh
category. Pydantic then validates the answer again on our side.

The second level is not redundant. Structured output constrains *shape*; it does
not stop the model writing the string `"не зрозуміло"` into a field that should
be `null`, and it does not stop it wrapping the JSON in a markdown fence. Both
are handled after the fact — `strip_markdown_fence` and the field validators.

## Duplicates are found by code, not by the model

`possible_duplicate_of` lives on `TriagedRequest`, not on `TriageResult`, and is
set by `dedup_service` after the whole batch is classified.

The reason is a hard constraint, not a preference: the model sees one request per
call. It cannot know that `REQ-001` exists, so asking it for a duplicate id would
produce an invented one. Anything requiring a view of the whole batch belongs to
code.

The comparison is `difflib.SequenceMatcher` over `raw_text`, threshold `0.35`,
first match wins so a chain of restatements resolves to the original. It is
character-level: it catches restatements, not two requests that describe the same
need in different words. The README says so, and names the LLM-judge upgrade that
would close the gap.

## Testing

30 tests, none of which call the API.

| Suite | What it pins down |
| --- | --- |
| `test_triage_result` | enums reject unknown values, ranges hold, non-answers become `None`, actions deduplicate |
| `test_csv_repository` | valid rows parse, malformed rows are skipped by line number, the run survives them |
| `test_triage_service` | a failing request becomes an error record and the other requests still finish |
| `test_dedup_service` | restatements are linked, unrelated requests are not, failed records are ignored |
| `test_report_service` | every aggregate the spec asks for, plus the fixed high/medium/low ordering |

`tests/conftest.py` puts a placeholder in `GEMINI_API_KEY` before the app is
imported, because `Settings` requires it at import time. Without that file a
fresh clone cannot even collect the tests — which is what a reviewer does first.

## Logging

`setup_logging()` is called once, in `main.py`. Output goes to stdout, so `docker
logs` and CI pick it up as ordinary output rather than as errors.

Always logged:
- every skipped CSV row, with its line number;
- `[n/total] REQ-xxx` before each request, so a slow run shows progress;
- every retry: which request, which attempt, and why;
- every request that exhausted its retries;
- the batch total and the failure count;
- the path of each file written.

Never logged: `GEMINI_API_KEY`, or any part of it.
