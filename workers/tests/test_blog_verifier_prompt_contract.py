from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

from blog_loop.atomic_review import (
    build_atomic_review_case,
)
from editorial_verifier import (
    CalibrationVerdict,
    VerificationVerdict,
)
from editorial_verifier_adapter import (
    VERIFIER_ADAPTER_VERSION,
    VerifierAdapterError,
    build_verifier_prompt,
    parse_verifier_response,
)
from workers.tests.test_blog_atomic_review_preparation import (
    ARTICLE,
    admitted_bundle,
)


ROOT = Path(__file__).resolve().parents[2]
BLOGGER_FILE = ROOT / "workers" / "llm_blogger.py"


def isolated_editorial_context():
    """
    Materialize the exact current production packets_by_type() and
    editorial_context() function bodies without importing llm_blogger.

    Any helper referenced by those bodies is resolved from the exact
    import declaration present in llm_blogger.py.
    """
    import importlib

    source = BLOGGER_FILE.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source,
        filename=str(BLOGGER_FILE),
    )

    wanted_functions = {
        "packets_by_type",
        "editorial_context",
    }

    selected = []

    for node in tree.body:
        if (
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name in wanted_functions
        ):
            selected.append(node)

    found = {
        node.name
        for node in selected
    }

    if found != wanted_functions:
        raise AssertionError(
            "could not isolate exact production functions; "
            "found="
            + repr(sorted(found))
        )

    trim_imports = []

    for node in tree.body:
        if not isinstance(
            node,
            ast.ImportFrom,
        ):
            continue

        for alias in node.names:
            local_name = (
                alias.asname
                or alias.name
            )

            if local_name == "trim_text":
                trim_imports.append(
                    (
                        node.module,
                        alias.name,
                    )
                )

    if len(trim_imports) != 1:
        raise AssertionError(
            "expected exactly one trim_text import; "
            "found="
            + repr(trim_imports)
        )

    module_name, imported_name = (
        trim_imports[0]
    )

    if not module_name:
        raise AssertionError(
            "trim_text import module missing"
        )

    helper_module = importlib.import_module(
        module_name
    )

    trim_text = getattr(
        helper_module,
        imported_name,
    )

    module = ast.Module(
        body=selected,
        type_ignores=[],
    )

    ast.fix_missing_locations(
        module
    )

    namespace = {
        "trim_text": trim_text,
    }

    exec(
        compile(
            module,
            filename=str(BLOGGER_FILE),
            mode="exec",
        ),
        namespace,
        namespace,
    )

    return namespace[
        "editorial_context"
    ]


