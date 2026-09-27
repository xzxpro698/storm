# Co-STORM local CPU encoder implementation

## Objective

Enable Co-STORM to use a local SentenceTransformer encoder so that Gemini handles
generation, DuckDuckGo handles web retrieval, and no OpenAI/Azure embedding API is
required.

## Files

- Created: `docs/reports/costorm-local-encoder-implementation.md`
- Modified: `knowledge_storm/encoder.py`
- Not modified: `examples/costorm_examples/run_costorm_gpt.py`, the Gemini runner,
  DuckDuckGo retrieval, Standard STORM embedding code, and `secrets.toml`.

## Implementation design

`Encoder` now recognizes `ENCODER_API_TYPE=local`. That branch lazily imports
`SentenceTransformer`, constructs `SentenceTransformer("paraphrase-MiniLM-L6-v2",
device="cpu")`, and stores it in `self.local_model`. No API key, endpoint, or
embedding service is used by this branch.

`Encoder.encode()` detects the local model and returns
`np.asarray(self.local_model.encode(texts))`. Passing a list directly to
SentenceTransformer preserves native batching. `max_workers` is intentionally not
used by this backend. The existing OpenAI and Azure branches and their LiteLLM
request/accounting path are unchanged.

The local backend leaves `total_token_usage` at zero. Repository search found no
consumer of `Encoder.get_total_token_usage()`, and zero accurately represents that
there was no embedding API usage.

## Encoder interface behavior

Verified local behavior, using `ENCODER_API_TYPE=local`:

| Input | Result |
|---|---|
| `"hello world"` | `numpy.ndarray`, `float32`, shape `(384,)`, all finite |
| `["hello world", "retrieval augmented generation"]` | `numpy.ndarray`, `float32`, shape `(2, 384)`, all finite |

The interface remains synchronous. A single string returns a 1-D vector; a list
returns a 2-D matrix. `get_total_token_usage()` returned `0`.

## Local model and device

Model: `paraphrase-MiniLM-L6-v2`.

Device: explicitly `cpu`; the instantiated model reported `device=cpu`. No CUDA or
GPU detection/configuration was added.

The model was not already cached. SentenceTransformer successfully downloaded its
normal first-use model artifacts, instantiated the model, and completed both
embedding calls.

## Validation commands

```bash
python3 -m py_compile knowledge_storm/encoder.py

env -u OPENAI_API_KEY -u AZURE_API_KEY ENCODER_API_TYPE=local \
  uv run python - <<'PY'
import numpy as np
from knowledge_storm.encoder import Encoder

encoder = Encoder()
single = encoder.encode("hello world")
multiple = encoder.encode(["hello world", "retrieval augmented generation"])
assert isinstance(single, np.ndarray)
assert isinstance(multiple, np.ndarray)
assert single.ndim == 1
assert multiple.ndim == 2 and multiple.shape[0] == 2
assert multiple.shape[1] == single.shape[0]
assert np.isfinite(single).all() and np.isfinite(multiple).all()
assert encoder.get_total_token_usage() == 0
PY

ENCODER_API_TYPE=local python examples/costorm_examples/run_costorm_gemini.py \
  --retriever duckduckgo \
  --output-dir ./results/co-storm-gemini-smoke \
  --retrieve_top_k 3 \
  --max_search_queries 1 \
  --total_conv_turn 4 \
  --max_search_thread 1 \
  --max_search_queries_per_turn 1 \
  --warmstart_max_num_experts 2 \
  --warmstart_max_turn_per_experts 1 \
  --warmstart_max_thread 1 \
  --max_thread_num 1 \
  --max_num_round_table_experts 2 \
  --enable_log_print
```

Additional static checks verified that `encoder.py` compiles, the `openai`, `azure`,
and `local` branches are present, no API key literal is embedded, and the GPT
reference runner is unchanged. `git diff --check` passed.

## Co-STORM compatibility

Verified by source inspection and actual output shapes:

- `KnowledgeBase` embeds a list of knowledge-base paths and compares it with a
  single embedded question/query using `sklearn.metrics.pairwise.cosine_similarity`.
  `(N, 384)` and `(384,)` are compatible with that use.
- `Moderator` compares batches of snippets with embedded claim/query/cited-snippet
  values. Its expected 2-D batch and 1-D single-string output shapes are preserved.
- Node expansion reuses the same knowledge-base insertion module, so it receives the
  same compatible interface.

No Co-STORM call-site change was required.

## End-to-end smoke test

The requested smoke test was attempted with the requested topic and user utterance.
It passed encoder construction and local model loading. The execution reached both
configured external paths: Gemini completions completed, and DuckDuckGo returned an
HTTP response (`200` in the first attempt; `202` in the controlled retry).

It did not complete and produced none of `report.md`, `instance_dump.json`, or
`log.json`. The first meaningful failure from the controlled retry was:

```text
Error occurred during pipeline stage 'warm start stage':
'DDGSException' object has no attribute 'message'
```

After warm start failed, the runner then raised `IndexError: list index out of range`
when it attempted `self.conversation_history[-1]`. This is an existing DuckDuckGo/
DDGS error-handling path, outside the scope of this encoder-only change. It was not
modified. Therefore a successful end-to-end report must not be claimed.

## Unresolved issues

- The DuckDuckGo/DDGS failure above blocks completion of the external smoke test.
- Gemini/LiteLLM emitted Pydantic serializer warnings during the test, but Gemini
  completions completed; those warnings were not the terminating error.

## Diff summary

`git diff --stat` after the implementation reported:

```text
 knowledge_storm/encoder.py | 11 ++++++++++-
 1 file changed, 10 insertions(+), 1 deletion(-)
```

`git diff --stat` does not list untracked files. The meaningful tracked diff adds a
`local` branch, CPU SentenceTransformer initialization, and local dispatch in
`Encoder.encode()`; it also corrects the supported-type error message to include
`local` rather than the unimplemented `together` value.
