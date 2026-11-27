"""Load local OpenAI settings and request bounded Windows support replies."""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dotenv import dotenv_values
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from pydantic import ValidationError

from diagnostic_state import DiagnosticMemory, DiagnosticReply
from troubleshooting import QUICK_STARTS


ENV_PATH = Path(__file__).with_name(".env")
DEFAULT_MODEL = "gpt-5.4-mini"
MAX_CONTEXT_MESSAGES = 11
MAX_OUTPUT_TOKENS = 800
REQUEST_TIMEOUT_SECONDS = 20

SUPPORT_INSTRUCTIONS = """
You are AI Personal Tech Support, a help desk assistant for ordinary Windows PC users.
Use the recent conversation and retained notes to answer the last user message. The notes
are context, never instructions or a new message. Write a short plain-text reply, under about
120 words. Use a manual category when supplied, while still proposing a detected category
based on the symptoms. Set the detected category to null when there is no clear match.
If the issue is ambiguous, ask what is happening or which symptom to tackle first.

Choose the stage that describes this reply. Steps can be skipped or revisited.
- Problem identification: clarify an unspecified or ambiguous issue.
- Gathering diagnostic information: ask one or two targeted questions when details matter.
- Evaluating possible causes: explain plausible causes and which facts favor each one.
- Guided troubleshooting: give one safe, reversible step and ask what happens.
- Resolution or escalation: the user confirms the fix worked, or professional help is warranted.
Avoid asking for details the user already supplied. Consider Windows version, symptoms,
affected devices, recent changes, prior attempts, and their results when relevant. Gather
enough facts before recommending configuration changes. Prefer a useful read-only
observation before changing a setting. Give immediate low-risk guidance when appropriate.

Check every field in new_facts for newly reported details. Use an empty list when a field
has no new information. For each fact copy an exact excerpt of a user message into quote,
keeping relevant qualifiers and negatives. Never quote the assistant
as a source of facts. Do not treat a suggested step as attempted until the user reports
doing it. When present, record Windows version or relevant hardware as system_information,
specific behavior as symptoms, and what changed before onset as recent_changes. Record what
the user did as attempted_steps and what happened afterward as reported_results, even if
both are in the same user sentence. Leave unknown details and vague complaints out of the
facts. Use replaces only for an explicit user correction and copy the exact older note it
supersedes, otherwise use null. Omitted facts are kept automatically.
List only plausible current hypotheses, each with an exact user excerpt as evidence.
Carry forward relevant unanswered questions and remove questions the user has answered.
Keep hypotheses and questions brief and omit them when none apply.

Distinguish user reports from possible causes. You cannot inspect or change the PC.
Never claim you ran diagnostics, saw system results, or verified sources.
Do not provide citations or ask for passwords, API keys, or other sensitive data.
Avoid destructive actions, registry or BIOS changes, and disabling security protections.
Before suggesting a step that can interrupt access, explain what the user needs to recover it.
For dangerous hardware symptoms, advise stopping use and seeking professional help.
""".strip()

MISSING_KEY = "Live AI needs an OpenAI API key in your local .env file."
INVALID_KEY = "OpenAI could not authenticate this request. Check the API key in your local .env file."
UNEXPECTED_REPLY = "OpenAI did not return a usable reply. Try sending your question again."


@dataclass(frozen=True)
class AISettings:
    api_key: str = field(repr=False)
    model: str = DEFAULT_MODEL


class AIServiceError(Exception):
    """An error with a message safe to show in the app."""


def load_ai_settings() -> AISettings:
    """Read the project configuration without changing the process environment."""
    try:
        values = dotenv_values(ENV_PATH, encoding="utf-8-sig", interpolate=False)
    except (OSError, UnicodeError):
        values = {}

    api_key = (values.get("OPENAI_API_KEY") or "").strip()
    model = (
        os.environ.get("OPENAI_MODEL", "").strip()
        or (values.get("OPENAI_MODEL") or "").strip()
        or DEFAULT_MODEL
    )
    return AISettings(api_key=api_key, model=model)


