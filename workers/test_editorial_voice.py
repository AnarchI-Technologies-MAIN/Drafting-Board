import unittest

from editorial_voice import (
    CORE_LAWS,
    HIGH_END_EDITORIAL,
    KILN_FIRE,
    VOICE_CONTRACT_VERSION,
    lint_voice,
    system_directive,
)


class EditorialVoiceTests(unittest.TestCase):
    def test_contract_has_version(self):
        self.assertEqual(
            VOICE_CONTRACT_VERSION,
            "anarchi.editorial-voice.v1",
        )

    def test_contract_requires_evidence_inference_separation(self):
        joined = " ".join(CORE_LAWS).lower()
        self.assertIn("evidence", joined)
        self.assertIn("inference", joined)

    def test_contract_forbids_strengthening_claims(self):
        joined = " ".join(CORE_LAWS).lower()
        self.assertIn("never strengthen a claim", joined)

    def test_kiln_fire_requires_pressure_on_claims(self):
        joined = " ".join(KILN_FIRE).lower()
        self.assertIn("survive pressure", joined)

    def test_kiln_fire_requires_failure_visibility(self):
        joined = " ".join(KILN_FIRE).lower()
        self.assertIn("failure", joined)

    def test_high_end_contract_is_answer_first(self):
        joined = " ".join(HIGH_END_EDITORIAL).lower()
        self.assertIn("answer-first", joined)

    def test_system_directive_contains_all_contract_layers(self):
        directive = system_directive()
        self.assertIn("CORE LAWS", directive)
        self.assertIn("KILN FIRE", directive)
        self.assertIn("EDITORIAL QUALITY", directive)

    def test_normal_personality_does_not_fail(self):
        review = lint_voice(
            "Randomly reinstalling the entire stack can turn one unknown "
            "into three. First establish which Docker endpoint the CLI is "
            "actually targeting, then prove the hypothesis."
        )
        self.assertTrue(review.passed)

    def test_fake_firsthand_testing_blocks(self):
        review = lint_voice(
            "We tested this configuration across several production systems."
        )
        self.assertFalse(review.passed)
        self.assertEqual(
            review.findings[0].code,
            "CLAIMED_FIRSTHAND_AUTHORITY",
        )

    def test_generic_ai_opener_is_detected(self):
        review = lint_voice(
            "In today's fast-paced digital world, Docker has become important."
        )
        codes = [finding.code for finding in review.findings]
        self.assertIn("GENERIC_EDITORIAL_FILLER", codes)

    def test_absolute_language_is_visible_to_reviewer(self):
        review = lint_voice(
            "This configuration always causes the daemon to fail."
        )
        codes = [finding.code for finding in review.findings]
        self.assertIn("ABSOLUTE_LANGUAGE_PRESENT", codes)

    def test_voice_contract_contains_no_publication_authority(self):
        directive = system_directive().lower()
        self.assertNotIn("publication permitted", directive)
        self.assertNotIn("publish automatically", directive)


if __name__ == "__main__":
    unittest.main()
