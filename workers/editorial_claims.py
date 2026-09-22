"""Atomic claim extraction contracts for AnarchI Editorial Foundry.

Extraction identifies candidate claims. It does not verify them and grants
no factual, adjudication, image, or publication authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from typing import Iterable


CLAIM_EXTRACTOR_VERSION = "anarchi.editorial-claims.v2"


class ExtractedClaimType(str, Enum):
    FACT = "FACT"
    CAUSAL = "CAUSAL"
    COMMAND = "COMMAND"
    CONFIGURATION = "CONFIGURATION"
    CAPABILITY = "CAPABILITY"
    BENCHMARK = "BENCHMARK"
    TEMPORAL = "TEMPORAL"
    RECOMMENDATION = "RECOMMENDATION"
    INFERENCE = "INFERENCE"
    OPINION = "OPINION"
    RHETORICAL = "RHETORICAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ExtractedClaim:
    claim_id: str
    text: str
    claim_type: ExtractedClaimType
    material: bool
    source_span_start: int
    source_span_end: int


@dataclass(frozen=True)
class ClaimLedger:
    article_digest: str
    extractor_version: str
    claims: tuple[ExtractedClaim, ...]

    @property
    def claim_count(self) -> int:
        return len(self.claims)

    @property
    def material_count(self) -> int:
        return sum(1 for claim in self.claims if claim.material)

    @property
    def verification_authority(self) -> bool:
        return False

    @property
    def adjudication_authority(self) -> bool:
        return False

    @property
    def publication_authority(self) -> bool:
        return False


def article_digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def normalize_claim_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def claim_id(index: int, text: str) -> str:
    digest = hashlib.sha256(
        normalize_claim_text(text).encode("utf-8")
    ).hexdigest()[:12]
    return f"claim-{index:04d}-{digest}"


def _is_internal_period(
    shadow: str,
    index: int,
) -> bool:
    previous = (
        shadow[index - 1]
        if index > 0
        else ""
    )

    following = (
        shadow[index + 1]
        if index + 1 < len(shadow)
        else ""
    )

    if (
        previous
        and following
        and (
            previous.isalnum()
            or previous == "_"
        )
        and (
            following.isalnum()
            or following == "_"
        )
    ):
        return True

    token_start = index

    while (
        token_start > 0
        and not shadow[token_start - 1].isspace()
    ):
        token_start -= 1

    token = shadow[token_start : index + 1].lower()

    if token in {
        "dr.",
        "mr.",
        "mrs.",
        "ms.",
        "prof.",
        "sr.",
        "jr.",
        "st.",
        "vs.",
        "etc.",
    }:
        return True

    if token in {
        "e.g.",
        "i.e.",
    }:
        return True

    if re.fullmatch(
        r"(?:[a-z]\.){2,}",
        token,
    ):
        following_index = index + 1

        while (
            following_index < len(shadow)
            and shadow[following_index].isspace()
        ):
            following_index += 1

        if (
            following_index < len(shadow)
            and shadow[following_index].islower()
        ):
            return True

    return False


def split_candidate_sentences(body: str) -> list[tuple[str, int, int]]:
    """Extract complete punctuation-terminated prose spans.

    Ordinary line wrapping is whitespace, not a claim boundary.

    Markdown heading characters are masked in a same-length shadow string
    so headings cannot swallow the first prose sentence while all returned
    offsets continue to reference the original article bytes.

    Periods embedded in technical tokens, numeric values, versions,
    hostnames, member access, and selected nonterminal abbreviations are
    preserved inside the containing sentence.
    """
    candidates: list[tuple[str, int, int]] = []

    shadow = re.sub(
        r"(?m)^#{1,6}[^\n]*(?=\n|$)",
        lambda match: " " * len(match.group(0)),
        body,
    )

    sentence_start = 0
    index = 0

    while index < len(shadow):
        character = shadow[index]

        if character not in ".!?":
            index += 1
            continue

        if (
            character == "."
            and _is_internal_period(
                shadow,
                index,
            )
        ):
            index += 1
            continue

        cluster_end = index + 1

        while (
            cluster_end < len(shadow)
            and shadow[cluster_end] in ".!?"
        ):
            cluster_end += 1

        start = sentence_start
        end = cluster_end

        while (
            start < end
            and shadow[start].isspace()
        ):
            start += 1

        while (
            end > start
            and shadow[end - 1].isspace()
        ):
            end -= 1

        candidate = normalize_claim_text(
            body[start:end]
        )

        if (
            candidate
            and not candidate.startswith("#")
        ):
            candidates.append(
                (
                    candidate,
                    start,
                    end,
                )
            )

        sentence_start = cluster_end
        index = cluster_end

    return candidates


def heuristic_classify(text: str) -> ExtractedClaimType:
    lowered = text.lower()

    if re.search(r"\b(if|because|therefore|causes?|leads? to|results? in)\b", lowered):
        return ExtractedClaimType.CAUSAL

    if re.search(r"\b(run|execute|invoke|use the command|command)\b", lowered):
        return ExtractedClaimType.COMMAND

    if re.search(r"\b(today|currently|now|latest|as of|recently)\b", lowered):
        return ExtractedClaimType.TEMPORAL

    if re.search(r"\b(configure|configuration|setting|environment variable)\b", lowered):
        return ExtractedClaimType.CONFIGURATION

    if re.search(r"\b(can|supports?|allows?|provides?|is capable of)\b", lowered):
        return ExtractedClaimType.CAPABILITY

    if re.search(r"\b(\d+(?:\.\d+)?%|\d+\s*(?:ms|seconds?|minutes?|gb|mb|kb))\b", lowered):
        return ExtractedClaimType.BENCHMARK

    if re.search(r"\b(should|recommend|prefer|best practice|avoid)\b", lowered):
        return ExtractedClaimType.RECOMMENDATION

    if re.search(r"\b(may|might|suggests?|likely|appears? to|inference)\b", lowered):
        return ExtractedClaimType.INFERENCE

    if re.search(r"\b(i think|we think|in our view|arguably)\b", lowered):
        return ExtractedClaimType.OPINION

    return ExtractedClaimType.FACT


def heuristic_materiality(
    text: str,
    claim_type: ExtractedClaimType,
) -> bool:
    if claim_type in {
        ExtractedClaimType.OPINION,
        ExtractedClaimType.RHETORICAL,
    }:
        return False

    if len(normalize_claim_text(text)) < 18:
        return False

    return True


def extract_claims(body: str) -> ClaimLedger:
    claims: list[ExtractedClaim] = []

    for index, (text, start, end) in enumerate(
        split_candidate_sentences(body),
        start=1,
    ):
        claim_type = heuristic_classify(text)
        material = heuristic_materiality(text, claim_type)

        claims.append(
            ExtractedClaim(
                claim_id=claim_id(index, text),
                text=text,
                claim_type=claim_type,
                material=material,
                source_span_start=start,
                source_span_end=end,
            )
        )

    return ClaimLedger(
        article_digest=article_digest(body),
        extractor_version=CLAIM_EXTRACTOR_VERSION,
        claims=tuple(claims),
    )
