"""Interactive local Streamlit frontend for Co-STORM."""

import os
from pathlib import Path

import streamlit as st

from knowledge_storm.collaborative_storm.engine import (
    CollaborativeStormLMConfigs,
    CoStormRunner,
    RunnerArgument,
)
from knowledge_storm.lm import LitellmModel
from knowledge_storm.logging_wrapper import LoggingWrapper
from knowledge_storm.rm import SerperRM
from knowledge_storm.utils import load_api_key


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GEMINI_MODEL = "gemini/gemini-3.5-flash-lite"


def build_runner(topic: str) -> CoStormRunner:
    """Build a runner with the same Gemini and Serper setup as the CLI example."""
    load_api_key(toml_file_path=REPOSITORY_ROOT / "secrets.toml")

    gemini_kwargs = {
        "api_key": os.getenv("GOOGLE_API_KEY"),
        "temperature": 1.0,
        "top_p": 0.9,
    }
    lm_config = CollaborativeStormLMConfigs()
    lm_config.set_question_answering_lm(
        LitellmModel(model=GEMINI_MODEL, max_tokens=800, **gemini_kwargs)
    )
    lm_config.set_discourse_manage_lm(
        LitellmModel(model=GEMINI_MODEL, max_tokens=300, **gemini_kwargs)
    )
    lm_config.set_utterance_polishing_lm(
        LitellmModel(model=GEMINI_MODEL, max_tokens=800, **gemini_kwargs)
    )
    lm_config.set_warmstart_outline_gen_lm(
        LitellmModel(model=GEMINI_MODEL, max_tokens=400, **gemini_kwargs)
    )
    lm_config.set_question_asking_lm(
        LitellmModel(model=GEMINI_MODEL, max_tokens=200, **gemini_kwargs)
    )
    lm_config.set_knowledge_base_lm(
        LitellmModel(model=GEMINI_MODEL, max_tokens=800, **gemini_kwargs)
    )

    runner_argument = RunnerArgument(topic=topic)
    rm = SerperRM(
        serper_search_api_key=os.getenv("SERPER_API_KEY"),
        query_params={"autocorrect": True, "num": 10, "page": 1},
    )
    return CoStormRunner(
        lm_config=lm_config,
        runner_argument=runner_argument,
        logging_wrapper=LoggingWrapper(lm_config),
        rm=rm,
    )


def get_runner() -> CoStormRunner | None:
    return st.session_state.get("costorm_runner")


def render_conversation(runner: CoStormRunner) -> None:
    st.subheader("Conversation")
    if not runner.conversation_history:
        st.info("No conversation turns yet.")
        return

    for turn in runner.conversation_history:
        role = turn.role or "Unknown"
        with st.chat_message("user" if role == "Guest" else "assistant"):
            st.caption(f"{role} · {turn.utterance_type}")
            st.markdown(turn.utterance)


def render_knowledge_tree(runner: CoStormRunner) -> None:
    st.subheader("Knowledge Tree")
    tree = runner.knowledge_base.get_node_hierarchy_string(
        include_indent=True,
        include_full_path=False,
        include_hash_tag=True,
        include_node_content_count=True,
    )
    st.code(tree or "No knowledge-base nodes yet.", language="markdown")


def reset_session() -> None:
    for key in ("costorm_runner", "costorm_report", "costorm_error"):
        st.session_state.pop(key, None)


def main() -> None:
    st.set_page_config(page_title="Co-STORM Local", layout="wide")
    st.title("Co-STORM Local")
    st.caption("Gemini generation · OpenAI embeddings · Serper retrieval")

    with st.sidebar:
        st.header("Session")
        if st.button("Reset / New Session", use_container_width=True):
            reset_session()
            st.rerun()

    topic = st.text_input("Research topic", key="costorm_topic")
    if st.button("Start Research", type="primary", disabled=not topic.strip()):
        try:
            with st.spinner("Warming up Co-STORM…"):
                runner = build_runner(topic.strip())
                runner.warm_start()
            st.session_state.costorm_runner = runner
            st.session_state.pop("costorm_report", None)
            st.session_state.pop("costorm_error", None)
            st.rerun()
        except Exception as exc:
            st.session_state.costorm_error = str(exc)

    if st.session_state.get("costorm_error"):
        st.error(st.session_state.costorm_error)

    runner = get_runner()
    if runner is None:
        st.info("Enter a topic and start research to create a Co-STORM session.")
        return

    conversation_column, knowledge_column = st.columns(2)
    with conversation_column:
        render_conversation(runner)
    with knowledge_column:
        render_knowledge_tree(runner)

    st.subheader("Continue Research")
    with st.form("human_utterance_form", clear_on_submit=True):
        user_utterance = st.text_area("Your message")
        submit_utterance = st.form_submit_button("Submit Human Utterance")

    if submit_utterance and user_utterance.strip():
        try:
            runner.step(user_utterance=user_utterance.strip())
            st.session_state.costorm_error = None
            st.rerun()
        except Exception as exc:
            st.session_state.costorm_error = str(exc)
            st.rerun()

    if st.button("Generate Next Co-STORM Turn"):
        try:
            with st.spinner("Co-STORM is generating a turn…"):
                conv_turn = runner.step()
            if conv_turn is None:
                raise RuntimeError(
                    "Co-STORM did not produce a turn; inspect the preceding server log."
                )
            st.session_state.costorm_error = None
            st.rerun()
        except Exception as exc:
            st.session_state.costorm_error = str(exc)
            st.rerun()

    if st.button("Generate Final Report"):
        try:
            with st.spinner("Generating report…"):
                runner.knowledge_base.reorganize()
                st.session_state.costorm_report = runner.generate_report()
            st.session_state.costorm_error = None
            st.rerun()
        except Exception as exc:
            st.session_state.costorm_error = str(exc)
            st.rerun()

    report = st.session_state.get("costorm_report")
    if report:
        st.subheader("Final Report")
        st.markdown(report)


if __name__ == "__main__":
    main()
