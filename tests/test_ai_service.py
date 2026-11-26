"""Verify API configuration, request limits, and safe errors without network calls."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from httpx2 import Request, Response
from openai import APIConnectionError, APIStatusError, APITimeoutError

from ai_service import (
    DEFAULT_MODEL,
    MAX_CONTEXT_MESSAGES,
    MAX_OUTPUT_TOKENS,
    REQUEST_TIMEOUT_SECONDS,
    AIServiceError,
    AISettings,
    get_live_reply,
    load_ai_settings,
)


class AIServiceTests(unittest.TestCase):
    def setUp(self):
        self.client = self.enterContext(patch("ai_service.OpenAI"))
        self.create_response = self.client.return_value.__enter__.return_value.responses.create
        self.settings = AISettings(api_key="fixture-value")
        self.history = [{"role": "user", "text": "My Wi-Fi drops.", "mode": "live"}]

    def test_reads_local_key_and_allows_model_environment_override(self):
        with patch.dict(os.environ, {"OPENAI_MODEL": "terminal-model"}):
            with patch("ai_service.dotenv_values", return_value={
                "OPENAI_API_KEY": "  fixture-value  ",
                "OPENAI_MODEL": "file-model",
            }):
                settings = load_ai_settings()
                self.assertEqual(settings, AISettings(api_key="fixture-value", model="terminal-model"))
                self.assertNotIn("fixture-value", repr(settings))

        with patch.dict(os.environ, {"OPENAI_MODEL": ""}):
            with patch("ai_service.dotenv_values", return_value={"OPENAI_MODEL": "file-model"}):
                self.assertEqual(load_ai_settings(), AISettings(api_key="", model="file-model"))
            with patch("ai_service.dotenv_values", return_value={}):
                self.assertEqual(load_ai_settings(), AISettings(api_key="", model=DEFAULT_MODEL))

    def test_sends_only_recent_live_context_with_request_limits(self):
        self.create_response.return_value = SimpleNamespace(status="completed", output_text="  Try another device.  ")
        history = [
            {"role": "user", "text": "Old note.", "mode": "live"},
            *[{"role": "user", "text": f"Live note {i}.", "mode": "live"} for i in range(MAX_CONTEXT_MESSAGES)],
            {"role": "user", "text": "Preview note.", "mode": "preview"},
        ]
        settings = AISettings(api_key="fixture-value", model="chosen-model")

        self.assertEqual(get_live_reply(settings, history, "Internet & Wi-Fi"), "Try another device.")
        self.client.assert_called_once_with(
            api_key="fixture-value",
            base_url="https://api.openai.com/v1",
            max_retries=0,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        self.create_response.assert_called_once()
        request = self.create_response.call_args.kwargs
        self.assertEqual(request["model"], "chosen-model")
        self.assertIn("Internet & Wi-Fi", request["instructions"])
        self.assertEqual(request["max_output_tokens"], MAX_OUTPUT_TOKENS)
        self.assertIs(request["store"], False)
        self.assertNotIn("tools", request)
        self.assertEqual(
            request["input"], [{"role": "user", "content": f"Live note {i}."} for i in range(MAX_CONTEXT_MESSAGES)]
        )

    def test_missing_and_malformed_keys_do_not_create_a_client(self):
        with self.assertRaisesRegex(AIServiceError, "needs an OpenAI API key"):
            get_live_reply(AISettings(api_key=""), self.history, None)
        with self.assertRaisesRegex(AIServiceError, "could not authenticate"):
            get_live_reply(AISettings(api_key="malformed value"), self.history, None)
        self.client.assert_not_called()

    def test_http_errors_have_safe_user_messages(self):
        request = Request("POST", "https://api.openai.com/v1/responses")
        for status, code, message in [
            (401, None, "authenticate"),
            (402, None, "out of API credits"),
            (429, "insufficient_quota", "out of API credits"),
            (429, "rate_limit_exceeded", "too quickly"),
            (403, None, "denied access"),
            (404, None, "model is unavailable"),
            (400, "model_not_found", "model is unavailable"),
            (408, None, "timed out"),
            (503, None, "temporarily unavailable"),
        ]:
            with self.subTest(status=status, code=code):
                self.create_response.side_effect = APIStatusError(
                    "private error detail",
                    response=Response(status, request=request),
                    body={"code": code},
                )
                with self.assertRaisesRegex(AIServiceError, message) as raised:
                    get_live_reply(self.settings, self.history, None)
                self.assertNotIn("private error detail", str(raised.exception))

    def test_connection_failure_and_timeout_are_distinct(self):
        request = Request("POST", "https://api.openai.com/v1/responses")
        for error, message in [
            (APIConnectionError(request=request), "Could not reach OpenAI"),
            (APITimeoutError(request), "timed out"),
        ]:
            with self.subTest(error=type(error).__name__):
                self.create_response.side_effect = error
                with self.assertRaisesRegex(AIServiceError, message):
                    get_live_reply(self.settings, self.history, None)

    def test_incomplete_empty_and_unexpected_replies_are_handled(self):
        for response, message in [
            (SimpleNamespace(status="incomplete", output_text="Partial advice"), "reply was cut short"),
            (SimpleNamespace(status="completed", output_text="  "), "did not return a usable reply"),
            (SimpleNamespace(status="failed", output_text=None), "did not return a usable reply"),
            (object(), "did not return a usable reply"),
        ]:
            self.create_response.return_value = response
            with self.assertRaisesRegex(AIServiceError, message):
                get_live_reply(self.settings, self.history, None)
