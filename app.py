"""Streamlit entry point for the local Windows troubleshooting interface."""

from pathlib import Path
from typing import NotRequired, TypedDict

import streamlit as st

try:
    from ai_service import AIServiceError, AISettings, MISSING_KEY, get_live_reply, load_ai_settings
except ModuleNotFoundError:
    st.error("A Python package is missing. Install the packages in requirements.txt, then restart the app.")
    st.stop()

from diagnostic_state import Category, DiagnosticMemory, FACT_LABELS, GuidedStep, Stage, StepFeedback, StepOutcome
from knowledge_base import KnowledgeDocument, RetrievalResult, resolve_citations, retrieve_references
from troubleshooting import CATEGORY_LABELS, QUICK_STARTS, detect_preview_category, placeholder_reply


MAX_PROBLEM_LENGTH = 2000


class ChatMessage(TypedDict):
    role: str
    text: str
    mode: str
    citations: NotRequired[tuple[KnowledgeDocument, ...]]
    step: NotRequired[GuidedStep]
    feedback: NotRequired[StepFeedback]


def reset_session() -> None:
    """Clear troubleshooting state while keeping the selected reply mode."""
    st.session_state.category = None
    st.session_state.messages = []
    st.session_state.problem_input = ""
    st.session_state.input_error = None
    st.session_state.reply_error = None
    st.session_state.reply_pending = False
    st.session_state.last_retrieval = None
    st.session_state.active_step = None
    st.session_state.diagnostics = {"live": DiagnosticMemory(), "preview": DiagnosticMemory()}


def select_category(category: Category | None) -> None:
    detected = current_memory().detected_category
    if not st.session_state.preview_mode and (st.session_state.category or detected) != (category or detected):
        st.session_state.active_step = None
    st.session_state.category = category


def current_memory() -> DiagnosticMemory:
    mode = "preview" if st.session_state.preview_mode else "live"
    return st.session_state.diagnostics[mode]


def queue_message(text: str, feedback: StepFeedback | None = None) -> None:
    st.session_state.input_error = None
    st.session_state.reply_error = None
    mode = "preview" if st.session_state.preview_mode else "live"
    memory = current_memory()
    if memory.original_problem is None:
        memory.original_problem = text
    message: ChatMessage = {"role": "user", "text": text, "mode": mode}
    if feedback is not None:
        message["feedback"] = feedback
    st.session_state.messages.append(message)
    st.session_state.reply_pending = True


def submit_problem() -> None:
    """Record a submitted message and queue exactly one reply."""
    if st.session_state.reply_pending:
        return
    problem = (st.session_state.problem_input or "").strip()
    if not any(character.isprintable() and not character.isspace() for character in problem):
        st.session_state.input_error = "Enter a description of the problem before sending."
        return
    queue_message(problem)


def submit_step_feedback(index: int, outcome: StepOutcome) -> None:
    if st.session_state.preview_mode or st.session_state.reply_pending or st.session_state.active_step != index:
        return
    message = st.session_state.messages[index]
    step = message["step"]
    details = st.session_state.get(f"step-details-{index}", "").strip()
    feedback = StepFeedback(step.title, step.instructions, outcome, details)

    # Consume the active step before queueing a reply. A second widget event cannot submit it again.
    st.session_state.active_step = None
    message["feedback"] = feedback
    memory = current_memory()
    memory.step_history.append(feedback)
    if outcome == StepOutcome.SOLVED:
        memory.stage = Stage.RESOLVE
    report = f"Result for “{step.title}”: {outcome.value}."
    queue_message(f"{report}\n{details}" if details else report, feedback)


def render_sidebar(settings: AISettings):
    with st.sidebar:
        st.header("Your session", anchor=False)
        # Reserve the sidebar space so it can reflect the reply from this same run.
        details = st.container(key="session-details", border=True)
        st.button(
            "New troubleshooting session",
            key="new-session",
            icon=":material/add:",
            width="stretch",
            on_click=reset_session,
        )
        st.caption("Starting a new session clears the conversation, diagnostic notes, sources, and steps.")

        st.divider()
        st.toggle("Simulated preview", key="preview_mode", value=not settings.api_key)
    return details


