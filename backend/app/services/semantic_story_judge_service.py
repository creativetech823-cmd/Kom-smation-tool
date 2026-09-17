"""Semantic Story Judge — Phase 3. Complements (never duplicates)
product_context_validator.py's deterministic category-drift detector and its
existing single-script llm_category_alignment_check.

Why this exists: the deterministic detector is relationship-based, not a
keyword list, but it's still finite — it only catches drift shapes it has a
registered pattern for (food/cooking, fitness/nutrition). A candidate can be
wrong in a way that uses none of those words at all, e.g. for Herbal Masala:
"A man gets ready for his morning routine and chooses this before his
workout." No food word, no explicit "supplement" phrase — but the product's
role has still silently become a generic wellness/routine item, not a gutka/
tobacco/supari alternative. That requires real semantic judgment, which is
what this module adds — scoped specifically to Choose Your Story candidates
(a BATCH of several situations at once, judged in a single call for cost
control), not a general-purpose replacement for the deterministic layer.

Cost control (Phase 3 Part J): ALL candidates from one generation batch are
judged in ONE Flash-Lite call, not one call per candidate — matching this
codebase's existing convention (territory/premise generation already judge
several candidates per call). Only invoked at all when the product's
contract actually carries a role risk (same gate the deterministic detector
uses) — a product with no known risk pattern never pays for this call.

Failure handling (Phase 3 Part K): a failed judge call returns None, never a
default "everyone passed". Callers must treat None as "semantic judging
unavailable this time" and fall back to the deterministic result alone
(candidates that already passed the free, real check) — never to an
unvalidated raw candidate. This is a deliberate, documented degrade-to-known-
good, not the fail-open hole Phase 2C removed.
"""

import json
import logging
from dataclasses import dataclass, field

from app.config import settings
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text
from app.services.product_context_service import ProductCreativeContract

logger = logging.getLogger("semantic_story_judge")

# Decision-policy thresholds (Part A6). Kept as named constants, not magic
# numbers scattered through the logic, so the policy is auditable in one
# place. UNCERTAIN is deliberately NOT a second LLM call (cost control) —
# it's treated as a conservative reject, distinct in logging from a clear
# drift, so it's never silently accepted.
CLEAR_PASS_MIN_ROLE_ALIGNMENT = 0.7
CLEAR_DRIFT_MAX_ROLE_ALIGNMENT = 0.4

_SCORE_FIELDS = [
    "product_truth_alignment", "audience_alignment", "behavior_alignment", "product_role_alignment",
    "creative_potential", "memorability", "visual_potential", "genericness_risk", "claim_safety",
    "territory_alignment",
]


@dataclass
class SemanticJudgment:
    candidate_index: int
    semantic_category_drift: bool
    reason: str
    product_truth_alignment: float = 0.0
    audience_alignment: float = 0.0
    behavior_alignment: float = 0.0
    product_role_alignment: float = 0.0
    creative_potential: float = 0.0
    memorability: float = 0.0
    visual_potential: float = 0.0
    genericness_risk: float = 0.0
    claim_safety: float = 1.0
    territory_alignment: float | None = None
    cluster_id: str = ""  # candidates sharing a cluster_id are "same idea, different clothes"

    @property
    def decision(self) -> str:
        """CLEAR_PASS / CLEAR_DRIFT / UNCERTAIN — never a silent pass-through."""
        if self.semantic_category_drift:
            return "clear_drift"
        if self.product_role_alignment <= CLEAR_DRIFT_MAX_ROLE_ALIGNMENT:
            return "clear_drift"
        if self.product_role_alignment >= CLEAR_PASS_MIN_ROLE_ALIGNMENT:
            return "clear_pass"
        return "uncertain"

    @property
    def passed(self) -> bool:
        return self.decision == "clear_pass"


