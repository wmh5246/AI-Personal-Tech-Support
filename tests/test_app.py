"""Exercise the same Streamlit widgets and callbacks used in the browser."""

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from ai_service import AIServiceError, AISettings
from app import submit_step_feedback
from diagnostic_state import DiagnosticReply, FACT_LABELS, FactUpdates, GuidedStep, ReportedFact, Stage, StepOutcome
from knowledge_base import KnowledgeBaseError, load_knowledge_base


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
SOUND_STEP = GuidedStep(
    title="Check the active sound output",
    instructions="Open Windows Sound settings and look for your headphones under Output.",
    expected="Your headphones appear by name.",
    safety="Keep the listening volume low before playing a test sound.",
)


def live_response(reply, category=None, stage=Stage.IDENTIFY, facts=None, *, citation_ids=(), step=None):
    update = DiagnosticReply(
        reply=reply,
        detected_category=category,
        stage=stage,
        new_facts=FactUpdates(**{kind: (facts or {}).get(kind, []) for kind in FACT_LABELS}),
        possible_causes=[],
        unresolved_questions=[],
        citation_ids=list(citation_ids),
        step=step,
    )
    return SimpleNamespace(status="completed", output_text=update.model_dump_json())


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
        self.assertIn("particular game", self.app.chat_message[1].text[0].value)
        self.assert_sidebar_contains("Overheating & Gaming")


