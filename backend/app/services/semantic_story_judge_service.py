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
import re
import time
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

# Live production timeout fix (2026-09-18 task) — this call's own timeout
# ceiling, and the minimum time worth even attempting it. Mirrors
# story_situation_service's identically-named constants; duplicated locally
# per this module's own existing convention (see _claim_safety_fields's
# rationale in that module) rather than imported, since story_situation_
# service.py already imports FROM this module. `deadline`, when given by
# the caller, shrinks the actual timeout used below this ceiling — never
# above it.
_JUDGE_CALL_TIMEOUT_SECONDS = 40.0
_JUDGE_MIN_CALL_SECONDS = 8.0


def _remaining_call_timeout(deadline: float | None) -> float:
    if deadline is None:
        return _JUDGE_CALL_TIMEOUT_SECONDS
    return min(_JUDGE_CALL_TIMEOUT_SECONDS, deadline - time.monotonic())

_SCORE_FIELDS = [
    "product_truth_alignment", "audience_alignment", "behavior_alignment", "product_role_alignment",
    "creative_potential", "memorability", "visual_potential", "genericness_risk", "claim_safety",
    "territory_alignment",
]

# Above this genericness_risk, a candidate is rejected outright regardless of
# its decision (Part 7's genericness test) — a candidate can score
# "clear_pass" on product-truth/role-alignment while still being an
# interchangeable, swap-the-product-name idea; genericness is a separate gate,
# not folded into decision, since a product-correct-but-generic idea is a
# different failure than a product-incorrect one.
GENERIC_REJECTION_THRESHOLD = 0.75


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
    # Story Ideas Creative DNA upgrade (2026-09-18 task, Parts 9-11) — claim
    # safety and emotional-authenticity signals computed in this SAME batched
    # call (no extra LLM call), reusing claim_safety_service's vocabulary
    # conceptually. The full semantic/narrative-implied-claim + coercion
    # check that claim_safety_service.py runs is still the script-level hard
    # gate; these are the cheaper idea-level screen so an unsafe concept
    # never reaches "strong concept" status or gets picked at all when a
    # safer alternative exists.
    implied_claim: bool = False
    emotional_coercion: bool = False

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
    def is_generic(self) -> bool:
        """Part 7's genericness test, as a hard boolean gate distinct from
        `decision` — a candidate can be product-correct (clear_pass) and
        still fail this on its own."""
        return self.genericness_risk >= GENERIC_REJECTION_THRESHOLD

    @property
    def passed(self) -> bool:
        return (
            self.decision == "clear_pass"
            and not self.is_generic
            and not self.implied_claim
            and not self.emotional_coercion
        )


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
  When hook_type/hook_execution are given, also weigh HOOK QUALITY here: does the described execution
  actually create curiosity and visibly execute the stated hook_type, or does it just announce the
  product/explain the benefit immediately/read as generic motivational copy with no visual/action/
  dialogue event? A weak hook lowers creative_potential even when the rest of the idea is sound.
- memorability: would a viewer remember the core idea after seeing it once?
- visual_potential: can this become a strong visual/video concept, concretely shootable?
- genericness_risk: how interchangeable is this with a generic ad for almost any product in this
  broad category (1.0 = completely generic, 0.0 = distinctly product-specific). A hook_execution that
  could open an ad for any unrelated product, or that doesn't connect to this candidate's own
  creative_mechanism, raises genericness_risk even if the rest of the premise is specific.
- claim_safety: 1.0 = makes no unsupported medical/health/performance/timeline claim; lower if it does.
- territory_alignment: ONLY if a CREATIVE TERRITORY is given below — does this candidate actually
  EXECUTE that territory's human tension, or does it just vaguely gesture at it? Omit (null) if no
  territory was given.

