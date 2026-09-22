import json
import tempfile
import unittest
from pathlib import Path

from blog_loop.corpus_contract import EducationalTopic
from blog_loop.corpus_store import CorpusStore, CorpusStoreError


class TestCorpusStore(unittest.TestCase):
    def make_topic(self, **overrides):
        values = {
            "topic_id": "demo-topic",
            "title": "Demo Topic",
            "domain": "testing",
            "starting_question": "What is this?",
            "barrier": "The initial barrier.",
            "evidence_required": [],
            "historical_context": "Relevant history.",
            "transformation": "The transformation.",
            "current_truth": "The current truth.",
            "lesson": "The lesson.",
            "related_topics": [],
            "status": "PLANNED",
            "provenance": [],
            "completion_boundary": "The boundary.",
            "prerequisites": [],
            "demonstrations": [],
            "examples": [],
            "diagrams": [],
        }
        values.update(overrides)
        return EducationalTopic(**values)

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            store = CorpusStore(temp)
            topic = self.make_topic()
            path = store.save_topic(topic)
            self.assertEqual(path, Path(temp) / "demo-topic.json")
            self.assertEqual(store.load_topic("demo-topic"), topic.to_dict())

    def test_save_writes_canonical_json(self):
        with tempfile.TemporaryDirectory() as temp:
            store = CorpusStore(temp)
            store.save_topic(self.make_topic())
            payload = json.loads(
                (Path(temp) / "demo-topic.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload["schema"], "anarchi.blogger.educational-topic.v1")
            self.assertEqual(payload["topic_id"], "demo-topic")

    def test_list_is_deterministically_sorted(self):
        with tempfile.TemporaryDirectory() as temp:
            store = CorpusStore(temp)
            store.save_topic(self.make_topic(topic_id="z-topic"))
            store.save_topic(self.make_topic(topic_id="a-topic"))
            self.assertEqual(store.list_topic_ids(), ["a-topic", "z-topic"])

    def test_invalid_topic_is_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as temp:
            store = CorpusStore(temp)
            with self.assertRaises(CorpusStoreError):
                store.save_topic(self.make_topic(title="   "))
            self.assertEqual(store.list_topic_ids(), [])

    def test_corrupt_stored_topic_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            store = CorpusStore(temp)
            path = Path(temp) / "demo-topic.json"
            path.write_text(json.dumps({"topic_id": "demo-topic"}), encoding="utf-8")
            with self.assertRaises(CorpusStoreError):
                store.load_topic("demo-topic")

    def test_delete_topic(self):
        with tempfile.TemporaryDirectory() as temp:
            store = CorpusStore(temp)
            store.save_topic(self.make_topic())
            store.delete_topic("demo-topic")
            self.assertEqual(store.list_topic_ids(), [])
            with self.assertRaises(FileNotFoundError):
                store.load_topic("demo-topic")

    def test_path_traversal_identifier_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            store = CorpusStore(temp)
            with self.assertRaises(CorpusStoreError):
                store.load_topic("..\\escape")


if __name__ == "__main__":
    unittest.main()

