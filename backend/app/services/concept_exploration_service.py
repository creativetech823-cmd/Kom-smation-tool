"""Multi-concept exploration — generates several genuinely different creative
territories in one call, each with its own insight/architecture/hook
sketch, so a human (or an automated diversity check) can compare them
before committing to one. Distinct from the main generate_script() pipeline,
which commits to a single insight/architecture/hook per call — this module
is for exploration/comparison (e.g. "show me 5 different directions"), not
wired into the default single-script generation path.

Never raises: returns an empty list on failure.
"""

import json
import logging
from dataclasses import dataclass, field

from app.config import settings
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text

logger = logging.getLogger("concept_exploration_service")


@dataclass
class ConceptSketch:
    creative_territory: str
    human_insight: str
    architecture_key: str
    hook: str
    beat_summary: str
    must_include: list[str] = field(default_factory=list)


_SYSTEM_PROMPT = """You are a creative director exploring multiple genuinely different directions for
a brief, before committing to one. Generate exactly N distinct creative concepts — not N variations
of the same underlying story with different wording.

Each concept must have its OWN human insight (a specific, narrow psychological truth — never a
restated category benefit), its own suggested architecture (pick from the list given), its own hook,
and a short beat-by-beat summary (3-5 sentences describing what happens, not polished dialogue).

DIVERSITY REQUIREMENT: no two concepts may share the same core insight, the same narrative frame, or
the same emotional register. If you notice two of your own concepts converging on the same underlying
story (e.g. two variations of "worried parent -> product -> reassurance"), replace one with something
structurally different (a different persona, a different moment, a different architecture, a
different tone entirely).

CRITICAL: ground every concept in THIS product's actual category and audience. Do not default to
tobacco/gutka/pan-shop/quitting-addiction/chewing-related situations unless the given product is
actually in that category.

Return ONLY this JSON, no prose, no markdown fences:
{
  "concepts": [
    {
      "creative_territory": string,
      "human_insight": string,
      "architecture_key": string,
      "hook": string,
      "beat_summary": string,
      "must_include": [string]
    }
  ]
}"""


def _user_message(product_name: str, category: str, target_audience: str, usp: str, benefits: list[str], count: int, architecture_catalog: str) -> str:
    return (
        f"Product: {product_name}\n"
        f"Category: {category}\n"
        f"Target audience: {target_audience}\n"
        f"USP: {usp or 'not given'}\n"
        f"Key benefits: {', '.join(benefits) or 'not given'}\n\n"
        f"Generate exactly {count} genuinely different creative concepts.\n\n"
        f"Available architectures to choose from:\n{architecture_catalog}"
    )


def generate_concept_sketches(
    *,
    product_name: str,
    category: str,
    target_audience: str,
    usp: str = "",
    benefits: list[str] | None = None,
    count: int = 5,
) -> list[ConceptSketch]:
    from app.services.creative_architecture import architecture_catalog_prompt_block

    try:
        user_msg = _user_message(product_name, category, target_audience, usp, benefits or [], count, architecture_catalog_prompt_block())
        text = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_SYSTEM_PROMPT,
                contents=[user_msg],
                model=settings.openrouter_text_model,
                max_output_tokens=2000,
                json_mode=True,
            ),
            label="concept_exploration",
        )
        data = json.loads(text)
        raw = data.get("concepts") or []
        return [
            ConceptSketch(
                creative_territory=str(c.get("creative_territory") or ""),
                human_insight=str(c.get("human_insight") or ""),
                architecture_key=str(c.get("architecture_key") or ""),
                hook=str(c.get("hook") or ""),
                beat_summary=str(c.get("beat_summary") or ""),
                must_include=[str(m) for m in (c.get("must_include") or [])],
            )
            for c in raw
            if isinstance(c, dict)
        ]
    except Exception as e:
        logger.warning("Concept exploration failed: %s", e)
        return []


def diversity_check(concepts: list[ConceptSketch]) -> list[str]:
    """Cheap, deterministic same-story-shape detector: flags when 3+
    concepts share a suspiciously similar insight (high word overlap) —
    the exact "mother worried -> child sick -> product -> ingredients ->
    child healthy -> CTA, repeated 5 times" failure this exists to catch."""
    import re

    def tokens(text: str) -> set[str]:
        return {w for w in re.findall(r"[a-zA-Z]{4,}", text.lower())}

    insight_tokens = [tokens(c.human_insight) for c in concepts]
    flagged_pairs = 0
    for i in range(len(insight_tokens)):
        for j in range(i + 1, len(insight_tokens)):
            a, b = insight_tokens[i], insight_tokens[j]
            if not a or not b:
                continue
            overlap = len(a & b) / min(len(a), len(b))
            if overlap > 0.5:
                flagged_pairs += 1

    issues = []
    if flagged_pairs >= 3:
        issues.append("insufficient_creative_diversity")
    architectures_used = {c.architecture_key for c in concepts if c.architecture_key}
    if len(concepts) >= 3 and len(architectures_used) <= 1:
        issues.append("no_architectural_diversity")
    return issues
