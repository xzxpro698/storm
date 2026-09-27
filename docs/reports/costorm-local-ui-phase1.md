# Co-STORM local UI: Phase 1

## Objective

Add a thin Streamlit frontend for running a live Co-STORM session and observing the
runner-owned knowledge-base tree after warm start and each subsequent turn.

## Files added and changed

- Added: `frontend/costorm_local/app.py`
- Added: `frontend/costorm_local/requirements.txt`
- Added: `frontend/costorm_local/README.md`
- Added: `docs/reports/costorm-local-ui-phase1.md`
- Changed: no Co-STORM engine, data model, or existing frontend file.

The existing `frontend/demo_light/` directory and
`examples/costorm_examples/run_costorm_gemini.py` were verified unchanged during
this work.

## Architecture

`frontend/costorm_local/app.py` is a single Streamlit adapter. It loads the existing
root `secrets.toml` through `load_api_key()`, constructs the same six Gemini
`LitellmModel` roles and `SerperRM` used by the Gemini CLI runner, then creates a
`CoStormRunner`.

The live runner is stored as `st.session_state.costorm_runner`. The app does not
introduce a persistence layer, a graph representation, a callback adapter, or a
parallel orchestration path.

## Reused Co-STORM APIs

- `CoStormRunner` for lifecycle and all turns.
- `CoStormRunner.warm_start()` for initial research.
- `CoStormRunner.step(user_utterance=...)` for a human turn.
- `CoStormRunner.step()` for the next generated turn.
- `ConversationTurn` objects from `runner.conversation_history` for the conversation
  panel.
- `KnowledgeBase.get_node_hierarchy_string()` for the live tree panel.
- `KnowledgeBase.reorganize()` and `CoStormRunner.generate_report()` for final report
  generation.

The tree view is therefore always derived from the live runner state rather than a
separate reconstructed tree.

## UI behavior

1. Enter a topic and select **Start Research**. The app creates a runner, runs warm
   start, and retains it in Streamlit session state.
2. The left panel renders conversation history, including speaker role and turn type.
3. The right panel renders the current knowledge hierarchy as readable Markdown-like
   text from `get_node_hierarchy_string()`.
4. **Submit Human Utterance** invokes the existing runner API. **Generate Next
   Co-STORM Turn** invokes the existing system-turn API.
5. The app reruns after each action, so both panels render current runner state.
6. **Generate Final Report** reorganizes the current knowledge base, generates the
   report through the runner, and displays it in the page.
7. **Reset / New Session** removes the live runner, report, and UI error state.

## Launch

From the repository root:

```bash
pip install -r frontend/costorm_local/requirements.txt
streamlit run frontend/costorm_local/app.py
```

The required configured stack is Gemini for language-model roles, OpenAI for the
existing encoder, and Serper for retrieval. The app loads these existing settings
from root-level `secrets.toml`; no secret is included in this frontend or report.

## Validation performed

### Static and integrity checks

```bash
python3 -m py_compile frontend/costorm_local/app.py
git diff --check
git diff --quiet -- frontend/demo_light
git diff --quiet -- examples/costorm_examples/run_costorm_gemini.py
```

Result: passed. The UI static contract check also confirmed calls to `warm_start`,
both `step` forms, `get_node_hierarchy_string`, `generate_report`, `SerperRM`, and
the requested Gemini model identifier.

### Streamlit startup

Streamlit was not installed in the project environment, so validation used the
frontend's pinned `streamlit==1.31.1` in an isolated `uv run --with` environment;
repository dependencies were not changed. The app imported successfully and started
headlessly. Streamlit reported its network URL before the controlled 12-second
startup timeout ended the server.

### Live Co-STORM workflow

The app module's `build_runner()` factory was used with the configured Gemini,
OpenAI-encoder, and Serper stack to run this sequence:

1. `warm_start()`;
2. assert and read `conversation_history`;
3. render-equivalent tree reads using `get_node_hierarchy_string()`;
4. submit `Please continue and focus on how retrieval improves factual grounding.`;
5. generate the next Co-STORM turn;
6. reorganize and generate a final report.

The workflow completed without an assertion or process failure. Provider output was
verbose enough to truncate the captured terminal output before its final counters,
but the execution completed after the report-generation assertion. This validates
the UI's real runner factory and each Phase 1 interaction path. Gemini/LiteLLM
emitted existing Pydantic serializer warnings during the run; they did not terminate
the workflow.

The existing CLI runner's `--help` command also passed after the UI addition.

## Known limitations

- Co-STORM calls run synchronously inside Streamlit button handlers, so long warm
  starts and turns block the page while the spinner is displayed.
- The runner is retained only in one process's Streamlit session memory; reset or
  server restart loses it.
- The tree panel is intentionally text-only and has no node/citation inspection.
- The app uses existing Co-STORM defaults, which can make warm start expensive.
- Detailed engine logs remain in the server console rather than the UI.

## Recommended Phase 2 improvements

- Add a callback handler that renders Co-STORM progress and errors in the UI.
- Add per-node citation and source inspection using existing `KnowledgeBase` state.
- Add safe save/resume controls based on `CoStormRunner.to_dict()` and `from_dict()`.
- Add explicit configurable runner limits for interactive cost and latency control.
- Add download controls for report and instance/log artifacts.

## Diff summary

At validation time, `git diff --stat` showed only pre-existing tracked encoder and
DDGS changes because the new UI files were untracked:

```text
 knowledge_storm/encoder.py | 11 ++++++++++-
 knowledge_storm/rm.py      |  8 ++++++--
 2 files changed, 16 insertions(+), 3 deletions(-)
```

The Phase 1 UI itself is three new files: 182 lines for the application, 15 lines
for launch documentation, and one pinned Streamlit dependency line.