def render_session_details(memory: DiagnosticMemory) -> None:
    manual_category = st.session_state.category
    detected_category = memory.detected_category
    category = manual_category or detected_category
    if memory.stage == Stage.RESOLVE:
        status = "Review outcome"
    elif memory.original_problem is not None:
        status = "In progress"
    elif category is not None:
        status = "Waiting for details"
    else:
        status = "Ready to start"

    st.caption("Troubleshooting category")
    st.markdown(CATEGORY_LABELS[category] if category else "None selected")
    if manual_category:
        st.caption("Manual selection")
        if detected_category and detected_category != manual_category:
            st.caption(f"Auto-detected: {CATEGORY_LABELS[detected_category]}")
        st.button("Use automatic category", key="auto-category", on_click=select_category, args=(None,))
    elif detected_category:
        st.caption("Auto-detected. Use a quick start to correct it.")
    elif memory.original_problem is not None:
        st.caption("The category is still unclear. Describe the symptom or choose a quick start.")
    if category != "general" and memory.original_problem is not None:
        st.button(
            "Use General Troubleshooting",
            key="general-category",
            type="tertiary",
            on_click=select_category,
            args=("general",),
        )

    st.caption("Session status")
    st.markdown(f":blue-badge[{status}]")
    st.markdown(f"**{memory.stage.value}**")
    steps = list(Stage)
    stage_number = steps.index(memory.stage) + 1
    st.progress(stage_number / len(steps), text=f"Stage {stage_number} of {len(steps)}")

    render_step_status()
    render_knowledge_status()
    with st.expander("Diagnostic notes"):
        if memory.original_problem is None:
            st.caption("No diagnostic details recorded yet.")
            return
        st.caption("Original problem")
        st.text(memory.original_problem)
        notes = [(label, memory.facts.get(kind, [])) for kind, label in FACT_LABELS.items()]
        notes.extend([
            ("Possible causes", memory.possible_causes),
            ("Unresolved questions", memory.unresolved_questions),
        ])
        for label, items in notes:
            if items:
                st.caption(label)
                st.text("\n".join(f"• {item}" for item in items))
        if memory.step_history:
            st.caption("Guided step outcomes")
            for feedback in memory.step_history:
                st.text(f"{feedback.title} · {feedback.outcome.value}")
                if feedback.details:
                    st.text(feedback.details)


def render_step_status() -> None:
    if st.session_state.preview_mode:
        return
    for message in reversed(st.session_state.messages):
        step = message.get("step")
        if step is not None:
            st.caption("Current step" if st.session_state.active_step is not None else "Latest step")
            st.text(step.title)
            feedback = message.get("feedback")
            st.caption(feedback.outcome.value if feedback else "No outcome reported")
            return


def render_knowledge_status() -> None:
    st.caption("Knowledge retrieval")
    result: RetrievalResult | None = st.session_state.last_retrieval
    if st.session_state.preview_mode:
        st.caption("Not performed in simulated preview.")
    elif result is None:
        st.caption("Not performed yet.")
    elif not result.available:
        st.caption("Local knowledge base unavailable. Live chat can continue with general guidance.")
    elif not result.documents:
        st.caption("Search completed. No relevant entries found.")
    else:
        with st.expander(f"Retrieved references ({len(result.documents)})"):
            st.text("\n".join(f"• {document.title}" for document in result.documents))
            st.caption("Sources cited for a recommendation appear under its reply in the conversation.")


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


def render_message(message: ChatMessage) -> None:
    is_assistant = message["role"] == "assistant"
    avatar = ":material/support_agent:" if is_assistant else ":material/person:"
    with st.chat_message(message["role"], avatar=avatar):
        if is_assistant:
            label = "Simulated response · Placeholder" if message["mode"] == "preview" else "Live AI · OpenAI"
            st.caption(label)
        else:
            st.caption("You")
        st.text(message["text"])
        step = message.get("step")
        if step is not None:
            render_step(step, message.get("feedback"))
        if is_assistant and message["mode"] == "live":
            citations = message.get("citations", ())
            if citations:
                st.caption("Sources cited for this reply")
                for number, document in enumerate(citations, start=1):
                    st.link_button(f"[{number}] {document.source_title} · {document.source_organization}", document.source_url)
            else:
                st.caption("General AI guidance · No knowledge base sources cited for this reply.")


def render_step(step: GuidedStep, feedback: StepFeedback | None) -> None:
    with st.container(border=True):
        st.caption("Troubleshooting step")
        st.text(step.title)
        st.text(step.instructions)
        st.caption("What to look for")
        st.text(step.expected)
        if step.safety:
            st.caption("Before you start")
            st.text(step.safety)
        if feedback is not None:
            st.caption(f"Reported outcome · {feedback.outcome.value}")


