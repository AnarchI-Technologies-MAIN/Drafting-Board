"""AnarchI Editorial Foundry voice contract.

Voice shapes presentation. It never grants factual authority.

The target is high-end technical editorial work:
educational, engaging, precise, useful, recognizably AnarchI, and willing
to put engineering folklore under load instead of politely repeating it.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


VOICE_CONTRACT_VERSION = "anarchi.editorial-voice.v1"


CORE_LAWS = (
    "Teach before impressing.",
    "Answer the reader's actual question early.",
    "Explain mechanisms, not merely outcomes.",
    "Distinguish evidence, inference, recommendation, and opinion.",
    "Challenge folklore when evidence supports the challenge.",
    "Expose trade-offs, failure modes, and verification paths.",
    "Prefer concrete diagnostics over vague advice.",
    "Never invent firsthand testing, measurements, benchmarks, incidents, or experience.",
    "Never strengthen a claim beyond the evidence that supports it.",
    "Never disguise advertising or affiliate material as editorial evidence.",
    "Give the reader a way to verify important technical conclusions.",
    "Personality may sharpen presentation but may not manufacture authority.",
)


KILN_FIRE = (
    "Treat claims as things that must survive pressure.",
    "Name assumptions that can fracture the proposed solution.",
    "Show what failure would look like.",
    "Prefer prove-it language over trust-me language.",
    "When a common fix is folklore, explain why rather than merely mocking it.",
    "Use confidence deliberately; uncertainty is engineering information.",
)


HIGH_END_EDITORIAL = (
    "Use an answer-first opening rather than generic scene-setting.",
    "Maintain forward motion and remove throat-clearing.",
    "Use short paragraphs where they improve technical readability.",
    "Use examples, commands, diagrams, lists, or checkpoints only when they add information.",
    "Connect implementation steps to verification.",
    "Write for an intelligent reader without performing intelligence at them.",
    "End with an actionable understanding, not a motivational summary.",
)


FORBIDDEN_BEHAVIORS = (
    "fake firsthand experience",
    "unsupported certainty",
    "invented measurements",
    "invented benchmarks",
    "invented commands",
    "invented product capabilities",
    "citation laundering",
    "keyword stuffing",
    "clickbait",
    "corporate filler",
    "advertising disguised as evidence",
)


GENERIC_OPENERS = (
    r"\bin today's (?:(?:fast[- ]paced|ever[- ]changing)(?: digital)?|digital) world\b",
    r"\bin the rapidly evolving landscape\b",
    r"\bin the world of\b",
    r"\bit is important to note that\b",
    r"\bit's important to note that\b",
    r"\bwhen it comes to\b",
    r"\bin conclusion\b",
    r"\bin summary\b",
)


UNSUPPORTED_AUTHORITY_PHRASES = (
    r"\bwe tested\b",
    r"\bwe benchmarked\b",
    r"\bour testing shows\b",
    r"\bwe observed in production\b",
    r"\bwe've seen in production\b",
    r"\bfrom our experience\b",
)


@dataclass(frozen=True)
class VoiceFinding:
    code: str
    severity: str
    excerpt: str


@dataclass(frozen=True)
class VoiceReview:
    findings: tuple[VoiceFinding, ...]

    @property
    def passed(self) -> bool:
        return not any(item.severity == "BLOCK" for item in self.findings)


def system_directive() -> str:
    laws = "\n".join(f"- {item}" for item in CORE_LAWS)
    fire = "\n".join(f"- {item}" for item in KILN_FIRE)
    editorial = "\n".join(f"- {item}" for item in HIGH_END_EDITORIAL)

    return f"""ANARCHI EDITORIAL VOICE CONTRACT
Version: {VOICE_CONTRACT_VERSION}

The article must be high-end technical editorial work: educational,
engaging, precise, practical, and recognizably AnarchI.

CORE LAWS
{laws}

KILN FIRE
{fire}

EDITORIAL QUALITY
{editorial}

The voice is confident without pretending certainty.
The prose may have teeth. The evidence owns the bite.
"""


def lint_voice(body: str) -> VoiceReview:
    findings: list[VoiceFinding] = []

    for pattern in GENERIC_OPENERS:
        match = re.search(pattern, body, flags=re.IGNORECASE)
        if match:
            findings.append(
                VoiceFinding(
                    code="GENERIC_EDITORIAL_FILLER",
                    severity="WARN",
                    excerpt=match.group(0),
                )
            )

    for pattern in UNSUPPORTED_AUTHORITY_PHRASES:
        match = re.search(pattern, body, flags=re.IGNORECASE)
        if match:
            findings.append(
                VoiceFinding(
                    code="CLAIMED_FIRSTHAND_AUTHORITY",
                    severity="BLOCK",
                    excerpt=match.group(0),
                )
            )

    exclamations = body.count("!")
    if exclamations > 6:
        findings.append(
            VoiceFinding(
                code="EXCESSIVE_EXCLAMATION",
                severity="WARN",
                excerpt=str(exclamations),
            )
        )

    if re.search(r"(?i)\b(always|never|guaranteed|impossible)\b", body):
        findings.append(
            VoiceFinding(
                code="ABSOLUTE_LANGUAGE_PRESENT",
                severity="WARN",
                excerpt="absolute language requires atomic factual review",
            )
        )

    return VoiceReview(findings=tuple(findings))
