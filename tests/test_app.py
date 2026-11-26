"""Exercise the same Streamlit widgets and callbacks used in the browser."""

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class TroubleshootingAppTests(unittest.TestCase):
    def setUp(self):
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