Keep "reason" VERY SHORT — 8 words or fewer, a label not a sentence (e.g. "generic setting, weak role
alignment"). This response judges many candidates in one call; verbose reasons waste output budget.

Also set semantic_category_drift (boolean): true only when the product's role has genuinely been
reinterpreted as something the contract's forbidden_contexts describe or clearly implies — NOT true
merely because the setting is a kitchen/office/gym/family scene; the setting is never the problem, the
product's role is. Do not reject a candidate just because it's conventional or simple — a correct,
if generic, situation should score correctly on genericness_risk, not be marked as drift.

Also assign cluster_id (a short string) to each candidate: candidates that are fundamentally the SAME
underlying creative idea — the same tension/reveal/mechanism with only the character, setting, or
wording changed ("friend notices he stopped", "friend asks why he doesn't carry it anymore", "friend
sees him using the new product instead" are the SAME idea in different clothes) — must share the exact
same cluster_id. If a creative_mechanism/creative_engine is given per candidate, weigh that heavily:
two candidates using the same underlying mechanism AND the same kind of behavior/object/turn, just with
a different character or setting standing in for it, are the same cluster even if the wording differs a
lot. Genuinely different ideas (different mechanism, different behavior, different turn) get different
cluster_id values. Do not force diversity by inventing differences that aren't really there, and do not
force sameness either — judge honestly.

Also detect, per candidate:
- implied_claim: true when the situation's premise (even just a title/description) implies an
  unsupported health/efficacy outcome caused by the product — e.g. "before weak, after using it
  energetic", a wilting-to-blooming metaphor, a prayer answered by the product working. A candidate
  simply mentioning a given ingredient, or a general positioning idea, is NOT a claim on its own.
- emotional_coercion: true when the premise relies on guilt, devotional/prayer-answered framing, a
  child being blamed for a parent's suffering, or family approval being tied to the purchase decision
  to persuade — NOT true for an ordinary warm family/relationship story with no guilt/pressure mechanism.

Return ONLY this JSON, no prose, no markdown fences:
{"judgments": [
  {"candidate_index": int, "semantic_category_drift": boolean, "reason": "<=8 words",
   "product_truth_alignment": number, "audience_alignment": number, "behavior_alignment": number,
   "product_role_alignment": number, "creative_potential": number, "memorability": number,
   "visual_potential": number, "genericness_risk": number, "claim_safety": number,
   "territory_alignment": number_or_null, "cluster_id": string,
   "implied_claim": boolean, "emotional_coercion": boolean}
]}"""


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"```\s*$", "", text)
    return text.strip()


def _salvage_judgments(text: str) -> list[dict]:
    """Best-effort recovery for a truncated judge response (same failure
    class, and same fix, as story_situation_service._salvage_array_objects
    for pool generation — duplicated locally rather than imported, since
    story_situation_service.py already imports FROM this module and an
    import the other way would be circular). Finds "judgments"'s `[`, walks
    top-level `{...}` objects by bracket depth (tracking string/escape
    state), and parses each independently — skipping only the incomplete
    trailing object a truncation leaves behind. Returns [] (never raises)
    if the array marker itself can't be found."""
    marker = '"judgments"'
    key_pos = text.find(marker)
    if key_pos == -1:
        return []
    array_start = text.find("[", key_pos)
    if array_start == -1:
        return []
    results: list[dict] = []
    i = array_start + 1
    n = len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n,":
            i += 1
        if i >= n or text[i] != "{":
            break
        depth = 0
        in_string = False
        escape = False
        start = i
        end = None
        while i < n:
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            i += 1
        if end is None:
            break  # ran off the end mid-object — the truncated tail, stop here
        candidate_text = text[start:end]
        try:
            obj = json.loads(candidate_text)
            if isinstance(obj, dict):
                results.append(obj)
        except json.JSONDecodeError:
            pass
        i = end
    return results


def _parse_judge_json(text: str) -> dict:
    """Robust parse for the judge's JSON response: strips a markdown fence
    the model can still emit despite json_mode, strips trailing commas, and
    — only when the response still doesn't parse as a whole — salvages
    whatever complete judgment objects survive rather than discarding the
    entire batch over one truncated tail object. A genuinely unrecoverable
    response still raises json.JSONDecodeError, unchanged from before this
    fix (the caller's existing "treat as unavailable" fallback still
    applies)."""
    cleaned = _strip_markdown_fence(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    no_trailing_commas = re.sub(r",\s*([}\]])", r"\1", cleaned)
    try:
        return json.loads(no_trailing_commas)
    except json.JSONDecodeError as e:
        salvaged = _salvage_judgments(cleaned)
        if salvaged:
            logger.warning(
                "Semantic story judge response didn't parse as a whole (likely truncated) — salvaged "
                "%d complete judgment(s) instead of discarding the entire batch.",
                len(salvaged),
            )
            return {"judgments": salvaged}
        raise e


def _candidate_block(index: int, item: dict) -> str:
    lines = [
        f"[{index}] title: {item.get('title', '')}",
        f"    description: {item.get('description', '')}",
        f"    persona: {item.get('persona', '')}",
        f"    marketing_angle: {item.get('marketing_angle', '')}",
    ]
    # Story Ideas Creative DNA upgrade (2026-09-18 task) — additive fields
    # only present once story_situation_service.py's new pool-generation
    # prompt is in use; older/mocked candidate dicts without them are
    # unaffected (nothing is appended).
    if item.get("creative_mechanism"):
        lines.append(f"    creative_mechanism: {item.get('creative_mechanism', '')}")
    if item.get("creative_engine"):
        lines.append(f"    creative_engine: {item.get('creative_engine', '')}")
    if item.get("behavioral_tension"):
        lines.append(f"    behavioral_tension: {item.get('behavioral_tension', '')}")
    if item.get("hook_type"):
        lines.append(f"    hook_type: {item.get('hook_type', '')}")
    if item.get("hook_execution"):
        lines.append(f"    hook_execution: {item.get('hook_execution', '')}")
    return "\n".join(lines)


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
        implied_claim=bool(raw.get("implied_claim")),
        emotional_coercion=bool(raw.get("emotional_coercion")),
        **kwargs,
    )


def judge_story_situations(
    contract: ProductCreativeContract,
    candidates: list[dict],
    territory_block: str = "",
    label: str = "semantic_story_judge",
    deadline: float | None = None,
) -> list[SemanticJudgment] | None:
    """ONE batched call judging every candidate at once. Returns None (never
    an empty-list-means-all-passed ambiguity, never a silent all-pass) on
    any failure — callers must treat None as "unavailable this run" and fall
    back to whatever already-verified state they had before calling this,
    never to trusting the raw candidates.

    `deadline` (live production timeout fix, 2026-09-18): an optional
    absolute time.monotonic() value shared with the caller's other Story
    Ideas calls — when there's not enough of it left to be worth trying,
    this call is skipped outright (no HTTP request at all) and treated the
    same as any other judge-unavailable failure. None (the default —
    including creative_quality_benchmark.py's direct call) preserves the
    exact prior fixed-40s-timeout behavior."""
    if not candidates:
        return []

    def _generate_judge_text() -> str:
        # Per-retry deadline fix (2026-09-18 live production task) — mirrors
        # story_situation_service.py's identical fix for pool generation:
        # the timeout used to be computed ONCE, before call_openrouter_with_
        # retry() ever ran, then captured by this closure and reused
        # unchanged for every attempt. Recomputing it HERE means every
        # individual attempt (including a retry) asks "how much time is
        # actually left right now?" immediately before making its own HTTP
        # request — a deadline that's already gone means this closure raises
        # instead of making another OpenRouter request at all.
        remaining = _remaining_call_timeout(deadline)
        if remaining < _JUDGE_MIN_CALL_SECONDS:
            logger.warning(
                "Semantic story judge skipped — shared Story Ideas time budget nearly exhausted (%.1fs left), "
                "falling back to deterministic-only", remaining,
            )
            raise ValueError("Semantic story judge time budget exhausted.")
        return generate_text(
            system_instruction=_SYSTEM_PROMPT,
            contents=[_user_message(contract, candidates, territory_block)],
            model=settings.validation_model,
            max_output_tokens=4096,
            json_mode=True,
            label=label,
            # Reasoning-token-truncation fix (2026-09-18 task, live
            # production failure): generate_text()'s reasoning_effort
            # defaults to settings.openrouter_reasoning_effort ("medium")
            # on EVERY call unless overridden — that default was added
            # for GPT-5.6 Luna, but Gemini Flash-Lite (this call's model,
            # per Option C routing) also honors OpenRouter's unified
            # reasoning.effort field, so it was silently spending a
            # variable, large share of max_output_tokens on hidden
            # reasoning before any visible JSON, truncating the batched
            # judgment response mid-string (confirmed in Render logs:
            # "Unterminated string..."). This call doesn't need or want
            # reasoning tokens — it's a scoring/classification task, not
            # open-ended generation — so reasoning is turned off here,
            # Story-Ideas-judge-specific, leaving every other call site's
            # (including Luna's) reasoning behavior untouched.
            reasoning_effort=None,
            # Budget-overshoot fix (2026-09-18 task, refined by the per-
            # retry shared-deadline fix above) — this judge is exclusively
            # used by Story Ideas generation (confirmed: its only callers
            # are story_situation_service.py and the offline creative_
            # quality_benchmark.py tool), so shortening its per-call
            # timeout is Story-Ideas-specific, not a global change. It's
            # one of three sequential LLM calls inside one Story Ideas
            # "attempt" — see story_situation_service.py's
            # _STORY_IDEAS_CALL_TIMEOUT_SECONDS for the full rationale.
            timeout=remaining,
        )

    try:
        text = call_openrouter_with_retry(
            _generate_judge_text,
            label=label,
            max_attempts=2,
        )
        try:
            data = _parse_judge_json(text)
        except json.JSONDecodeError as e:
            logger.warning(
                "Semantic story judge JSON parse failed (model=%s): length=%d chars, head=%r, tail=%r, error=%s",
                settings.validation_model, len(text), text[:120], text[-120:], e,
            )
            raise
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
