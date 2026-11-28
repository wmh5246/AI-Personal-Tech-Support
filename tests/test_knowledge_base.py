"""Verify corpus validation and local retrieval without API or internet access."""

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

from knowledge_base import DATA_PATH, KnowledgeBaseError, load_knowledge_base, retrieve_references


class KnowledgeBaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = load_knowledge_base()

    def test_bundled_documents_initialize_with_unique_ids_and_source_metadata(self):
        documents = self.index.documents
        self.assertEqual(len(documents), 25)
        self.assertEqual(len({doc.id for doc in documents}), len(documents))
        self.assertEqual(Counter(doc.category for doc in documents), {
            "internet": 5, "performance": 5, "storage": 5, "audio": 5, "gaming": 5,
        })
        domains = {"support.microsoft.com", "www.dell.com", "www.intel.com", "www.amd.com"}
        self.assertEqual({urlparse(doc.source_url).hostname for doc in documents}, domains)
        self.assertEqual(len({doc.source_url for doc in documents}), 15)
        for doc in documents:
            self.assertTrue(doc.source_title and doc.possible_causes and doc.diagnostic_steps and doc.safety)

    def test_top_result_matches_specific_symptoms_in_each_category(self):
        examples = {
            "My Wi-Fi disconnects during video calls.": "wifi-drops",
            "The PC is slow at startup.": "slow-startup",
            "My C: drive is almost full and Windows shows a low disk space warning.": "c-drive-low",
            "My Bluetooth headphones say connected but I hear no sound.": "bluetooth-no-sound",
            "My laptop overheats and shuts down unexpectedly while gaming.": "heat-shutdown",
            "Windows Update says it needs more space.": "update-space",
            "On my AMD Radeon, FPS drops and my game stutters.": "fps-stutter",
        }
        for problem, expected in examples.items():
            with self.subTest(problem=problem):
                matches = self.index.search(problem)
                self.assertTrue(matches)
                self.assertEqual(matches[0].id, expected)
                self.assertLessEqual(len(matches), 3)
                self.assertTrue(all(doc.category == matches[0].category for doc in matches))
                self.assertEqual(matches, self.index.search(problem))

    def test_ambiguous_and_unrelated_queries_abstain(self):
        for problem in (
            "My PC is acting up.",
            "Wi-Fi disconnects and my Bluetooth headphones have no sound.",
            "I have no internet and no sound.",
            "The printer keeps jamming.",
            "Explain the history of Rome.",
        ):
            with self.subTest(problem=problem):
                self.assertEqual(self.index.search(problem), ())

    def test_follow_up_can_use_retained_symptoms_but_unrelated_messages_do_not(self):
        arguments = {
            "original": "My PC has a problem.",
            "category": "internet",
            "session_context": ("My Wi-Fi disconnects during video calls.",),
        }
        self.assertEqual(self.index.search("It still happens.", **arguments)[0].id, "wifi-drops")
        self.assertEqual(self.index.search("I still want a recipe for pancakes.", **arguments), ())
        self.assertEqual(self.index.search("The printer keeps jamming.", **arguments), ())
        new_topic = self.index.search("My Bluetooth headphones connect but no sound plays.", **arguments)
        self.assertEqual(new_topic[0].id, "bluetooth-no-sound")

    def test_category_preference_alone_does_not_return_documents(self):
        self.assertEqual(self.index.search("I have a problem.", category="gaming"), ())

    def test_missing_invalid_and_duplicate_data_are_rejected(self):
        first = json.loads(DATA_PATH.read_text(encoding="utf-8"))[0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "knowledge.json"
            with self.assertRaises(KnowledgeBaseError):
                load_knowledge_base(path)
            for text in ("not json", "[]", '[{"id": "missing fields"}]', json.dumps([first, first])):
                with self.subTest(text=text[:30]):
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaises(KnowledgeBaseError):
                        load_knowledge_base(path)

    def test_retrieval_reports_unavailable_for_bad_data(self):
        with patch("knowledge_base.load_knowledge_base", side_effect=KnowledgeBaseError):
            result = retrieve_references("Wi-Fi dropped.")
        self.assertFalse(result.available)
        self.assertEqual(result.documents, ())
