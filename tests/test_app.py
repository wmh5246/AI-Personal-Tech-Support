"""Exercise the same Streamlit widgets and callbacks used in the browser."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from ai_service import AIServiceError, AISettings


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class TroubleshootingAppTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("ai_service.load_ai_settings", return_value=AISettings(api_key="")))
        self.app = AppTest.from_file(str(APP_PATH)).run()
        self.assertFalse(self.app.exception)

    def assert_sidebar_contains(self, text):
        self.assertTrue(any(text in item.value for item in self.app.sidebar.markdown))

    def test_initial_screen(self):
        self.assertEqual(self.app.title[0].value, "AI Personal Tech Support")
        self.assert_sidebar_contains("None selected")
        self.assert_sidebar_contains("Ready to start")
        self.assertEqual(len(self.app.chat_message), 0)

    def test_quick_starts_update_the_category_and_status(self):
        categories = {
            "internet": "Internet & Wi-Fi",
            "performance": "Slow PC",
            "storage": "Storage",
            "audio": "Audio & Drivers",
            "gaming": "Overheating & Gaming",
        }
        for category, label in categories.items():
            with self.subTest(category=category):
                self.app.button(key=f"category-{category}").click().run()
                self.assertFalse(self.app.exception)
                self.assert_sidebar_contains(label)
                self.assert_sidebar_contains("Waiting for details")

    def test_chat_uses_the_selected_category_and_retains_previous_turns(self):
        self.app.button(key="category-internet").click().run()
        self.app.chat_input[0].set_value("  My Wi-Fi drops during calls.  ").run()
        self.assertFalse(self.app.exception)
        self.assertEqual([message.name for message in self.app.chat_message], ["user", "assistant"])
        self.assertEqual(self.app.chat_message[0].text[0].value, "My Wi-Fi drops during calls.")
        self.assertIn("other devices", self.app.chat_message[1].text[0].value)
        self.assertIn("Simulated response", self.app.chat_message[1].caption[0].value)
        self.assert_sidebar_contains("In progress")

        self.app.chat_input[0].set_value("It also affects my phone.").run()
        self.app.button(key="category-storage").click().run()
        self.assertEqual(len(self.app.chat_message), 4)
        self.assertEqual(self.app.chat_message[0].text[0].value, "My Wi-Fi drops during calls.")
        self.assertEqual(self.app.chat_message[2].text[0].value, "It also affects my phone.")
        self.assert_sidebar_contains("Storage")

    def test_chat_accepts_a_problem_without_a_category_and_displays_plain_text(self):
        problem = "My screen shows <error> and **flashes**."
        self.app.chat_input[0].set_value(problem).run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.chat_message[0].text[0].value, problem)
        self.assertIn("When did the problem start", self.app.chat_message[1].text[0].value)
        self.assert_sidebar_contains("None selected")
        self.assert_sidebar_contains("In progress")

    def test_invalid_input_does_not_add_messages(self):
        for problem in ("", "  \t\n ", "\u200b"):
            with self.subTest(problem=problem):
                self.app.chat_input[0].set_value(problem).run()
                self.assertFalse(self.app.exception)
                self.assertEqual(len(self.app.chat_message), 0)
                self.assertIn("Enter a description", self.app.warning[0].value)

        self.app.chat_input[0].set_value("My PC freezes.").run()
        self.assertEqual(len(self.app.warning), 0)
        self.assertEqual(len(self.app.chat_message), 2)

    def test_chat_limits_problem_descriptions_to_2000_characters(self):
        self.app.chat_input[0].set_value("x" * 2001).run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.chat_message[0].text[0].value, "x" * 2000)

    def test_new_session_clears_history_category_and_error(self):
        self.app.button(key="category-audio").click().run()
        self.app.chat_input[0].set_value("I lost sound after an update.").run()
        self.app.chat_input[0].set_value("   ").run()
        self.assertEqual(len(self.app.warning), 1)
        self.app.button(key="new-session").click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(len(self.app.chat_message), 0)
        self.assertEqual(len(self.app.warning), 0)
        self.assert_sidebar_contains("None selected")
        self.assert_sidebar_contains("Ready to start")

        self.app.chat_input[0].set_value("My PC overheats.").run()
        self.assertEqual(len(self.app.chat_message), 2)
        self.assertIn("When did the problem start", self.app.chat_message[1].text[0].value)


class LiveAppTests(unittest.TestCase):
    def test_live_replies_keep_context_without_sending_on_reruns(self):
        self.enterContext(patch("ai_service.load_ai_settings", return_value=AISettings(api_key="mock-key")))
        client = self.enterContext(patch("ai_service.OpenAI"))
        create_response = client.return_value.__enter__.return_value.responses.create
        create_response.side_effect = [
            SimpleNamespace(status="completed", output_text="Are other devices affected?"),
            SimpleNamespace(status="completed", output_text="Check whether it happens near the router, too."),
        ]
        app = AppTest.from_file(str(APP_PATH)).run()
        self.assertFalse(app.toggle(key="preview_mode").value)
        self.assertTrue(any("shares your recent live conversation" in item.value for item in app.caption))

        app.button(key="category-internet").click().run()
        app.chat_input[0].set_value("  ").run()
        create_response.assert_not_called()
        app.chat_input[0].set_value("My Wi-Fi drops.").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.chat_message[1].caption[0].value, "Live AI · OpenAI")
        self.assertEqual(app.chat_message[1].text[0].value, "Are other devices affected?")
        app.run()
        app.button(key="category-internet").click().run()
        self.assertEqual(create_response.call_count, 1)

        app.chat_input[0].set_value("Yes, my phone too.").run()
        self.assertFalse(app.exception)
        self.assertEqual(create_response.call_count, 2)
        self.assertEqual(
            create_response.call_args.kwargs["input"],
            [
                {"role": "user", "content": "My Wi-Fi drops."},
                {"role": "assistant", "content": "Are other devices affected?"},
                {"role": "user", "content": "Yes, my phone too."},
            ],
        )
        self.assertIn("Internet & Wi-Fi", create_response.call_args.kwargs["instructions"])
        self.assertEqual(len(app.chat_message), 4)

        app.button(key="new-session").click().run()
        self.assertEqual(len(app.chat_message), 0)
        self.assertFalse(app.toggle(key="preview_mode").value)
        self.assertEqual(create_response.call_count, 2)

    def test_preview_stays_local_even_when_live_is_configured(self):
        self.enterContext(patch("ai_service.load_ai_settings", return_value=AISettings(api_key="mock-key")))
        client = self.enterContext(patch("ai_service.OpenAI"))
        create_response = client.return_value.__enter__.return_value.responses.create
        create_response.return_value = SimpleNamespace(status="completed", output_text="When did it start?")
        app = AppTest.from_file(str(APP_PATH)).run()
        app.toggle(key="preview_mode").set_value(True).run()
        app.chat_input[0].set_value("A preview-only example.").run()
        client.assert_not_called()
        self.assertEqual(app.chat_message[1].caption[0].value, "Simulated response · Placeholder")

        app.toggle(key="preview_mode").set_value(False).run()
        client.assert_not_called()
        app.chat_input[0].set_value("Live example.").run()
        self.assertFalse(app.exception)
        self.assertEqual(create_response.call_args.kwargs["input"], [{"role": "user", "content": "Live example."}])
        self.assertEqual(app.chat_message[1].caption[0].value, "Simulated response · Placeholder")
        self.assertEqual(app.chat_message[3].caption[0].value, "Live AI · OpenAI")

    def test_missing_key_defaults_to_preview_and_disables_live_submission(self):
        self.enterContext(patch("ai_service.load_ai_settings", return_value=AISettings(api_key="")))
        client = self.enterContext(patch("ai_service.OpenAI"))
        app = AppTest.from_file(str(APP_PATH)).run()
        self.assertTrue(app.toggle(key="preview_mode").value)
        app.toggle(key="preview_mode").set_value(False).run()
        self.assertFalse(app.exception)
        self.assertIn("needs an OpenAI API key", app.warning[0].value)
        self.assertTrue(app.chat_input[0].proto.disabled)
        client.assert_not_called()

    def test_live_error_keeps_the_user_message_without_automatic_retry(self):
        self.enterContext(patch("ai_service.load_ai_settings", return_value=AISettings(api_key="mock-key")))
        reply = self.enterContext(
            patch("ai_service.get_live_reply", side_effect=AIServiceError("The OpenAI request timed out."))
        )
        app = AppTest.from_file(str(APP_PATH)).run()
        app.chat_input[0].set_value("My PC freezes.").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.chat_message), 1)
        self.assertIn("timed out", app.error[0].value)

        app.run()
        self.assertEqual(reply.call_count, 1)
        self.assertIn("timed out", app.error[0].value)
        app.button(key="new-session").click().run()
        self.assertFalse(app.error)
        self.assertFalse(app.chat_message)
        self.assertEqual(reply.call_count, 1)
