import sys
import unittest

sys.path.insert(0, r"workers")

from blog_loop.corpus_contract import (
    ALLOWED_STATUS,
    CORPUS_TOPIC_SCHEMA,
    REQUIRED_FIELDS,
    EducationalTopic,
    validate_topic,
)


class TestEducationalTopicContract(unittest.TestCase):
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

    def test_canonical_schema(self):
        self.assertEqual(
            CORPUS_TOPIC_SCHEMA,
            "anarchi.blogger.educational-topic.v1",
        )

    def test_required_fields_and_statuses(self):
        self.assertEqual(len(REQUIRED_FIELDS), 14)
        self.assertEqual(len(ALLOWED_STATUS), 7)
        self.assertIn("topic_id", REQUIRED_FIELDS)
        self.assertIn("status", REQUIRED_FIELDS)
        self.assertIn("VERIFIED", ALLOWED_STATUS)

    def test_to_dict_is_canonical_and_complete(self):
        payload = self.make_topic().to_dict()
        self.assertEqual(payload["schema"], CORPUS_TOPIC_SCHEMA)
        self.assertEqual(len(payload), 19)
        self.assertEqual(payload["topic_id"], "demo-topic")
        self.assertEqual(payload["demonstrations"], [])
        self.assertEqual(payload["examples"], [])
        self.assertEqual(payload["diagrams"], [])

    def test_valid_topic_has_no_errors(self):
        self.assertEqual(validate_topic(self.make_topic().to_dict()), [])

    def test_missing_required_field_is_rejected(self):
        payload = self.make_topic().to_dict()
        del payload["title"]
        errors = validate_topic(payload)
        self.assertIn("missing required field: title", errors)

    def test_invalid_status_is_rejected(self):
        payload = self.make_topic(status="INVALID").to_dict()
        errors = validate_topic(payload)
        self.assertTrue(any("status must be one of" in error for error in errors))

    def test_empty_topic_id_is_rejected(self):
        payload = self.make_topic(topic_id="   ").to_dict()
        errors = validate_topic(payload)
        self.assertIn("topic_id must be a non-empty string", errors)

    def test_wrong_collection_types_are_rejected(self):
        payload = self.make_topic().to_dict()
        payload["evidence_required"] = {}
        payload["related_topics"] = "wrong"
        payload["provenance"] = "wrong"
        errors = validate_topic(payload)
        self.assertIn("evidence_required must be a list", errors)
        self.assertIn("related_topics must be a list", errors)
        self.assertIn("provenance must be a list", errors)


if __name__ == "__main__":
    unittest.main()
