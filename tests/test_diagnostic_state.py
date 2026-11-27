"""Verify local preview classification and the rules for retaining diagnostic notes."""

import unittest

from diagnostic_state import DiagnosticMemory, DiagnosticReply, FACT_LABELS, FactUpdates, PossibleCause, ReportedFact, Stage
from troubleshooting import detect_preview_category


class DiagnosticMemoryTests(unittest.TestCase):
    def test_preview_recognizes_the_five_categories_and_leaves_ambiguity_open(self):
        examples = {
            "Wi-Fi drops in the middle of calls.": "internet",
            "The PC is slow at startup.": "performance",
            "I am running out of disk space.": "storage",
            "The speakers have no sound.": "audio",
            "The laptop overheats during gaming.": "gaming",
            "My PC has a problem.": None,
            "The Wi-Fi and speakers stopped working.": None,
        }
        for problem, category in examples.items():
            with self.subTest(problem=problem):
                self.assertEqual(detect_preview_category(problem), category)

    def test_only_user_supported_details_are_recorded_and_omissions_keep_old_facts(self):
        original = "On Windows 11 the sound stopped after an update. I rebooted but still have no sound."
        memory = DiagnosticMemory(original_problem=original)
        update = DiagnosticReply(
            reply="The update might be related. Which output device appears in Settings?",
            detected_category="audio",
            stage=Stage.EVALUATE,
            new_facts=FactUpdates(
                system_information=[ReportedFact(quote="Windows 11", replaces=None)],
                symptoms=[ReportedFact(quote="the sound stopped", replaces=None)],
                recent_changes=[ReportedFact(quote="after an update", replaces=None)],
                attempted_steps=[
                    ReportedFact(quote="I rebooted", replaces=None),
                    ReportedFact(quote="I reinstalled the audio driver", replaces=None),
                ],
                reported_results=[ReportedFact(quote="still have no sound", replaces=None)],
            ),
            possible_causes=[
                PossibleCause(hypothesis="The update might be related.", evidence="after an update"),
                PossibleCause(hypothesis="A damaged cable.", evidence="The cable snapped."),
            ],
            unresolved_questions=["Which output device appears in Settings?"],
        )
        memory.apply(update, [original])
        self.assertEqual(memory.original_problem, original)
        self.assertEqual(memory.facts, {
            "system_information": ["Windows 11"],
            "symptoms": ["the sound stopped"],
            "recent_changes": ["after an update"],
            "attempted_steps": ["I rebooted"],
            "reported_results": ["still have no sound"],
        })
        self.assertEqual(memory.possible_causes, ["The update might be related."])
        self.assertEqual(memory.unresolved_questions, ["Which output device appears in Settings?"])

        memory.apply(update.model_copy(update={
            "stage": Stage.GATHER,
            "new_facts": FactUpdates(**{kind: [] for kind in FACT_LABELS}),
            "possible_causes": [],
            "unresolved_questions": [],
        }), [])
        self.assertEqual(memory.stage, Stage.GATHER)
        self.assertEqual(memory.facts["system_information"], ["Windows 11"])
        self.assertEqual(memory.unresolved_questions, [])

    def test_an_explicit_supported_correction_can_replace_an_older_note(self):
        memory = DiagnosticMemory(facts={"system_information": ["Windows 11"]})
        update = DiagnosticReply(
            reply="Thanks for clarifying the version.",
            detected_category=None,
            stage=Stage.IDENTIFY,
            new_facts=FactUpdates(
                system_information=[
                    ReportedFact(quote="Windows 10", replaces="Windows 11"),
                    ReportedFact(quote="Windows 8", replaces="Windows 10"),
                ],
                symptoms=[],
                recent_changes=[],
                attempted_steps=[],
                reported_results=[],
            ),
            possible_causes=[],
            unresolved_questions=[],
        )
        memory.apply(update, ["Correction: this is Windows 10."])
        self.assertEqual(memory.facts, {"system_information": ["Windows 10"]})
