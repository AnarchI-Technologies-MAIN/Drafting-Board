from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


WORKERS = Path(__file__).resolve().parents[1]
if str(WORKERS) not in sys.path:
    sys.path.insert(0, str(WORKERS))

from blog_loop.core import canonical_digest, seal_receipt, validate_receipt
from blog_loop.editorial import (
    affiliate_eligible,
    build_affiliate_candidate,
    build_affiliate_program_observation,
    build_article_input,
    build_evidence_receipt,
    build_keyword_receipt,
    build_niche_assessment,
    build_seo_plan,
    build_seo_validation,
    build_topic_packet,
    derive_freshness,
    rank_affiliate_candidates,
    validate_affiliate_candidate,
    validate_affiliate_program_observation,
    validate_evidence_receipt,
    validate_keyword_receipt,
    validate_topic_packet,
)
from blog_loop.market_visual import (
    analyze_image_opportunity,
    build_before_after_comparison,
    build_image_candidate,
    build_image_plan,
    build_image_request,
    build_publication_execution_receipt,
    build_telemetry_receipt,
    validate_before_after_comparison,
    validate_image_candidate,
    validate_image_opportunity,
    validate_image_plan,
    validate_image_request,
    validate_publication_receipt,
    validate_telemetry_receipt,
)


NOW = "2026-08-28T12:00:00Z"
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64


class Fixtures:
    @staticmethod
    def keyword(state="LIVE_ACQUIRED_KEYWORD"):
        return build_keyword_receipt(
            keyword="python idempotency patterns", keyword_state=state,
            provider="fixture-search", acquisition_method="PROVIDER_EXPORT" if state == "LIVE_ACQUIRED_KEYWORD" else "DERIVATION",
            retrieval_timestamp=NOW, market="US", locale="en-US",
            raw_source_reference="fixture://keyword/1" if state == "LIVE_ACQUIRED_KEYWORD" else None,
            provider_metrics={}, query_context="backend reliability",
        )

    @staticmethod
    def niche(keyword=None, disposition="IN_NICHE"):
        return build_niche_assessment(
            keyword or Fixtures.keyword(), niche_definition_id="engineering-systems",
            niche_definition_version="2026-08-28", disposition=disposition,
            rationale="Directly addresses deterministic backend reliability.",
        )

    @staticmethod
    def evidence(keyword=None, *, topic="ALIGNED", niche="IN_NICHE", published="2026-08-20T12:00:00Z"):
        keyword = keyword or Fixtures.keyword()
        return build_evidence_receipt(
            keyword_receipt_digest=keyword["receipt_digest"], query_digest=DIGEST_B,
            source_url="https://docs.example.test/idempotency", source_title="Idempotency",
            source_identity="docs.example.test:idempotency", retrieved_at=NOW,
            published_at=published, updated_at=None, content_digest=DIGEST_C,
            topic_alignment=topic, niche_alignment=niche,
            freshness_requirement={"max_age_days": 30}, source_quality={"type": "primary-documentation"},
            claim_usefulness="BACKGROUND_CANDIDATE",
        )

    @staticmethod
    def topic(current=True):
        keyword = Fixtures.keyword()
        niche = Fixtures.niche(keyword)
        evidence = Fixtures.evidence(keyword, published="2026-08-20T12:00:00Z" if current else "2020-01-01T00:00:00Z")
        topic = build_topic_packet(
            niche_assessment=niche, keyword_receipt=keyword, search_intent="informational",
            supporting_queries=["idempotency key replay"], evidence_receipts=[evidence],
            freshness_requirement="CURRENT_REQUIRED" if current else "ANY",
            article_opportunity="Explain a bounded implementation pattern",
            proposed_subject="Idempotency without accidental authority", known_evidence_gaps=[],
            affiliate_hints=[], seo_inputs={"query": keyword["keyword"]},
        )
        return topic, keyword, niche, evidence

    @staticmethod
    def telemetry(metrics=None, images=None):
        return build_telemetry_receipt(
            post_id="post-1", publication_receipt_digest=DIGEST_A, topic_id="topic-1",
            niche_id="engineering-systems", primary_keyword="python idempotency patterns",
            published_at="2026-08-01T12:00:00Z",
            observation_window={"start": "2026-08-01T12:00:00Z", "end": "2026-08-28T11:00:00Z"},
            provider="fixture-analytics", property_id="property-1", traffic_source="organic",
            metrics=metrics if metrics is not None else {"impressions": 1000, "clicks": 40, "scroll_depth": 0.2, "bounce_rate": 0.8},
            image_inventory=images or [], last_observed_at="2026-08-28T11:00:00Z", retrieved_at=NOW,
        )


