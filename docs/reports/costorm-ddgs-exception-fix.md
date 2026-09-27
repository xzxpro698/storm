# Co-STORM DDGS exception compatibility fix

## Objective

Expose the real DDGS/DuckDuckGo failure that was masked by an incompatible DSPy
exception handler, and prevent the Gemini runner from dereferencing a missing
conversation turn after a failed Co-STORM pipeline stage.

## Files changed

- Modified: `knowledge_storm/rm.py`
- Modified: `examples/costorm_examples/run_costorm_gemini.py`
- Created: `docs/reports/costorm-ddgs-exception-fix.md`

No DuckDuckGo backend, retry configuration, provider fallback, sleep, API key, or
`secrets.toml` setting was changed. No commit was created.

## Confirmed cause

The installed DSPy handler imported by `knowledge_storm.rm` is:

```python
def giveup_hdlr(details):
    if "rate limits" in details.message:
        return False
    return True
```

The `backoff` decorator passes the exception object to this handler. The installed
`ddgs.exceptions.DDGSException` has no `.message` attribute; its underlying message
is available from `str(exc)`. This caused the observed masking error:

```text
'DDGSException' object has no attribute 'message'
```

An initial compatibility attempt treated the callback argument as a mapping; the
subsequent smoke test proved it is an exception object by raising
`'DDGSException' object has no attribute 'get'`. The final implementation uses the
actual callback contract.

## Implementation

`knowledge_storm.rm` now defines the DuckDuckGo-specific handler:

```python
def _ddgs_giveup_hdlr(exc):
    return "rate limits" not in str(exc).lower()
```

`DuckDuckGoSearchRM.request()` retains its existing `backoff.on_exception`
configuration and uses this handler in place of DSPy's incompatible handler. Thus
the original intended behavior is retained: exception strings containing
`"rate limits"` remain retryable; other exceptions are surfaced. No retry/backoff
settings were added or changed.

The Gemini runner now raises a clear `RuntimeError` if either observed
`costorm_runner.step()` call returns `None`. This prevents `conv_turn.role` from
raising a secondary `AttributeError` and directs the user to the preceding pipeline
error.

## Validation

### Compile and import checks

```bash
python3 -m py_compile knowledge_storm/rm.py \
  examples/costorm_examples/run_costorm_gemini.py

uv run python - <<'PY'
from ddgs.exceptions import DDGSException
from knowledge_storm.rm import _ddgs_giveup_hdlr

exc = DDGSException("underlying DDGS error")
assert _ddgs_giveup_hdlr(exc) is True
assert _ddgs_giveup_hdlr(DDGSException("rate limits exceeded")) is False
PY
```

Result: passed. The `knowledge_storm.rm` import succeeded, the handler accepts a
real `DDGSException`, and `str(exc)` preserved its message.

`git diff --check` also passed.

### Direct DuckDuckGo test

```bash
uv run python - <<'PY'
from knowledge_storm.rm import DuckDuckGoSearchRM

rm = DuckDuckGoSearchRM(k=1)
print(rm.forward("What is retrieval-augmented generation?"))
PY
```

An earlier direct request succeeded with `DIRECT_DDG_SUCCESS count=1` and an HTTP
200 response. The final direct validation received DuckDuckGo HTTP 202 and exposed
the real exception without an attribute error:

```text
ddgs.exceptions.DDGSException: No results found.
```

The existing decorator logged `Giving up request(...) after 1 tries`; this follows
the unchanged give-up policy for a non-rate-limit exception. No retry behavior was
introduced.

### Gemini + OpenAI encoder + DuckDuckGo Co-STORM smoke test

The smoke test was run with the existing non-secret configuration selecting
`ENCODER_API_TYPE=openai`, with Gemini generation and DuckDuckGo retrieval. It
reached Gemini, OpenAI embeddings, DuckDuckGo HTTP 200/202 responses, warm start,
the moderator's first utterance, and the supplied user utterance.

The first run after the preliminary handler attempt stopped with the handler's own
`.get` compatibility error. The final direct test then exposed the actual DDGS
failure above. Per the requested stop condition, a further full Co-STORM run was not
performed after that real DDGS error; no retriever workaround was implemented.

## Unresolved blocker

The current underlying external retrieval failure is:

```text
DDGSException: No results found.
```

It followed a DuckDuckGo HTTP 202 response. This is no longer masked by the DSPy
`.message` bug. Diagnosing or changing DDGS/DuckDuckGo behavior is outside this
task's requested fix.

## Diff summary

At report time, `git diff --stat` showed the tracked changes below. New untracked
files are not included by `git diff --stat`.

```text
 knowledge_storm/encoder.py | 11 ++++++++++-
 knowledge_storm/rm.py      |  8 ++++++--
 2 files changed, 16 insertions(+), 3 deletions(-)
```

The meaningful change for this task is the DDGS-specific `str(exc)` handler and two
runner `None` guards. The encoder diff predates this task.
