"""Streamlit entry point for the local Windows troubleshooting interface."""

from pathlib import Path

import streamlit as st

from troubleshooting import QUICK_STARTS, placeholder_reply


MAX_PROBLEM_LENGTH = 2000


def reset_session() -> None:
    """Clear the current category, conversation, and any draft or input error."""
    st.session_state.category = None
    st.session_state.messages = []
    st.session_state.problem_input = ""
    st.session_state.input_error = None


def select_category(category: str) -> None:
    st.session_state.category = category


def submit_problem() -> None:
    """Validate the chat input and add one user and one placeholder message."""
    problem = (st.session_state.problem_input or "").strip()
    if not any(character.isprintable() and not character.isspace() for character in problem):
        st.session_state.input_error = "Enter a description of the problem before sending."
        return

    st.session_state.input_error = None
    messages = st.session_state.messages
    reply = placeholder_reply(st.session_state.category, first_message=not messages)
    messages.extend(
        [
            {"role": "user", "text": problem},
            {"role": "assistant", "text": reply},
        ]
    )


def render_sidebar() -> None:
    category = st.session_state.category
    if st.session_state.messages:
        status = "In progress"
    elif category is not None:
        status = "Waiting for details"
    else:
        status = "Ready to start"

    with st.sidebar:
        st.header("Your session", anchor=False)
        with st.container(key="session-details", border=True):
            st.caption("Troubleshooting category")
            st.markdown(QUICK_STARTS[category]["label"] if category else "None selected")
            st.caption("Session status")
            st.markdown(f":blue-badge[{status}]")
        st.button(
            "New troubleshooting session",
            key="new-session",
            icon=":material/add:",
            width="stretch",
            on_click=reset_session,
        )
        st.caption("Starting a new session clears the current conversation and category.")


def render_quick_starts() -> None:
    st.subheader("Quick starts", anchor=False)
    with st.container(key="quick-starts"):
        columns = st.columns(len(QUICK_STARTS), gap="small")
        for column, (category, topic) in zip(columns, QUICK_STARTS.items(), strict=True):
            column.button(
                topic["label"],
                key=f"category-{category}",
                icon=f":material/{topic['icon']}:",
                width="stretch",
                type="primary" if st.session_state.category == category else "secondary",
                on_click=select_category,
                args=(category,),
            )


def render_conversation() -> None:
    with st.container(key="conversation", border=True):
        st.subheader("Troubleshooting conversation", anchor=False)
        st.caption("Preview mode uses scripted replies.")
        if not st.session_state.messages:
            st.markdown("**Tell us what’s happening.**")
            st.caption("For example, “My Wi-Fi disconnects during video calls.”")

        for message in st.session_state.messages:
            is_assistant = message["role"] == "assistant"
            avatar = ":material/support_agent:" if is_assistant else ":material/person:"
            with st.chat_message(message["role"], avatar=avatar):
                st.caption("Simulated response · Placeholder" if is_assistant else "You")
                st.text(message["text"])

        if st.session_state.input_error:
            st.warning(st.session_state.input_error)

    # A main-page chat input stays visible at the bottom as the conversation grows.
    st.chat_input(
        "Describe your Windows PC problem",
        key="problem_input",
        max_chars=MAX_PROBLEM_LENGTH,
        on_submit=submit_problem,
    )


def main() -> None:
    st.set_page_config(
        page_title="AI Personal Tech Support",
        page_icon=":material/support_agent:",
        layout="wide",
    )
    st.html(Path(__file__).with_name("styles.css"))
    st.session_state.setdefault("category", None)
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("input_error", None)

    render_sidebar()
    with st.container(key="support-intro"):
        st.markdown(":blue-badge[:material/desktop_windows: Windows PC support]")
        st.title("AI Personal Tech Support", anchor=False)
        st.markdown("Describe what’s happening with your PC, or pick a common issue to get started.")
    render_quick_starts()
    render_conversation()


if __name__ == "__main__":
    main()