def render_feedback_controls() -> None:
    index = st.session_state.active_step
    if st.session_state.preview_mode or index is None:
        return
    step = st.session_state.messages[index]["step"]
    # Submit the note and outcome together. Enter alone must not choose an outcome.
    with st.form(key=f"feedback-form-{index}", enter_to_submit=False):
        st.caption("How did the current step go?")
        st.text(step.title)
        st.text_input("Describe what happened (optional)", key=f"step-details-{index}", max_chars=MAX_PROBLEM_LENGTH)
        for column, outcome in zip(st.columns(3, gap="small"), StepOutcome, strict=True):
            column.form_submit_button(
                outcome.value,
                key=f"step-feedback-{index}-{outcome.name}",
                width="stretch",
                on_click=submit_step_feedback,
                args=(index, outcome),
            )


def reported_text(message: ChatMessage) -> str:
    feedback = message.get("feedback")
    return feedback.details if feedback is not None else message["text"]


def reply_to_pending_message(settings: AISettings) -> None:
    if not st.session_state.reply_pending:
        return

    # Consume the submission before calling the API so widget reruns cannot resend it.
    st.session_state.reply_pending = False
    messages = st.session_state.messages
    mode = messages[-1]["mode"]
    memory = st.session_state.diagnostics[mode]
    category = st.session_state.category
    message: ChatMessage = {"role": "assistant", "text": "", "mode": mode}
    if mode == "preview":
        first_message = not any(message["mode"] == "preview" for message in messages[:-1])
        previous_category = memory.detected_category
        memory.detected_category = detect_preview_category(messages[-1]["text"], previous_category)
        category = category or memory.detected_category
        asking_for_details = first_message or memory.detected_category != previous_category or memory.stage == Stage.IDENTIFY
        reply = placeholder_reply(category, first_message=asking_for_details)
        if asking_for_details:
            memory.stage = Stage.GATHER if category else Stage.IDENTIFY
            memory.unresolved_questions = [reply]
    else:
        category_label = CATEGORY_LABELS[category] if category else None
        feedback = messages[-1].get("feedback")
        latest = reported_text(messages[-1]) or (feedback.outcome.value if feedback else "")
        user_reports = [
            reported_text(turn) for turn in messages if turn["mode"] == "live" and turn["role"] == "user"
        ]
        retrieval = retrieve_references(
            latest,
            original=memory.original_problem or "",
            category=category,
            session_context=tuple(memory.facts.get("symptoms", [])[-4:]),
            findings=(*user_reports[-4:-1], *memory.facts.get("reported_results", [])[-4:]),
        )
        st.session_state.last_retrieval = retrieval
        try:
            with st.spinner("Waiting for OpenAI…", show_time=True):
                update = get_live_reply(settings, messages, category_label, memory, retrieval.documents)
        except AIServiceError as error:
            st.session_state.reply_error = str(error)
            return
        previous_category = memory.detected_category
        memory.apply(update, user_reports)
        reply = update.reply.strip()
        message["citations"] = resolve_citations(update.citation_ids, retrieval.documents)
        confirmed_solved = feedback is not None and feedback.outcome == StepOutcome.SOLVED
        if confirmed_solved:
            memory.stage = Stage.RESOLVE
        if memory.stage == Stage.RESOLVE or (category is None and memory.detected_category != previous_category):
            st.session_state.active_step = None
        step = update.step
        if not confirmed_solved and step is not None and step.title and step.instructions and step.expected:
            message["step"] = step
            st.session_state.active_step = len(messages)

    message["text"] = reply
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
                "Live AI · Searching the knowledge base runs on this computer. Sending a message shares your recent live "
                "conversation, diagnostic notes, step feedback, selected category, and any retrieved reference summaries with OpenAI. "
                "Leave out passwords and other sensitive details."
            )
        if live_key_missing:
            st.warning(f"{MISSING_KEY} Turn on Simulated preview to continue without a key.")
        if not st.session_state.messages:
            st.markdown("**Tell us what’s happening.**")
            st.caption("For example, “My Wi-Fi disconnects during video calls.”")

        for message in st.session_state.messages:
            render_message(message)

        reply_to_pending_message(settings)
        if not live_key_missing:
            render_feedback_controls()
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
    st.session_state.setdefault("last_retrieval", None)
    st.session_state.setdefault("active_step", None)
    st.session_state.setdefault("diagnostics", {"live": DiagnosticMemory(), "preview": DiagnosticMemory()})

    settings = load_ai_settings()
    details = render_sidebar(settings)
    with st.container(key="support-intro"):
        st.markdown(":blue-badge[:material/desktop_windows: Windows PC support]")
        st.title("AI Personal Tech Support", anchor=False)
        st.markdown("Describe what’s happening with your PC, or pick a common issue to get started.")
    render_quick_starts()
    render_conversation(settings)
    with details:
        render_session_details(current_memory())


if __name__ == "__main__":
    main()