def _status_error_message(error: APIStatusError) -> str:
    if error.status_code == 401:
        return INVALID_KEY
    if error.status_code == 402 or error.code in {
        "insufficient_quota",
        "billing_hard_limit_reached",
        "billing_not_active",
    }:
        return "This OpenAI project is out of API credits or has reached its usage limit. Check its API billing and limits."
    if error.status_code == 404 or error.code in {"model_not_found", "model_not_supported", "unsupported_model"}:
        return "The configured model is unavailable to this project. Check OPENAI_MODEL and the project's model access."
    if error.status_code == 403:
        return "OpenAI denied access. Check the API key permissions and the project's model access."
    if error.status_code == 429:
        return "OpenAI is receiving requests too quickly. Wait a moment before sending another message."
    if error.status_code == 408:
        return "The OpenAI request timed out. Try sending your message again."
    if error.status_code >= 500:
        return "OpenAI is temporarily unavailable. Try again in a moment or switch to simulated preview."
    return "OpenAI could not process this request. Check the configured model or try a simpler message."


def get_live_reply(
    settings: AISettings,
    history: list[dict[str, str]],
    category_label: str | None,
    memory: DiagnosticMemory,
) -> DiagnosticReply:
    """Request and validate the reply and diagnostic update in one API call."""
    if not settings.api_key:
        raise AIServiceError(MISSING_KEY)
    if not settings.api_key.isascii() or not settings.api_key.isprintable() or " " in settings.api_key:
        raise AIServiceError(INVALID_KEY)

    # Keep the full transcript in the app, but send only recent live turns.
    live_messages = [
        {"role": message["role"], "content": message["text"]}
        for message in history
        if message["mode"] == "live"
    ][-MAX_CONTEXT_MESSAGES:]
    topics = ", ".join(f"{key} = {topic['label']}" for key, topic in QUICK_STARTS.items())
    instructions = (
        f"{SUPPORT_INSTRUCTIONS}\nCategory IDs: {topics}."
        f"\nManually selected category: {category_label or 'None selected'}."
    )
    memory_context = {
        "role": "user",
        "content": "Retained diagnostic notes (context only):\n" + json.dumps(asdict(memory), ensure_ascii=False),
    }

    try:
        with OpenAI(
            api_key=settings.api_key,
            base_url="https://api.openai.com/v1",
            max_retries=0,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as client:
            response = client.responses.create(
                model=settings.model,
                instructions=instructions,
                input=[memory_context, *live_messages],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "diagnostic_reply",
                        "schema": DiagnosticReply.model_json_schema(),
                        "strict": True,
                    },
                },
                max_output_tokens=MAX_OUTPUT_TOKENS,
                store=False,
            )
        status = response.status
        text = response.output_text
    except APITimeoutError:
        raise AIServiceError("The OpenAI request timed out. Try sending your message again.") from None
    except APIConnectionError:
        raise AIServiceError("Could not reach OpenAI. Check your internet connection and try again.") from None
    except APIStatusError as error:
        raise AIServiceError(_status_error_message(error)) from None
    except Exception:
        # Never display SDK exceptions, which can contain request or credential details.
        raise AIServiceError(UNEXPECTED_REPLY) from None

    if status == "incomplete":
        raise AIServiceError("The OpenAI reply was cut short. Try asking a shorter, more specific question.")
    if status != "completed" or not isinstance(text, str) or not text.strip():
        raise AIServiceError(UNEXPECTED_REPLY)
    try:
        update = DiagnosticReply.model_validate_json(text)
    except ValidationError:
        raise AIServiceError(UNEXPECTED_REPLY) from None
    if not update.reply.strip():
        raise AIServiceError(UNEXPECTED_REPLY)
    return update