class LiveAppTests(unittest.TestCase):
    def test_live_replies_keep_context_without_sending_on_reruns(self):
        self.enterContext(patch("ai_service.load_ai_settings", return_value=AISettings(api_key="mock-key")))
        client = self.enterContext(patch("ai_service.OpenAI"))
        create_response = client.return_value.__enter__.return_value.responses.create
        create_response.side_effect = [
            live_response("Are other devices affected?", "internet", Stage.GATHER),
            live_response("Check whether it happens near the router, too.", "internet", Stage.GUIDE),
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
            create_response.call_args.kwargs["input"][-3:],
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
        create_response.return_value = live_response("When did it start?")
        app = AppTest.from_file(str(APP_PATH)).run()
        app.toggle(key="preview_mode").set_value(True).run()
        with patch("knowledge_base.load_knowledge_base") as loader:
            app.chat_input[0].set_value("A preview-only example.").run()
        loader.assert_not_called()
        client.assert_not_called()
        self.assertEqual(app.chat_message[1].caption[0].value, "Simulated response · Placeholder")
        self.assertIn("Not performed in simulated preview.", [item.value for item in app.sidebar.caption])

        app.toggle(key="preview_mode").set_value(False).run()
        client.assert_not_called()
        app.chat_input[0].set_value("Live example.").run()
        self.assertFalse(app.exception)
        request_input = create_response.call_args.kwargs["input"]
        self.assertEqual(request_input[1:], [{"role": "user", "content": "Live example."}])
        self.assertNotIn("A preview-only example.", request_input[0]["content"])
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

    def test_detected_category_and_stage_update_and_allow_manual_correction(self):
        self.enterContext(patch("ai_service.load_ai_settings", return_value=AISettings(api_key="mock-key")))
        client = self.enterContext(patch("ai_service.OpenAI"))
        create_response = client.return_value.__enter__.return_value.responses.create
        create_response.side_effect = [
            live_response("What are you seeing when you use the PC?"),
            live_response("Watch the Wi-Fi icon when this happens.", "internet", Stage.GUIDE),
            live_response("What does the storage warning say?", "internet", Stage.GATHER),
            live_response("That sounds resolved for now.", "internet", Stage.RESOLVE),
        ]
        app = AppTest.from_file(str(APP_PATH)).run()
        app.chat_input[0].set_value("My PC isn't right.").run()
        self.assertIn("None selected", [item.value for item in app.sidebar.markdown])
        self.assertIn("**Problem identification**", [item.value for item in app.sidebar.markdown])

        app.chat_input[0].set_value("Wi-Fi drops when I make video calls.").run()
        self.assertFalse(app.exception)
        self.assertIn("Internet & Wi-Fi", [item.value for item in app.sidebar.markdown])
        self.assertIn("**Guided troubleshooting**", [item.value for item in app.sidebar.markdown])

        app.button(key="category-storage").click().run()
        self.assertIn("Storage", [item.value for item in app.sidebar.markdown])
        self.assertEqual(create_response.call_count, 2)
        app.chat_input[0].set_value("I want to investigate the storage warning first.").run()
        self.assertIn("Manually selected category: Storage.", create_response.call_args.kwargs["instructions"])
        self.assertIn("Storage", [item.value for item in app.sidebar.markdown])
        self.assertIn("**Gathering diagnostic information**", [item.value for item in app.sidebar.markdown])
        app.button(key="auto-category").click().run()
        self.assertIn("Internet & Wi-Fi", [item.value for item in app.sidebar.markdown])
        self.assertEqual(create_response.call_count, 3)
        app.chat_input[0].set_value("Wi-Fi is working again.").run()
        self.assertIn("**Resolution or escalation**", [item.value for item in app.sidebar.markdown])
        self.assertIn(":blue-badge[Review outcome]", [item.value for item in app.sidebar.markdown])
        self.assertEqual(create_response.call_count, 4)

    def test_older_facts_stay_in_context_and_reset_clears_both_modes(self):
        self.enterContext(patch("ai_service.load_ai_settings", return_value=AISettings(api_key="mock-key")))
        client = self.enterContext(patch("ai_service.OpenAI"))
        create_response = client.return_value.__enter__.return_value.responses.create
        create_response.side_effect = [
            live_response(
                "Is the phone affected too?",
                "internet",
                Stage.GATHER,
                {"system_information": [ReportedFact(quote="Windows 11", replaces=None)]},
            ),
            live_response("The adapter may be involved.", "internet", Stage.EVALUATE),
            live_response("When did it start?"),
        ]
        app = AppTest.from_file(str(APP_PATH)).run()
        original = "My Windows 11 laptop loses Wi-Fi."
        app.chat_input[0].set_value(original).run()
        self.assertIn("• Windows 11", [item.value for item in app.sidebar.text])
        app.session_state["messages"].extend(
            {"role": "user", "text": f"Later note {i}.", "mode": "live"} for i in range(11)
        )

        app.chat_input[0].set_value("Only the laptop loses connection.").run()
        self.assertFalse(app.exception)
        request = create_response.call_args.kwargs["input"]
        self.assertNotIn(original, [item["content"] for item in request[1:]])
        retained = json.loads(request[0]["content"].split("\n", 1)[1])
        self.assertEqual(retained["original_problem"], original)
        self.assertEqual(retained["facts"], {"system_information": ["Windows 11"]})
        self.assertIn("• Windows 11", [item.value for item in app.sidebar.text])

        app.toggle(key="preview_mode").set_value(True).run()
        app.chat_input[0].set_value("My preview storage is full.").run()
        app.button(key="new-session").click().run()
        self.assertFalse(app.chat_message)
        self.assertIn("**Problem identification**", [item.value for item in app.sidebar.markdown])
        self.assertIn("None selected", [item.value for item in app.sidebar.markdown])

        app.toggle(key="preview_mode").set_value(False).run()
        app.chat_input[0].set_value("My PC has an issue.").run()
        request = create_response.call_args.kwargs["input"]
        retained = json.loads(request[0]["content"].split("\n", 1)[1])
        self.assertEqual(retained["original_problem"], "My PC has an issue.")
        self.assertEqual(retained["facts"], {})
        self.assertEqual(len(request), 2)

    def test_malformed_live_reply_leaves_current_stage_and_facts_intact(self):
        self.enterContext(patch("ai_service.load_ai_settings", return_value=AISettings(api_key="mock-key")))
        client = self.enterContext(patch("ai_service.OpenAI"))
        create_response = client.return_value.__enter__.return_value.responses.create
        create_response.side_effect = [
            live_response(
                "Which drive shows the warning?",
                "storage",
                Stage.GATHER,
                {"symptoms": [ReportedFact(quote="low disk space", replaces=None)]},
            ),
            SimpleNamespace(status="completed", output_text='{"reply": "partial"}'),
        ]
        app = AppTest.from_file(str(APP_PATH)).run()
        app.chat_input[0].set_value("I see low disk space.").run()
        app.chat_input[0].set_value("The warning names C:.").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.chat_message), 3)
        self.assertIn("did not return a usable reply", app.error[0].value)
        self.assertIn("**Gathering diagnostic information**", [item.value for item in app.sidebar.markdown])
        self.assertIn("• low disk space", [item.value for item in app.sidebar.text])
        self.assertEqual(create_response.call_count, 2)

    def test_live_retrieval_sends_reference_data_and_shows_the_current_titles(self):
        self.enterContext(patch("ai_service.load_ai_settings", return_value=AISettings(api_key="mock-key")))
        client = self.enterContext(patch("ai_service.OpenAI"))
        create_response = client.return_value.__enter__.return_value.responses.create
        create_response.return_value = live_response("Watch the Wi-Fi icon during a call.", "internet", Stage.GUIDE)
        app = AppTest.from_file(str(APP_PATH)).run()
        self.assertIn("Not performed yet.", [item.value for item in app.sidebar.caption])

        problem = "My Wi-Fi disconnects during video calls."
        app.chat_input[0].set_value(problem).run()
        self.assertFalse(app.exception)
        self.assertIn("• Wi-Fi drops during calls or streaming", [item.value for item in app.sidebar.text])
        request = create_response.call_args.kwargs
        self.assertTrue(request["text"]["format"]["strict"])
        self.assertEqual(request["input"][-1], {"role": "user", "content": problem})
        reference_input = request["input"][1]
        self.assertEqual(reference_input["role"], "user")
        self.assertIn("reference data only", reference_input["content"])
        references = json.loads(reference_input["content"].split("\n", 1)[1])
        self.assertEqual(references[0]["id"], "wifi-drops")
        self.assertLessEqual(len(references), 3)
        self.assertTrue(references[0]["diagnostic_steps"] and references[0]["safety"])
        self.assertNotIn(references[0]["title"], request["instructions"])
        self.assertNotIn("source_url", references[0])
        create_response.assert_called_once()

        app.run()
        create_response.assert_called_once()
        app.button(key="new-session").click().run()
        self.assertIn("Not performed yet.", [item.value for item in app.sidebar.caption])
        self.assertNotIn("• Wi-Fi drops during calls or streaming", [item.value for item in app.sidebar.text])

    def test_no_match_and_unavailable_corpus_allow_a_regular_live_reply(self):
        self.enterContext(patch("ai_service.load_ai_settings", return_value=AISettings(api_key="mock-key")))
        client = self.enterContext(patch("ai_service.OpenAI"))
        create_response = client.return_value.__enter__.return_value.responses.create
        create_response.return_value = live_response("Can you describe the symptom?")
        failing_loader = patch("knowledge_base.load_knowledge_base", side_effect=KnowledgeBaseError)
        app = AppTest.from_file(str(APP_PATH)).run()

        app.chat_input[0].set_value("My PC is acting up.").run()
        self.assertIn("Search completed. No relevant entries found.", [item.value for item in app.sidebar.caption])
        self.assertEqual(len(app.chat_message), 2)
        self.assertEqual(len(create_response.call_args.kwargs["input"]), 2)

        with failing_loader:
            app.chat_input[0].set_value("My Wi-Fi disconnects during video calls.").run()
        self.assertFalse(app.exception)
        self.assertIn(
            "Local knowledge base unavailable. Live chat can continue with general guidance.",
            [item.value for item in app.sidebar.caption],
        )
        self.assertEqual(len(app.chat_message), 4)
        self.assertEqual(len(create_response.call_args.kwargs["input"]), 4)
        self.assertEqual(create_response.call_count, 2)


class MilestoneSixAppTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("ai_service.load_ai_settings", return_value=AISettings(api_key="mock-key")))
        client = self.enterContext(patch("ai_service.OpenAI"))
        self.create_response = client.return_value.__enter__.return_value.responses.create
        self.app = AppTest.from_file(str(APP_PATH)).run()

    def submit(self, text):
        self.app.chat_input[0].set_value(text).run()
        self.assertFalse(self.app.exception)

    def assert_category(self, label):
        self.assertIn(label, [item.value for item in self.app.sidebar.markdown])

    def test_general_troubleshooting_is_distinct_from_ambiguity(self):
        self.create_response.side_effect = [
            live_response("What are you seeing?"),
            live_response("How is the printer connected?", "general", Stage.GATHER),
        ]
        self.submit("My PC has a problem.")
        self.assert_category("None selected")
        self.assertIn("What are you seeing?", self.app.chat_message[1].text[0].value)
        self.assertIn("**Problem identification**", [item.value for item in self.app.sidebar.markdown])
        self.submit("The USB printer refuses to print.")
        self.assert_category("General Troubleshooting")
        self.assertIn("**Gathering diagnostic information**", [item.value for item in self.app.sidebar.markdown])
        self.assertIn("Search completed. No relevant entries found.", [item.value for item in self.app.sidebar.caption])
        self.assertEqual(len([button for button in self.app.button if button.key.startswith("category-")]), 5)
        self.assertEqual(self.create_response.call_count, 2)

    def test_windows_update_reclassifies_after_free_space_and_restarts_are_reported(self):
        original = "Windows Update fails with error 0x80070002 and will not install."
        update = "I have 250 GB of free storage available and have restarted several times."
        # Simulate the earlier model classification to check that it cannot anchor the next turn.
        self.create_response.side_effect = [
            live_response("What does Windows show for free space?", "storage", Stage.GATHER),
            live_response(
                "Which update failed in Windows Update history?",
                "general",
                Stage.EVALUATE,
                {"reported_results": [ReportedFact(quote="250 GB of free storage", replaces=None)]},
                citation_ids=["update-space"],
            ),
        ]
        self.submit(original)
        self.assert_category("Storage")
        self.assertFalse(self.app.session_state.last_retrieval.documents)
        self.submit(update)
        self.assert_category("General Troubleshooting")
        self.assertFalse(self.app.session_state.last_retrieval.documents)
        self.assertFalse(self.app.get("link_button"))
        request = self.create_response.call_args.kwargs
        self.assertEqual(request["input"][-1]["content"], update)
        self.assertIn(original, request["input"][0]["content"])
        self.assertFalse(any("Retrieved troubleshooting references" in item["content"] for item in request["input"]))
        self.assertEqual(self.create_response.call_count, 2)

    def test_manual_override_stays_selected_during_automatic_reclassification(self):
        self.create_response.side_effect = [
            live_response("When does the sound stop?", "audio", Stage.GATHER),
            live_response("Which update failed?", "general", Stage.GATHER),
        ]
        self.submit("My headphones have no sound.")
        self.app.button(key="category-audio").click().run()
        self.submit("The sound is back. What I want to look at now is a failed Windows update.")
        self.assert_category("Audio & Drivers")
        self.assertIn("Auto-detected: General Troubleshooting", [item.value for item in self.app.sidebar.caption])
        self.assertIn("Manually selected category: Audio & Drivers.", self.create_response.call_args.kwargs["instructions"])
        self.app.button(key="auto-category").click().run()
        self.assert_category("General Troubleshooting")
        self.assertEqual(self.create_response.call_count, 2)

    def test_only_valid_citations_render_and_they_stay_with_their_reply(self):
        self.create_response.side_effect = [
            live_response(
                "Windows may be using another output.",
                "audio",
                Stage.GUIDE,
                citation_ids=["fake", "bluetooth-no-sound", "wifi-drops", "bluetooth-no-sound"],
                step=SOUND_STEP,
            ),
            live_response("What does the printer screen show?", "general", Stage.GATHER, citation_ids=["bluetooth-no-sound"]),
        ]
        self.submit("My Bluetooth headphones say connected but I hear no sound.")
        expected_source = next(doc for doc in load_knowledge_base().documents if doc.id == "bluetooth-no-sound")
        links = self.app.chat_message[1].get("link_button")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].proto.url, expected_source.source_url)
        self.assertEqual(links[0].proto.label, f"[1] {expected_source.source_title} · {expected_source.source_organization}")
        self.assertIn("Sources cited for this reply", [item.value for item in self.app.chat_message[1].caption])
        for text in (SOUND_STEP.title, SOUND_STEP.instructions, SOUND_STEP.expected, SOUND_STEP.safety):
            self.assertIn(text, [item.value for item in self.app.chat_message[1].text])

        self.submit("The printer keeps jamming.")
        self.assertEqual(len(self.app.chat_message[1].get("link_button")), 1)
        self.assertEqual(len(self.app.get("link_button")), 1)
        self.assertFalse(self.app.chat_message[3].get("link_button"))
        self.assertTrue(any("General AI guidance" in item.value for item in self.app.chat_message[3].caption))
        self.assertIsNone(self.app.session_state.active_step)
        self.app.button(key="new-session").click().run()
        self.assertFalse(self.app.get("link_button"))
        self.assertIsNone(self.app.session_state.last_retrieval)

    def test_outcome_controls_record_user_feedback_and_only_send_once_per_step(self):
        for outcome in StepOutcome:
            with self.subTest(outcome=outcome):
                self.app.button(key="new-session").click().run()
                self.create_response.reset_mock()
                next_step = SOUND_STEP.model_copy(update={"title": "Check the app volume"})
                self.create_response.side_effect = [
                    live_response("Let's check the output.", "audio", Stage.GUIDE, step=SOUND_STEP),
                    live_response("Thanks for your result.", "audio", Stage.GUIDE, step=next_step),
                ]
                self.submit("My headphones have no sound.")
                self.assertIn("Current step", [item.value for item in self.app.sidebar.caption])
                self.app.text_input(key="step-details-1").set_value("The output list was visible.")
                self.app.button(key=f"step-feedback-1-{outcome.name}").click().run()
                self.assertFalse(self.app.exception)
                self.assertEqual(self.create_response.call_count, 2)
                history = self.app.session_state.diagnostics["live"].step_history
                self.assertEqual(len(history), 1)
                self.assertEqual(history[0].title, SOUND_STEP.title)
                self.assertEqual(history[0].outcome, outcome)
                self.assertEqual(history[0].details, "The output list was visible.")
                self.assertIn(
                    f"Reported outcome · {outcome.value}",
                    [item.value for item in self.app.chat_message[1].caption],
                )
                request = self.create_response.call_args.kwargs["input"]
                notes = json.loads(request[0]["content"].split("\n", 1)[1])
                self.assertEqual(notes["step_history"][0]["outcome"], outcome.value)
                self.assertIn("The output list was visible.", request[-1]["content"])
                # AppTest removes stale widgets. Invoke their callback against the current state.
                with patch("app.st.session_state", self.app.session_state):
                    submit_step_feedback(1, outcome)
                self.app.run()
                self.assertFalse(self.app.exception)
                self.assertEqual(self.create_response.call_count, 2)
                if outcome == StepOutcome.SOLVED:
                    self.assertIsNone(self.app.session_state.active_step)
                    self.assertEqual(self.app.session_state.diagnostics["live"].stage, Stage.RESOLVE)
                    self.assertFalse(self.app.text_input)
                else:
                    self.assertEqual(self.app.session_state.active_step, 3)
                    self.assertEqual(self.app.text_input[0].key, "step-details-3")

        self.app.button(key="new-session").click().run()
        self.assertFalse(self.app.chat_message)
        self.assertIsNone(self.app.session_state.active_step)
        self.assertEqual(self.app.session_state.diagnostics["live"].step_history, [])

    def test_preview_hides_live_controls_and_api_failure_preserves_feedback(self):
        self.create_response.side_effect = [
            live_response("Let's check the output.", "audio", Stage.GUIDE, step=SOUND_STEP),
            RuntimeError("private request error"),
        ]
        self.submit("My headphones have no sound.")
        self.app.toggle(key="preview_mode").set_value(True).run()
        self.assertFalse(self.app.text_input)
        self.submit("Windows Update error 0x80070002.")
        self.assert_category("General Troubleshooting")
        self.assertEqual(self.create_response.call_count, 1)
        self.app.toggle(key="preview_mode").set_value(False).run()
        self.app.button(key="step-feedback-1-UNABLE").click().run()
        self.assertFalse(self.app.exception)
        self.assertIn("did not return a usable reply", self.app.error[0].value)
        self.assertNotIn("private request error", self.app.error[0].value)
        self.assertIsNone(self.app.session_state.active_step)
        feedback = self.app.session_state.diagnostics["live"].step_history
        self.assertEqual([item.outcome for item in feedback], [StepOutcome.UNABLE])
        self.app.run()
        self.assertEqual(self.create_response.call_count, 2)