_SYSTEM_PROMPT = """You are a semantic judge for a set of short-form ad "story situation" candidates —
premises, not scripts. Evaluate MEANING and ROLE, not keyword presence. A candidate can be wrong even
when it uses none of the obviously wrong words for this product's category — e.g. for a tobacco/gutka
replacement product, "he gets ready for his morning routine and reaches for this before his workout"
contains no food or fitness-supplement keyword, but the product has still quietly become a generic
wellness/routine item instead of what it actually is. Judge the underlying role, not the vocabulary.

You are given a PRODUCT CREATIVE CONTRACT (immutable fact — the product's real category, audience,
behavior, and consumption context) and, for each candidate, its title/description/persona/marketing
angle. For each candidate, score (0.0-1.0 each):
- product_truth_alignment: does this situation make sense for what the product ACTUALLY is?
- audience_alignment: does it naturally involve the real audience who'd use/consider this product?
- behavior_alignment: does it connect to a real behavior/tension/problem this product's category
  actually involves (per the contract), not an unrelated one?
- product_role_alignment: is the product playing its CORRECT role in the situation (not reinterpreted
  as a different kind of product)? This is the single most important score — weight it accordingly.
- creative_potential: does this have real ad potential (a recognizable tension, an unexpected turn, a
  visual opportunity, a specific setting, a memorable premise) or is it flat/generic even if correct?
- memorability: would a viewer remember the core idea after seeing it once?
- visual_potential: can this become a strong visual/video concept, concretely shootable?
- genericness_risk: how interchangeable is this with a generic ad for almost any product in this
  broad category (1.0 = completely generic, 0.0 = distinctly product-specific)?
- claim_safety: 1.0 = makes no unsupported medical/health/performance/timeline claim; lower if it does.
- territory_alignment: ONLY if a CREATIVE TERRITORY is given below — does this candidate actually
  EXECUTE that territory's human tension, or does it just vaguely gesture at it? Omit (null) if no
  territory was given.

Also set semantic_category_drift (boolean): true only when the product's role has genuinely been
reinterpreted as something the contract's forbidden_contexts describe or clearly implies — NOT true
merely because the setting is a kitchen/office/gym/family scene; the setting is never the problem, the
product's role is. Do not reject a candidate just because it's conventional or simple — a correct,
if generic, situation should score correctly on genericness_risk, not be marked as drift.

Also assign cluster_id (a short string) to each candidate: candidates that are fundamentally the SAME
underlying creative idea — the same tension/reveal/mechanism with only the character, setting, or
wording changed ("friend notices he stopped", "friend asks why he doesn't carry it anymore", "friend
sees him using the new product instead" are the SAME idea in different clothes) — must share the exact
same cluster_id. Genuinely different ideas get different cluster_id values. Do not force diversity by
inventing differences that aren't really there, and do not force sameness either — judge honestly.

Return ONLY this JSON, no prose, no markdown fences:
{"judgments": [
  {"candidate_index": int, "semantic_category_drift": boolean, "reason": string,
   "product_truth_alignment": number, "audience_alignment": number, "behavior_alignment": number,
   "product_role_alignment": number, "creative_potential": number, "memorability": number,
   "visual_potential": number, "genericness_risk": number, "claim_safety": number,
   "territory_alignment": number_or_null, "cluster_id": string}
]}"""


def _candidate_block(index: int, item: dict) -> str:
    return (
        f"[{index}] title: {item.get('title', '')}\n"
        f"    description: {item.get('description', '')}\n"
        f"    persona: {item.get('persona', '')}\n"
        f"    marketing_angle: {item.get('marketing_angle', '')}"
    )


def _user_message(contract: ProductCreativeContract, candidates: list[dict], territory_block: str = "") -> str:
    candidates_block = "\n".join(_candidate_block(i, c) for i, c in enumerate(candidates))
    territory_section = f"\nCREATIVE TERRITORY (score territory_alignment against this):\n{territory_block}\n" if territory_block else ""
    return f"{contract.prompt_block()}\n{territory_section}\nCandidates:\n{candidates_block}"


def _parse_judgment(raw: dict) -> SemanticJudgment | None:
    if not isinstance(raw, dict):
        return None
    try:
        index = int(raw.get("candidate_index"))
    except (TypeError, ValueError):
        return None
    territory_raw = raw.get("territory_alignment")
    territory = float(territory_raw) if isinstance(territory_raw, (int, float)) else None
    kwargs = {}
    for k in _SCORE_FIELDS:
        if k == "territory_alignment":
            continue
        try:
            kwargs[k] = float(raw.get(k) or 0.0)
        except (TypeError, ValueError):
            kwargs[k] = 0.0
    return SemanticJudgment(
        candidate_index=index,
        semantic_category_drift=bool(raw.get("semantic_category_drift")),
        reason=str(raw.get("reason") or ""),
        territory_alignment=territory,
        cluster_id=str(raw.get("cluster_id") or f"_ungrouped_{index}"),
        **kwargs,
    )


def judge_story_situations(
    contract: ProductCreativeContract,
    candidates: list[dict],
    territory_block: str = "",
    label: str = "semantic_story_judge",
) -> list[SemanticJudgment] | None:
    """ONE batched call judging every candidate at once. Returns None (never
    an empty-list-means-all-passed ambiguity, never a silent all-pass) on
    any failure — callers must treat None as "unavailable this run" and fall
    back to whatever already-verified state they had before calling this,
    never to trusting the raw candidates."""
    if not candidates:
        return []
    try:
        text = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_SYSTEM_PROMPT,
                contents=[_user_message(contract, candidates, territory_block)],
                model=settings.validation_model,
                max_output_tokens=4096,
                json_mode=True,
                label=label,
            ),
            label=label,
            max_attempts=2,
        )
        data = json.loads(text)
        raw_judgments = data.get("judgments") or []
        judgments = [j for j in (_parse_judgment(r) for r in raw_judgments) if j is not None]
        if not judgments:
            logger.warning("Semantic story judge returned no parseable judgments — treating as unavailable")
            return None
        return judgments
    except Exception as e:
        logger.warning("Semantic story judge failed, treating as unavailable (falling back to deterministic-only): %s", e)
        return None


def dedupe_by_cluster(judgments: list[SemanticJudgment]) -> set[int]:
    """Returns the set of candidate_index values to KEEP — one
    representative per cluster_id (the highest creative_potential, tie-
    broken by lowest genericness_risk). Operates purely on the judgments'
    own candidate_index (which already references positions in the caller's
    original candidate list) — no re-indexing required by the caller."""
    clusters: dict[str, list[SemanticJudgment]] = {}
    for j in judgments:
        clusters.setdefault(j.cluster_id, []).append(j)

    def best_of(js: list[SemanticJudgment]) -> SemanticJudgment:
        return max(js, key=lambda j: (j.creative_potential, -j.genericness_risk))

    return {best_of(js).candidate_index for js in clusters.values()}