class VerifierPromptV2ContractTests(
    unittest.TestCase
):
    def review_case(self):
        case = build_atomic_review_case(
            article_text=ARTICLE,
            source_bundle=admitted_bundle(),
        )

        self.assertTrue(
            case.verifier_cases
        )

        return case.verifier_cases[0]

    def empty_evidence_case(self):
        case = build_atomic_review_case(
            article_text=ARTICLE,
            source_bundle=admitted_bundle(),
        )

        source_case = case.verifier_cases[0]

        empty_set = type(
            source_case.evidence_set
        )(
            claim_id=source_case.claim.claim_id,
            candidates=(),
        )

        return type(source_case)(
            claim=source_case.claim,
            evidence_set=empty_set,
        )

    def prompt_payload(self, case):
        messages = build_verifier_prompt(
            case
        )

        self.assertEqual(
            2,
            len(messages),
        )

        self.assertEqual(
            "system",
            messages[0]["role"],
        )

        self.assertEqual(
            "user",
            messages[1]["role"],
        )

        payload = json.loads(
            messages[1]["content"]
        )

        return (
            messages[0]["content"],
            payload,
        )

    def test_verdict_and_calibration_are_explicitly_distinct_semantics(self):
        system, payload = self.prompt_payload(
            self.review_case()
        )

        combined = (
            system
            + "\n"
            + json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
            )
        ).lower()

        self.assertIn(
            "verdict",
            combined,
        )

        self.assertIn(
            "calibration",
            combined,
        )

        self.assertIn(
            "evidentiary",
            combined,
        )

        self.assertIn(
            "wording",
            combined,
        )

        self.assertIn(
            "must not be copied",
            combined,
        )

    def test_insufficient_evidence_is_explicitly_forbidden_as_calibration(self):
        system, payload = self.prompt_payload(
            self.review_case()
        )

        combined = (
            system
            + "\n"
            + json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
            )
        )

        self.assertIn(
            "INSUFFICIENT_EVIDENCE is a verdict",
            combined,
        )

        self.assertIn(
            "never a calibration value",
            combined,
        )

    def test_empty_evidence_has_explicit_fail_closed_instruction(self):
        system, payload = self.prompt_payload(
            self.empty_evidence_case()
        )

        combined = (
            system
            + "\n"
            + json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
            )
        )

        self.assertEqual(
            [],
            payload["eligible_evidence"],
        )

        self.assertIn(
            "eligible_evidence is empty",
            combined,
        )

        self.assertIn(
            "SUPPORTED is forbidden",
            combined,
        )

        self.assertIn(
            "INSUFFICIENT_EVIDENCE",
            combined,
        )

    def test_prompt_explicitly_forbids_outside_facts_in_rationale(self):
        system, payload = self.prompt_payload(
            self.review_case()
        )

        combined = (
            system
            + "\n"
            + json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
            )
        )

        self.assertIn(
            "rationale",
            combined,
        )

        self.assertIn(
            "must not introduce",
            combined,
        )

        self.assertIn(
            "outside",
            combined.lower(),
        )

    def test_allowed_calibration_values_remain_exact(self):
        _, payload = self.prompt_payload(
            self.review_case()
        )

        expected = [
            item.value
            for item in CalibrationVerdict
            if item
            != CalibrationVerdict.UNASSESSED
        ]

        actual = payload[
            "required_output"
        ][
            "calibration"
        ]

        self.assertIsInstance(
            actual,
            dict,
        )

        self.assertEqual(
            "string",
            actual["type"],
        )

        self.assertEqual(
            expected,
            actual["enum"],
        )

        self.assertNotIn(
            VerificationVerdict
            .INSUFFICIENT_EVIDENCE
            .value,
            actual["enum"],
        )

    def test_live_failure_shape_remains_rejected(self):
        case = self.empty_evidence_case()

        malformed = json.dumps(
            {
                "calibration": (
                    "INSUFFICIENT_EVIDENCE"
                ),
                "claim_id": (
                    case.claim.claim_id
                ),
                "rationale": (
                    "The evidence is empty."
                ),
                "relied_on_packet_ids": [],
                "temporal_sensitivity": (
                    "NONE"
                ),
                "verdict": (
                    "INSUFFICIENT_EVIDENCE"
                ),
            }
        )

        with self.assertRaises(
            VerifierAdapterError
        ):
            parse_verifier_response(
                case,
                malformed,
            )

    def test_legal_insufficient_evidence_shape_remains_accepted(self):
        case = self.empty_evidence_case()

        legal = json.dumps(
            {
                "calibration": "PRECISE",
                "claim_id": (
                    case.claim.claim_id
                ),
                "rationale": (
                    "No eligible evidence "
                    "was supplied."
                ),
                "relied_on_packet_ids": [],
                "temporal_sensitivity": (
                    "NONE"
                ),
                "verdict": (
                    "INSUFFICIENT_EVIDENCE"
                ),
            }
        )

        result = parse_verifier_response(
            case,
            legal,
        )

        self.assertEqual(
            VerificationVerdict
            .INSUFFICIENT_EVIDENCE,
            result.verdict,
        )

        self.assertEqual(
            CalibrationVerdict.PRECISE,
            result.calibration,
        )

    def test_adapter_v5_is_post_repair_identity(self):
        self.assertEqual(
            "anarchi.editorial-verifier-adapter.v5",
            VERIFIER_ADAPTER_VERSION,
        )


class ProductionGenerationEvidenceProjectionTests(
    unittest.TestCase
):
    def test_blogger_uses_page_excerpt_from_admitted_source(self):
        editorial_context = (
            isolated_editorial_context()
        )

        context = editorial_context(
            admitted_bundle()
        )

        self.assertTrue(
            context["sources"]
        )

        source = context["sources"][0]

        self.assertEqual(
            (
                "Node.js runtime diagnostics "
                "can expose memory and heap behavior. "
                "Repeated observations can help "
                "engineers investigate retained objects "
                "and event-loop behavior."
            ),
            source["evidence_excerpt"],
        )

        self.assertEqual(
            "https://nodejs.org/docs/example",
            source["url"],
        )

        self.assertTrue(
            source[
                "relevance"
            ][
                "passed"
            ]
        )

    def test_isolated_function_bodies_come_from_current_blogger_source(self):
        source = BLOGGER_FILE.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'page.get("excerpt")',
            source,
        )

        self.assertIn(
            'payload.get("search_snippet", "")',
            source,
        )

        self.assertIn(
            '"evidence_excerpt"',
            source,
        )


if __name__ == "__main__":
    unittest.main()