class IdentityTests(unittest.TestCase):
    def test_canonical_identity_is_key_order_independent(self):
        self.assertEqual(canonical_digest({"b": 2, "a": 1}), canonical_digest({"a": 1, "b": 2}))

    def test_payload_mutation_invalidates_receipt(self):
        receipt = seal_receipt({"schema": "fixture", "value": 1})
        receipt["value"] = 2
        self.assertIn("does not match", " ".join(validate_receipt(receipt)))

    def test_replay_is_deterministic(self):
        first = Fixtures.keyword()
        second = Fixtures.keyword()
        self.assertEqual(first, second)


class DemandAndEvidenceTests(unittest.TestCase):
    def test_live_keyword_binds_provider_and_timestamp(self):
        receipt = Fixtures.keyword()
        self.assertEqual(receipt["provider"], "fixture-search")
        self.assertFalse(validate_keyword_receipt(receipt))

    def test_generated_keyword_cannot_claim_live(self):
        receipt = Fixtures.keyword()
        receipt["acquisition_method"] = "MODEL"
        receipt["receipt_digest"] = canonical_digest({k: v for k, v in receipt.items() if k != "receipt_digest"})
        self.assertTrue(validate_keyword_receipt(receipt))

    def test_live_keyword_requires_raw_observation(self):
        receipt = Fixtures.keyword()
        receipt["raw_source_reference"] = None
        receipt["receipt_digest"] = canonical_digest({k: v for k, v in receipt.items() if k != "receipt_digest"})
        self.assertTrue(validate_keyword_receipt(receipt))

    def test_missing_timestamp_fails_closed(self):
        receipt = Fixtures.keyword()
        receipt["retrieval_timestamp"] = ""
        receipt["receipt_digest"] = canonical_digest({k: v for k, v in receipt.items() if k != "receipt_digest"})
        self.assertTrue(validate_keyword_receipt(receipt))

    def test_fresh_retrieval_does_not_make_unknown_source_current(self):
        self.assertEqual(derive_freshness(retrieved_at=NOW, published_at=None, updated_at=None,
                                         freshness_requirement={"max_age_days": 30}), "UNKNOWN")

    def test_stale_evidence_is_separate_from_alignment(self):
        evidence = Fixtures.evidence(published="2020-01-01T00:00:00Z")
        self.assertEqual(evidence["freshness_state"], "STALE")
        self.assertEqual(evidence["topic_alignment"], "ALIGNED")

    def test_freshness_is_recomputed_not_trusted(self):
        evidence = Fixtures.evidence()
        evidence["freshness_state"] = "STALE"
        evidence["evidence_receipt_digest"] = canonical_digest({k: v for k, v in evidence.items() if k != "evidence_receipt_digest"})
        self.assertTrue(validate_evidence_receipt(evidence))

    def test_topic_rejects_niche_drift(self):
        topic, keyword, niche, evidence = Fixtures.topic()
        drifted = copy.deepcopy(evidence)
        drifted["niche_alignment"] = "ADJACENT"
        drifted["evidence_receipt_digest"] = canonical_digest({k: v for k, v in drifted.items() if k != "evidence_receipt_digest"})
        self.assertTrue(validate_topic_packet(topic, niche_assessment=niche, keyword_receipt=keyword, evidence_receipts=[drifted]))

    def test_topic_rejects_stale_when_current_required(self):
        keyword = Fixtures.keyword()
        niche = Fixtures.niche(keyword)
        stale = Fixtures.evidence(keyword, published="2020-01-01T00:00:00Z")
        base, _, _, _ = Fixtures.topic()
        self.assertTrue(validate_topic_packet(base, niche_assessment=niche, keyword_receipt=keyword, evidence_receipts=[stale]))

    def test_article_input_carries_no_authority(self):
        topic, *_ = Fixtures.topic()
        result = build_article_input(topic, evidence_packet_digests=[DIGEST_A], seo_plan_digest=None,
                                     affiliate_candidate_digests=[], editorial_constraints=[], brand_constraints=[])
        self.assertEqual(result["output_state"], "ARTICLE_CANDIDATE_ONLY")
        self.assertEqual(result["publication_authority"], "NONE")


