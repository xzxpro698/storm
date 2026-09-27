# Co-STORM Local UI

This Phase 1 Streamlit frontend keeps a live `CoStormRunner` in session state and
shows its conversation plus its current knowledge-base hierarchy.

From the repository root, install the UI dependency and launch the app:

```bash
pip install -r frontend/costorm_local/requirements.txt
streamlit run frontend/costorm_local/app.py
```

The app loads the existing root-level `secrets.toml` through `load_api_key()` and
uses the Gemini, OpenAI encoder, and Serper configuration already used by the local
Co-STORM runner.
