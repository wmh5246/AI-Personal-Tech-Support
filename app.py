"""Streamlit entry point for the local Windows troubleshooting interface."""

from pathlib import Path

import streamlit as st

try:
    from ai_service import AIServiceError, AISettings, MISSING_KEY, get_live_reply, load_ai_settings
except ModuleNotFoundError:
    st.error("A Python package is missing. Install the packages in requirements.txt, then restart the app.")
    st.stop()

from troubleshooting import QUICK_STARTS, placeholder_reply


MAX_PROBLEM_LENGTH = 2000


def reset_session() -> None:
    """Clear troubleshooting state while keeping the selected reply mode."""
    st.session_state.category = None
    st.session_state.messages = []
    st.session_state.problem_input = ""
    st.session_state.input_error = None
    st.session_state.reply_error = None
    st.session_state.reply_pending = False


def select_category(category: str) -> None:
    st.session_state.category = category


def submit_problem() -> None:
    """Record a submitted message and queue exactly one reply."""
    problem = (st.session_state.problem_input or "").strip()
    if not any(character.isprintable() and not character.isspace() for character in problem):
        st.session_state.input_error = "Enter a description of the problem before sending."
        return

    st.session_state.input_error = None
    st.session_state.reply_error = None
    mode = "preview" if st.session_state.preview_mode else "live"
    st.session_state.messages.append({"role": "user", "text": problem, "mode": mode})
    st.session_state.reply_pending = True


def render_sidebar(settings: AISettings) -> None:
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

        st.divider()
        st.toggle("Simulated preview", key="preview_mode", value=not settings.api_key)


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


def render_message(message: dict[str, str]) -> None:
    is_assistant = message["role"] == "assistant"
    avatar = ":material/support_agent:" if is_assistant else ":material/person:"
    with st.chat_message(message["role"], avatar=avatar):
        if is_assistant:
            label = "Simulated response · Placeholder" if message["mode"] == "preview" else "Live AI · OpenAI"
            st.caption(label)
        else:
            st.caption("You")
        st.text(message["text"])


def reply_to_pending_message(settings: AISettings) -> None:
    if not st.session_state.reply_pending:
        return

    # Consume the submission before calling the API so widget reruns cannot resend it.
    st.session_state.reply_pending = False
    messages = st.session_state.messages
    mode = messages[-1]["mode"]
    category = st.session_state.category
    if mode == "preview":
        first_message = not any(message["mode"] == "preview" for message in messages[:-1])
        reply = placeholder_reply(category, first_message=first_message)
    else:
        category_label = QUICK_STARTS[category]["label"] if category else None
        try:
            with st.spinner("Waiting for OpenAI…", show_time=True):
                reply = get_live_reply(settings, messages, category_label)
        except AIServiceError as error:
            st.session_state.reply_error = str(error)
            return

    message = {"role": "assistant", "text": reply, "mode": mode}
    messages.append(message)
    render_message(message)


def render_conversation(settings: AISettings) -> None:
    preview_mode = st.session_state.preview_mode
    live_key_missing = not preview_mode and not settings.api_key
    with st.container(key="conversation", border=True):
        st.subheader("Troubleshooting conversation", anchor=False)
        if preview_mode:
            st.caption("Simulated preview · Scripted replies stay on this computer.")
        else:
            st.caption(
                "Live AI · Sending a message shares your recent live conversation and selected category "
                "with OpenAI. Leave out passwords and other sensitive details."
            )
        if live_key_missing:
            st.warning(f"{MISSING_KEY} Turn on Simulated preview to continue without a key.")
        if not st.session_state.messages:
            st.markdown("**Tell us what’s happening.**")
            st.caption("For example, “My Wi-Fi disconnects during video calls.”")

        for message in st.session_state.messages:
            render_message(message)

        reply_to_pending_message(settings)
        if st.session_state.input_error:
            st.warning(st.session_state.input_error)
        if not preview_mode and st.session_state.reply_error:
            st.error(st.session_state.reply_error)

    # A main-page chat input stays visible at the bottom as the conversation grows.
    st.chat_input(
        "Describe your Windows PC problem",
        key="problem_input",
        max_chars=MAX_PROBLEM_LENGTH,
        disabled=live_key_missing,
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
    st.session_state.setdefault("reply_error", None)
    st.session_state.setdefault("reply_pending", False)

    settings = load_ai_settings()
    render_sidebar(settings)
    with st.container(key="support-intro"):
        st.markdown(":blue-badge[:material/desktop_windows: Windows PC support]")
        st.title("AI Personal Tech Support", anchor=False)
        st.markdown("Describe what’s happening with your PC, or pick a common issue to get started.")
    render_quick_starts()
    render_conversation(settings)


if __name__ == "__main__":
    main()