class AffiliateAndSeoTests(unittest.TestCase):
    def affiliate(self, article="RELEVANT", destination="VALID"):
        return build_affiliate_candidate(
            product_id="product-1", article_digest=DIGEST_A, niche_disposition="IN_NICHE",
            article_disposition=article, purchase_intent_alignment="ALIGNED",
            availability_state="AVAILABLE", destination="https://vendor.example.test/product",
            destination_validity=destination, price_state="UNAVAILABLE", observed_price=None,
            retrieval_timestamp=NOW, affiliate_source="fixture-affiliate", product_identity="vendor:product-1",
        )

    def test_niche_relevance_without_article_relevance_is_insufficient(self):
        self.assertFalse(affiliate_eligible(self.affiliate(article="IRRELEVANT")))

    def test_invalid_destination_is_ineligible(self):
        self.assertFalse(affiliate_eligible(self.affiliate(destination="INVALID")))

    def test_unobserved_price_cannot_be_fabricated(self):
        value = self.affiliate()
        value["observed_price"] = 999
        value["candidate_digest"] = canonical_digest({k: v for k, v in value.items() if k != "candidate_digest"})
        self.assertTrue(validate_affiliate_candidate(value))

    def test_affiliate_candidate_never_has_cta_authority(self):
        value = self.affiliate()
        self.assertEqual(value["cta_authority"], "NONE")

    def test_program_metrics_remain_unknown_when_not_disclosed(self):
        candidate = self.affiliate()
        observed = build_affiliate_program_observation(
            candidate_digest=candidate["candidate_digest"], provider="fixture-network",
            program_url="https://network.example.test/program/1", retrieved_at=NOW,
            commission_model="RECURRING_PERCENT", commission_value=20,
            cookie_duration_days=30, epc=None, conversion_rate=None, refund_rate=None,
            payout_terms="monthly", raw_terms_digest=DIGEST_A,
        )
        ranked = rank_affiliate_candidates([(candidate, observed)])
        self.assertEqual(ranked[0]["net_epc_state"], "UNKNOWN")
        self.assertIsNone(ranked[0]["net_epc"])

    def test_observed_net_return_ranks_only_eligible_products(self):
        eligible = self.affiliate()
        irrelevant = self.affiliate(article="IRRELEVANT")
        eligible_observation = build_affiliate_program_observation(
            candidate_digest=eligible["candidate_digest"], provider="fixture-network",
            program_url="https://network.example.test/program/1", retrieved_at=NOW,
            commission_model="FLAT", commission_value=10, cookie_duration_days=30,
            epc=2.0, conversion_rate=0.1, refund_rate=0.25, payout_terms="monthly",
            raw_terms_digest=DIGEST_A,
        )
        irrelevant_observation = build_affiliate_program_observation(
            candidate_digest=irrelevant["candidate_digest"], provider="fixture-network",
            program_url="https://network.example.test/program/2", retrieved_at=NOW,
            commission_model="FLAT", commission_value=100, cookie_duration_days=30,
            epc=20.0, conversion_rate=0.5, refund_rate=0.0, payout_terms="monthly",
            raw_terms_digest=DIGEST_B,
        )
        ranked = rank_affiliate_candidates([(irrelevant, irrelevant_observation), (eligible, eligible_observation)])
        self.assertEqual(ranked[0]["candidate_digest"], eligible["candidate_digest"])
        self.assertEqual(ranked[0]["net_epc"], 1.5)
        self.assertEqual(ranked[0]["cta_authority"], "NONE")

    def test_invalid_disclosed_ratio_fails_closed(self):
        candidate = self.affiliate()
        with self.assertRaises(ValueError):
            build_affiliate_program_observation(
                candidate_digest=candidate["candidate_digest"], provider="fixture-network",
                program_url="https://network.example.test/program/1", retrieved_at=NOW,
                commission_model="FLAT", commission_value=10, cookie_duration_days=30,
                epc=2.0, conversion_rate=1.5, refund_rate=0.0, payout_terms="monthly",
                raw_terms_digest=DIGEST_A,
            )

    def test_seo_plan_has_no_evidence_authority(self):
        result = build_seo_plan(
            topic_packet_digest=DIGEST_A, primary_query="python idempotency", supporting_queries=[],
            search_intent="informational", topic_entities=["idempotency"], question_coverage=[],
            content_gaps=[], title_direction="Bounded implementation", heading_structure=["H1", "H2"],
            internal_link_opportunities=[], intent_class="INFORMATIONAL",
        )
        self.assertEqual(result["evidence_authority"], "NONE")
        self.assertEqual(result["publication_authority"], "NONE")

    def test_seo_validation_rejects_keyword_density_authority_field(self):
        with self.assertRaises(ValueError):
            build_seo_validation(seo_plan_digest=DIGEST_A, article_digest=DIGEST_B,
                                 checks={"keyword_density_authority": "PASS"})


