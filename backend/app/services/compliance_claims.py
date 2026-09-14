"""Compliance V2 — Layer 1: deterministic, free, regex-only claim detection.

This module only catches claims that are unambiguous by their own wording —
a guarantee, a medical/absolute-outcome verb, a quantified result, or a
fake-authority appeal. It deliberately does NOT touch ordinary marketing
adjectives ("strength", "energy", "glow", "stamina", "wellness", ...) on
their own — those are creative language, not claims, and are left entirely
to the contextual LLM pass in compliance_service.py.

Every pattern here is written to require the actual CLAIM SHAPE (a promise,
an absolute verb, a number, an appeal to authority) rather than a keyword,
which is what keeps "New strength, new finish line." out of this list while
"Guaranteed to increase stamina." is in it. When a hit lands here, severity
is always "blocker" — these are the obvious, high-confidence violations
Layer 2 doesn't need to re-litigate (see compliance_service.audit_script).
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DeterministicFinding:
    phrase: str
    claim_type: str
    reason: str
    suggested_fix: str
    severity: str = "blocker"


# Each entry: (compiled pattern, claim_type, reason, suggested_fix template).
# Patterns require an actual guarantee/absolute/quantified/authority SHAPE,
# not a bare adjective — see module docstring.
_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    # --- GUARANTEED_OUTCOME ---
    (
        re.compile(r"\bguarantee(s|d|ing)?\b", re.IGNORECASE),
        "GUARANTEED_OUTCOME",
        "This line promises a guaranteed result. A guarantee is a strong, binding claim that "
        "requires real substantiation, not aspirational marketing copy.",
        "Remove the guarantee — describe the product as designed to support the experience or "
        "routine instead of promising a specific, binding outcome.",
    ),
    (
        re.compile(r"\bresults?\s+guaranteed\b", re.IGNORECASE),
        "GUARANTEED_OUTCOME",
        "This line states results are guaranteed, which is a binding outcome claim.",
        "Remove the guarantee — describe the experience without promising a specific result.",
    ),
    (
        re.compile(r"\byou'?ll\s+(definitely|certainly)\b", re.IGNORECASE),
        "GUARANTEED_OUTCOME",
        "This phrasing states a definite/certain personal outcome for the customer, which reads "
        "as a guarantee rather than aspirational language.",
        "Soften to an aspirational statement (e.g. 'may help you feel...') rather than a certainty.",
    ),
    # --- MEDICAL_CLAIM / ABSOLUTE_OUTCOME (disease, cure, heal, prevent) ---
    (
        re.compile(r"\bcures?\b", re.IGNORECASE),
        "MEDICAL_CLAIM",
        "This line claims the product cures a condition — an unsubstantiated medical/absolute "
        "efficacy claim.",
        "Replace with supportive, experience-oriented language (e.g. 'helps support...') instead "
        "of a cure claim.",
    ),
    (
        re.compile(r"\bcure\s+for\b", re.IGNORECASE),
        "MEDICAL_CLAIM",
        "This line frames the product as 'a cure for' something — an unsubstantiated medical claim.",
        "Replace with supportive, experience-oriented language instead of a cure claim.",
    ),
    (
        re.compile(r"\bheals?\b", re.IGNORECASE),
        "MEDICAL_CLAIM",
        "This line claims the product heals a condition — an unsubstantiated medical claim.",
        "Replace with supportive, experience-oriented language instead of a healing claim.",
    ),
    (
        re.compile(r"\bprevents?\s+disease\b", re.IGNORECASE),
        "MEDICAL_CLAIM",
        "This line claims the product prevents disease — a regulated medical claim that requires "
        "real clinical substantiation.",
        "Remove the disease-prevention claim entirely; describe the general wellness experience instead.",
    ),
    (
        re.compile(r"\breverses?\s+aging\b", re.IGNORECASE),
        "MEDICAL_CLAIM",
        "This line claims the product reverses aging — an absolute, unsubstantiated outcome claim.",
        "Replace with supportive language about appearance/routine instead of reversing a biological process.",
    ),
    # --- ABSOLUTE_OUTCOME / COSMETIC_APPEARANCE_CLAIM ---
    (
        re.compile(r"\beliminates?\b", re.IGNORECASE),
        "ABSOLUTE_OUTCOME",
        "This line claims the product eliminates something completely — an absolute outcome claim "
        "rather than a supported/contributes-to framing.",
        "Replace with supportive language (e.g. 'helps reduce the look of...') instead of a complete "
        "elimination claim.",
    ),
    (
        re.compile(r"\berases?\b", re.IGNORECASE),
        "COSMETIC_APPEARANCE_CLAIM",
        "This line claims the product erases something completely — an absolute cosmetic outcome claim.",
        "Replace with supportive language (e.g. 'helps support a brighter, more even look') instead "
        "of an erase/complete-removal claim.",
    ),
    (
        re.compile(
            r"\bremoves?\s+(all\s+)?(pigmentation|dark\s+spots?|wrinkles?|acne|scars?|blemish(es)?)\b",
            re.IGNORECASE,
        ),
        "COSMETIC_APPEARANCE_CLAIM",
        "This line claims the product completely removes a specific skin condition — an absolute "
        "cosmetic outcome claim.",
        "Replace with supportive language (e.g. 'helps support brighter, more even-looking skin') "
        "instead of a removal claim.",
    ),
    (
        re.compile(r"\bpermanently\s+(removes?|eliminates?|cures?|fixes?)\b", re.IGNORECASE),
        "ABSOLUTE_OUTCOME",
        "This line claims a permanent result — an absolute, unsubstantiated outcome claim.",
        "Remove the permanence claim; describe the routine or experience instead.",
    ),
    (
        re.compile(r"\bworks?\s+instantly\b", re.IGNORECASE),
        "ABSOLUTE_OUTCOME",
        "This line claims an instant result, which is an unsubstantiated speed-of-efficacy claim.",
        "Remove the instant-result claim; describe the experience without promising a speed of effect.",
    ),
    (
        re.compile(r"\binstant(ly)?\s+results?\b", re.IGNORECASE),
        "ABSOLUTE_OUTCOME",
        "This line claims instant results, which is an unsubstantiated speed-of-efficacy claim.",
        "Remove the instant-result claim; describe the experience without promising a speed of effect.",
    ),
    (
        re.compile(r"\bcompletely\s+removes?\b", re.IGNORECASE),
        "ABSOLUTE_OUTCOME",
        "This line claims a complete removal — an absolute outcome claim.",
        "Replace with supportive, partial-effect language instead of a complete-removal claim.",
    ),
    # --- QUANTIFIED_CLAIM ---
    (
        re.compile(r"\b100%\s*effective\b", re.IGNORECASE),
        "QUANTIFIED_CLAIM",
        "This line claims 100% effectiveness — a quantified efficacy claim that requires real "
        "substantiation.",
        "Remove the effectiveness percentage; describe the general benefit instead.",
    ),
    (
        re.compile(r"\blose\s+\d+\s?(kg|kgs|lbs|pounds)\b", re.IGNORECASE),
        "QUANTIFIED_CLAIM",
        "This line promises a specific, measurable weight-loss amount — a quantified outcome claim.",
        "Remove the specific weight figure; describe the routine/lifestyle support instead.",
    ),
    (
        re.compile(
            r"\b(doubles?|triples?|2x|3x)\s+(your\s+)?(more\s+)?(stamina|energy|strength|endurance|performance)\b",
            re.IGNORECASE,
        ),
        "QUANTIFIED_CLAIM",
        "This line promises a specific multiplier on a physical outcome — a quantified performance claim.",
        "Remove the multiplier; describe the product as designed to support the activity instead of "
        "promising a measured increase.",
    ),
    (
        re.compile(r"\d+\s?%\s*(better|more|increase|improvement|effective)", re.IGNORECASE),
        "QUANTIFIED_CLAIM",
        "This line states a specific percentage improvement — a quantified efficacy claim.",
        "Remove the percentage figure; describe the benefit qualitatively instead.",
    ),
    (
        re.compile(
            r"\bclinically\s+proven\s+to\s+work\s+in\s+\d+\s*(day|days|week|weeks)\b",
            re.IGNORECASE,
        ),
        "QUANTIFIED_CLAIM",
        "This line combines a clinical-proof appeal with a specific timeframe — a compound quantified "
        "authority claim.",
        "Remove both the clinical claim and the timeframe unless real study data is attached; describe "
        "the routine instead.",
    ),
    # --- AUTHORITY_CLAIM ---
    (
        re.compile(r"\bclinically\s+(proven|tested)\b", re.IGNORECASE),
        "AUTHORITY_CLAIM",
        "This line claims clinical proof/testing, which is a regulated authority claim that requires "
        "real study data.",
        "Remove the clinical claim unless verified study data is available in the supplied product data.",
    ),
    (
        re.compile(r"\bscientifically\s+proven\b", re.IGNORECASE),
        "AUTHORITY_CLAIM",
        "This line claims scientific proof, which requires real substantiation to state.",
        "Remove the scientific-proof claim unless verified data is available.",
    ),
    (
        # Covers the English form and common Hinglish word orders: "doctor(s)
        # recommend(s/ed)", "doctor bhi recommend karte hain", "doctor ne
        # recommend kiya".
        re.compile(
            r"\bdoctor[s]?\s+(ne\s+|bhi\s+)?recommend(s|ed)?(\s+karte\s+hain|\s+kart[ea]\s+h[ae]i?n?|\s+kiya)?\b",
            re.IGNORECASE,
        ),
        "AUTHORITY_CLAIM",
        "This line claims a medical/professional endorsement that isn't necessarily verified.",
        "Remove the doctor-recommendation claim unless a genuine, verifiable endorsement is on file.",
    ),
    (
        re.compile(r"\bdoctor\s+approved\b", re.IGNORECASE),
        "AUTHORITY_CLAIM",
        "This line claims doctor approval, an unverified professional-endorsement claim.",
        "Remove the doctor-approval claim unless a genuine, verifiable endorsement is on file.",
    ),
    (
        re.compile(r"\bfda\s+approved\b", re.IGNORECASE),
        "AUTHORITY_CLAIM",
        "This line claims FDA approval, a specific regulatory claim that requires verification.",
        "Remove the regulatory-approval claim unless it is verified and applicable to this product.",
    ),
    (
        re.compile(r"\bgovernment\s+approved\b", re.IGNORECASE),
        "AUTHORITY_CLAIM",
        "This line claims government approval, a specific regulatory claim that requires verification.",
        "Remove the regulatory-approval claim unless it is verified and applicable to this product.",
    ),
    # --- FABRICATED_ACHIEVEMENT / TESTIMONIAL ---
    (
        re.compile(r"\bwon\s+a\s+marathon\b", re.IGNORECASE),
        "FABRICATED_ACHIEVEMENT",
        "This line claims a specific personal athletic achievement (winning a marathon) tied to the "
        "product — an unsubstantiated, likely-fabricated result.",
        "Remove the specific achievement claim; keep the story emotional/aspirational without a "
        "verifiable, unearned result.",
    ),
    (
        re.compile(r"\bthousands?\s+of\s+customers\b", re.IGNORECASE),
        "FABRICATED_ACHIEVEMENT",
        "This line cites a specific customer count/result that isn't sourced from supplied data — a "
        "likely-fabricated social-proof claim.",
        "Remove the specific customer-count claim unless it is a verified, supplied statistic.",
    ),
    # --- ABSOLUTE_OUTCOME: an outcome/resolution verb intensified by
    # "completely"/"permanently" nearby, either order. Generalizes rather
    # than listing literal sentences — this is what catches both "Prevents
    # hair fall completely." and a first-person testimonial like "my fatigue
    # completely disappeared" without needing a claim-specific pattern for
    # each, and without flagging a bare "prevents"/"disappeared" on its own. ---
    (
        re.compile(
            r"\b(cures?|cured|heals?|healed|prevents?|prevented|removes?|removed|eliminates?|eliminated|"
            r"erases?|erased|stops?|stopped|fixes?|fixed|disappears?|disappeared|vanishes?|vanished)\b"
            r"(?:\s+\S+){0,4}?\s+(completely|permanently)\b",
            re.IGNORECASE,
        ),
        "ABSOLUTE_OUTCOME",
        "This line pairs an outcome verb with an absolute intensifier ('completely'/'permanently') — a "
        "complete-resolution claim rather than a supported/contributes-to framing.",
        "Replace with supportive, partial-effect language (e.g. 'helps support...') instead of a "
        "complete or permanent resolution claim.",
    ),
    (
        re.compile(
            r"\b(completely|permanently)\b(?:\s+\S+){0,4}?\s+"
            r"(cured?|healed?|prevented|removed|eliminated|erased|stopped|fixed|disappeared|vanished|gone)\b",
            re.IGNORECASE,
        ),
        "ABSOLUTE_OUTCOME",
        "This line pairs an absolute intensifier ('completely'/'permanently') with a resolution verb — a "
        "complete-resolution claim rather than a supported/contributes-to framing.",
        "Replace with supportive, partial-effect language (e.g. 'helps support...') instead of a "
        "complete or permanent resolution claim.",
    ),
    (
        re.compile(r"\bnever\s+(feel|get)\s+tired\s+again\b", re.IGNORECASE),
        "ABSOLUTE_OUTCOME",
        "This line promises a permanent absence of fatigue — an absolute, unsubstantiated outcome claim.",
        "Replace with supportive energy-routine language instead of promising fatigue never returns.",
    ),
    (
        re.compile(r"\bkabhi\s+thakaan\s+nahi\b", re.IGNORECASE),
        "ABSOLUTE_OUTCOME",
        "This line promises fatigue will never occur again (Hinglish 'kabhi thakaan nahi') — an "
        "absolute, unsubstantiated outcome claim.",
        "Replace with supportive energy-routine language instead of promising fatigue never returns.",
    ),
    # --- MEDICAL_CLAIM / QUANTIFIED_CLAIM: Hinglish equivalents. An ailment
    # word and an absolute-resolution phrase within a short window of each
    # other, in either order — the same "claim shape, not a keyword" logic
    # as the English removes+bodypart pattern above, generalized so it
    # doesn't need a literal entry per test sentence. ---
    (
        re.compile(
            r"\b(pigmentation|thakaan|fatigue|dard|pain|acne|dana|hair\s*fall|wrinkles?|"
            r"dark\s+spots?|blemish(es)?|joint\s+pain|pet\s+ki\s+problem)\b"
            r"(?:\s+\S+){0,6}?\s+"
            r"(gayab(\s+ho(\s+gay[ai])?)?|bilkul\s+theek(\s+ho\s+gay[ai])?|poori\s+tarah\s+theek(\s+ho\s+gay[ai])?|"
            r"chali\s+gayi|ruk\s+gaya|khatam(\s+ho\s+gay[ai])?|theek\s+ho\s+gay[ai]|theek\s+karta\s+hai|"
            r"theek\s+kar\s+deta\s+hai)\b",
            re.IGNORECASE,
        ),
        "MEDICAL_CLAIM",
        "This line pairs a specific ailment/condition with an absolute Hinglish resolution phrase "
        "(fully gone/fixed) — an unsubstantiated medical/absolute-outcome claim.",
        "Replace with supportive, experience-oriented language instead of claiming the condition is "
        "fully resolved.",
    ),
    (
        re.compile(
            r"\b(gayab\s+ho(\s+gay[ai])?|bilkul\s+theek|poori\s+tarah\s+theek|chali\s+gayi|ruk\s+gaya|"
            r"khatam)\b"
            r"(?:\s+\S+){0,6}?\s+"
            r"(pigmentation|thakaan|fatigue|dard|pain|acne|dana|hair\s*fall|wrinkles?|dark\s+spots?|"
            r"blemish(es)?|joint\s+pain|pet\s+ki\s+problem)\b",
            re.IGNORECASE,
        ),
        "MEDICAL_CLAIM",
        "This line pairs an absolute Hinglish resolution phrase (fully gone/fixed) with a specific "
        "ailment/condition — an unsubstantiated medical/absolute-outcome claim.",
        "Replace with supportive, experience-oriented language instead of claiming the condition is "
        "fully resolved.",
    ),
    (
        re.compile(r"\bnormal\s+kar\s+deta\s+hai\b", re.IGNORECASE),
        "MEDICAL_CLAIM",
        "This line claims the product normalizes a medical measurement (e.g. blood pressure/sugar) — "
        "an unsubstantiated medical claim.",
        "Remove the medical-normalization claim; describe general wellness support instead.",
    ),
    (
        re.compile(
            r"\b(stamina|energy|strength|endurance)\s+double\s+ho\s+gaya\b|"
            r"\bdouble\s+ho\s+gaya\s+(stamina|energy|strength|endurance)\b",
            re.IGNORECASE,
        ),
        "QUANTIFIED_CLAIM",
        "This line claims a physical attribute doubled (Hinglish 'double ho gaya') — a quantified "
        "performance claim.",
        "Remove the multiplier; describe the product as designed to support the activity instead of "
        "promising a measured increase.",
    ),
    # --- MISLEADING_COMPARATIVE_CLAIM: an unqualified superiority claim over
    # every/all competitors, or an unverified market-leadership claim. ---
    (
        re.compile(r"\bbetter\s+than\s+(every|all|any)\s+other\b", re.IGNORECASE),
        "MISLEADING_COMPARATIVE_CLAIM",
        "This line claims superiority over every other competing product without substantiation.",
        "Remove the blanket superiority claim; describe this product's own benefit instead of comparing "
        "against all competitors.",
    ),
    (
        re.compile(r"\b(india'?s|world'?s)\s+(number\s*1|#\s?1|no\.?\s*1)\b", re.IGNORECASE),
        "MISLEADING_COMPARATIVE_CLAIM",
        "This line claims an unverified #1 market-leadership position.",
        "Remove the market-leadership claim unless it is a verified, sourced ranking.",
    ),
    (
        re.compile(r"\bbest\s+product\s+in\s+the\s+market\b", re.IGNORECASE),
        "MISLEADING_COMPARATIVE_CLAIM",
        "This line claims to be the best product in the market without substantiation.",
        "Remove the unqualified superlative; describe this product's own benefit instead.",
    ),
    (
        re.compile(r"\bfaster\s+than\s+(all|every)\s+competitors?\b", re.IGNORECASE),
        "MISLEADING_COMPARATIVE_CLAIM",
        "This line claims to outperform every competitor without substantiation.",
        "Remove the blanket competitive claim; describe this product's own benefit instead.",
    ),
    (
        re.compile(r"\b\d+x\s+(stronger|better|faster|more\s+effective)\b", re.IGNORECASE),
        "MISLEADING_COMPARATIVE_CLAIM",
        "This line states a specific multiplier of superiority without substantiation or a named basis "
        "of comparison.",
        "Remove the multiplier claim; describe this product's own benefit qualitatively instead.",
    ),
]


def find_deterministic_violations(text: str) -> list[DeterministicFinding]:
    """Scans the full script text for unambiguous, high-confidence claim
    violations. Returns an empty list when nothing definitive is found —
    that's the expected, common case for ordinary creative copy, and just
    means Layer 2 (contextual LLM) should do the more nuanced read."""
    if not text:
        return []
    raw_hits: list[tuple[tuple[int, int], DeterministicFinding]] = []
    for pattern, claim_type, reason, suggested_fix in _PATTERNS:
        for match in pattern.finditer(text):
            raw_hits.append(
                (
                    match.span(),
                    DeterministicFinding(
                        phrase=match.group(0),
                        claim_type=claim_type,
                        reason=reason,
                        suggested_fix=suggested_fix,
                    ),
                )
            )

    # Longer matches first so a compound pattern (e.g. "clinically proven to
    # work in 7 days") wins over the shorter pattern it overlaps with (e.g.
    # "clinically proven") instead of surfacing both as separate violations.
    raw_hits.sort(key=lambda item: (item[0][0], -(item[0][1] - item[0][0])))
    findings: list[DeterministicFinding] = []
    covered: list[tuple[int, int]] = []
    for (start, end), finding in raw_hits:
        if any(start < c_end and end > c_start for c_start, c_end in covered):
            continue
        covered.append((start, end))
        findings.append(finding)
    return findings
