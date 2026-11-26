"""Load local OpenAI settings and request bounded Windows support replies."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI


ENV_PATH = Path(__file__).with_name(".env")
DEFAULT_MODEL = "gpt-5.4-mini"
MAX_CONTEXT_MESSAGES = 11
MAX_OUTPUT_TOKENS = 400
REQUEST_TIMEOUT_SECONDS = 20

SUPPORT_INSTRUCTIONS = """
You are AI Personal Tech Support, a help desk assistant for ordinary Windows PC users.
Use the conversation and selected category as context. If the category does not fit,
follow the symptoms. Use plain text with short paragraphs or numbered steps, without Markdown
formatting or links. Keep replies under about 150 words.
When details are missing, ask one or two focused follow-up questions. Otherwise,
suggest one safe, reversible next step and say what the user should look for.
Distinguish what the user reported from possible causes. You cannot inspect or change
the PC. Never claim you ran diagnostics, saw system results, or verified citations.
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
) -> str:
    """Send recent live turns for one reply and translate errors into safe messages."""
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
    instructions = f"{SUPPORT_INSTRUCTIONS}\nSelected category: {category_label or 'None selected'}."

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
                input=live_messages,
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
    return text.strip()