class PublicationAndTelemetryTests(unittest.TestCase):
    def test_publication_receipt_requires_real_url_and_authority_lineage(self):
        result = build_publication_execution_receipt(
            article_digest=DIGEST_A, claim_review_digest=DIGEST_B, human_approval_digest=DIGEST_C,
            publication_authority_digest="d" * 64, adapter_id="fixture-adapter", executed_at=NOW,
            public_url="https://blog.example.test/post", published_bytes_digest="e" * 64,
            idempotency_key="post:1", replay_disposition="FIRST_EXECUTION",
        )
        self.assertFalse(validate_publication_receipt(result))

    def test_fake_publication_url_fails(self):
        result = {
            "article_digest": DIGEST_A, "claim_review_digest": DIGEST_B,
            "human_approval_digest": DIGEST_C, "publication_authority_digest": "d" * 64,
            "published_bytes_digest": "e" * 64, "executed_at": NOW, "public_url": "not-a-url",
            "adapter_id": "fixture", "idempotency_key": "key", "replay_disposition": "FIRST_EXECUTION",
        }
        self.assertTrue(validate_publication_receipt(result))

    def test_telemetry_cannot_create_publication_authority(self):
        value = Fixtures.telemetry()
        self.assertEqual(value["publication_authority"], "NONE")

    def test_unknown_provider_metric_is_rejected(self):
        value = Fixtures.telemetry()
        value["metrics"]["invented_score"] = 99
        value["telemetry_receipt_digest"] = canonical_digest({k: v for k, v in value.items() if k != "telemetry_receipt_digest"})
        self.assertTrue(validate_telemetry_receipt(value))

    def test_telemetry_chain_is_append_only_compatible(self):
        first = Fixtures.telemetry()
        second = build_telemetry_receipt(
            post_id=first["post_id"], publication_receipt_digest=DIGEST_A, topic_id="topic-1",
            niche_id="engineering-systems", primary_keyword="python idempotency patterns",
            published_at="2026-08-01T12:00:00Z",
            observation_window={"start": "2026-08-01T12:00:00Z", "end": "2026-08-28T12:00:00Z"},
            provider="fixture-analytics", property_id="property-1", traffic_source="organic",
            metrics={"impressions": 1100}, image_inventory=[], last_observed_at=NOW, retrieved_at=NOW,
            previous_receipt_digest=first["telemetry_receipt_digest"],
        )
        self.assertEqual(second["previous_receipt_digest"], first["telemetry_receipt_digest"])
        self.assertNotEqual(second["telemetry_receipt_digest"], first["telemetry_receipt_digest"])


class VisualLoopTests(unittest.TestCase):
    def request(self, mode="PULL_MODE"):
        return build_image_request(
            mode=mode, post_id="post-1", section_id=None, topic_id="topic-1", niche_id="engineering",
            image_role="HERO", target_intent="Orient the reader", reader_problem="Dense abstract subject",
            seo_context={}, brand_profile={"profile": "anarchi-v1"},
            truth_constraints=["Do not introduce factual claims"], affiliate_constraints=[],
            evidence_packet_references=[DIGEST_A], market_opportunity_references=[],
            request_reason="Editorial pull request for a conceptual hero.",
        )

    def test_missing_image_does_not_force_generation(self):
        opportunity = analyze_image_opportunity(Fixtures.telemetry(), article_digest=DIGEST_B)
        self.assertIn(opportunity["opportunity_state"], {"POSSIBLE_OPPORTUNITY", "STRONG_OPPORTUNITY"})
        self.assertEqual(opportunity["approval"], "NONE")
        self.assertEqual(opportunity["recommendation_only"], True)

    def test_insufficient_market_data_is_not_opportunity_claim(self):
        opportunity = analyze_image_opportunity(Fixtures.telemetry(metrics={"impressions": 10}), article_digest=DIGEST_B)
        self.assertEqual(opportunity["opportunity_state"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(validate_image_opportunity(opportunity))

    def test_push_request_does_not_authorize_generation(self):
        request = self.request(mode="PUSH_MODE")
        self.assertEqual(request["generation_authority"], "NONE")
        self.assertEqual(request["publication_authority"], "NONE")

    def test_request_tampering_fails_identity(self):
        request = self.request()
        request["request_reason"] = "changed"
        self.assertTrue(validate_image_request(request))

    def test_plan_cannot_create_execution_or_factual_authority(self):
        plan = build_image_plan(
            self.request(), required_semantic_elements=["abstract idempotency key"],
            forbidden_semantic_elements=["unverified performance numbers"],
            composition_guidance=["clear focal point"], text_on_image_policy="NO_TEXT",
            product_restrictions=[], factual_restrictions=["No claim expansion"],
            aspect_roles=["16:9"], generation_strategy="LOCAL_CANDIDATE_ONLY",
        )
        self.assertEqual(plan["execution_authority"], "NONE")
        self.assertEqual(plan["factual_authority"], "NONE")
        self.assertFalse(validate_image_plan(plan))

    def test_materialized_pixels_do_not_create_approval(self):
        candidate = build_image_candidate(
            request_digest=DIGEST_A, plan_digest=DIGEST_B, provider_id="fixture-materializer",
            model_id="fixture-model", runtime_id="fixture-runtime", generation_configuration={"seed": 1},
            asset_reference="candidate://asset/1", asset_sha256=DIGEST_C,
            dimensions={"width": 1200, "height": 630}, materialization_state="MATERIALIZED_CANDIDATE",
        )
        self.assertEqual(candidate["approval"], "NONE")
        self.assertEqual(candidate["publication_authority"], "NONE")
        self.assertFalse(validate_image_candidate(candidate))

    def test_before_after_never_claims_causality(self):
        comparison = build_before_after_comparison(
            post_id="post-1", url_identity="https://blog.example.test/post",
            image_deployment_receipt=DIGEST_A, pre_image_telemetry=DIGEST_B,
            post_image_telemetry=DIGEST_C,
            comparison_window={"pre": "PRE_IMAGE_WINDOW", "post": "POST_IMAGE_WINDOW"},
            traffic_source="organic", observed_changes={"ctr_delta": 0.01}, confounder_notes=["seasonality unknown"],
        )
        self.assertEqual(comparison["causality"], "NOT_CAUSALLY_ESTABLISHED")
        self.assertFalse(validate_before_after_comparison(comparison))


if __name__ == "__main__":
    unittest.main()
    rank_affiliate_candidates,
