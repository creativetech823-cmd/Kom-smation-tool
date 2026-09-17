"""Human Insight Discovery — Part 3 of the AHM Creative DNA implementation.

A separate, small LLM stage that runs BEFORE architecture selection and hook
generation. Its only job is to answer one question concretely: what specific,
narrow psychological truth about THIS audience's relationship to THIS
problem makes a script worth writing — not a restatement of the product
benefit ("mothers want their kids healthy"), but something specific enough
that removing the product name would still read as true and recognizable.

Never raises: a failure here returns an empty/generic-fallback Insight and
the caller (script_service.py) proceeds with the existing arc-only behavior,
same fail-open convention as script_quality.py's gate.
"""

import json
import logging
from dataclasses import dataclass

from app.config import settings
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text

logger = logging.getLogger("creative_insight_service")

# Phrases that signal a "restated benefit" rather than a real insight — if
# the model's own insight text is dominated by these with no concrete scene/
# behavior/number attached, it's rejected and retried once.
_GENERIC_INSIGHT_SIGNALS = [
    "mothers worry about",
    "parents want the best",
    "every mother wants",
    "everyone wants to be healthy",
    "health is important",
    "people want to look good",
    "customers want quality",
    "in today's world",
    "in today's busy life",
    "wants their family to be healthy",
    "cares about their child's health",
    "wants what's best for",
]


@dataclass
class HumanInsight:
    target_person: str
    purchaser: str
    user: str
    situation: str
    behavior: str
    tension: str
    unspoken_truth: str
    why_not_solved_already: str
    insight_statement: str
    is_specific: bool

    def prompt_block(self) -> str:
        return (
            "HUMAN INSIGHT (discovered before writing — build the whole script around this, don't "
            "drift into a more generic angle):\n"
            f"Target person: {self.target_person}\n"
            f"Purchaser: {self.purchaser}\n"
            f"User (who actually uses/experiences it, if different from purchaser): {self.user}\n"
            f"Real-life situation: {self.situation}\n"
            f"Specific recurring behavior: {self.behavior}\n"
            f"Tension/fear/frustration/desire: {self.tension}\n"
            f"Unspoken truth: {self.unspoken_truth}\n"
            f"Why they haven't already solved this: {self.why_not_solved_already}\n"
            f'Insight statement (the ONE idea the script is built around): "{self.insight_statement}"\n'
        )


def _is_generic(insight_statement: str) -> bool:
    low = insight_statement.lower()
    if any(sig in low for sig in _GENERIC_INSIGHT_SIGNALS):
        return True
    # A real insight is specific enough to survive removing the product
    # category words — heuristic: too short / no concrete noun signal at all.
    return len(insight_statement.strip()) < 25


_SYSTEM_PROMPT = """You are a creative research strategist, the kind who does the thinking BEFORE an
ad agency writes a single line. Your only job: find ONE specific, narrow, true psychological insight
about this exact audience's relationship to this exact problem — not a category-level truth that
could apply to any competing product.

A weak insight is a restated benefit ("mothers worry about their kids' health"). A strong insight is
specific enough that a real person in this situation would recognize it immediately and a stranger
reading it without the product name attached would still find it true and recognizable — often a
CONTRADICTION, a recurring specific behavior, or an unspoken reason the problem hasn't been solved yet
(not just "they don't know about the solution").

Explicitly determine the PURCHASER and the USER — they may be the same person (self-purchase) or
different (e.g. a parent buying for a child, a gift, a caregiver). This changes what insight is even
relevant: a purchaser buying for someone else needs an insight about THEIR relationship to the user's
wellbeing, not a first-person insight that actually belongs to the user.

CRITICAL: derive the insight from THIS product's actual category and audience, not from any other
product's reference material you may know about. Do not default to tobacco/gutka/pan-shop/quitting-
addiction/chewing/smell-related situations, tropes, or phrasing unless the given product is actually
in that category — those belong to a completely different product and audience.

If a PRODUCT CREATIVE CONTRACT is given below, treat its category/use case/audience/consumption
context as fixed fact — never reinterpret the product based on an ambiguous word in its name (e.g. a
product with "masala" in its name is not automatically a cooking ingredient if the contract says
otherwise).

Return ONLY this JSON, no prose, no markdown fences:
{
  "target_person": string,
  "purchaser": string,
  "user": string,
  "situation": string,
  "behavior": string,
  "tension": string,
  "unspoken_truth": string,
  "why_not_solved_already": string,
  "insight_statement": string
}

Every field must be concrete and specific to the given product/audience — never a generic category
statement. If you cannot find a genuinely specific angle, still fill every field, but make
"insight_statement" as narrow and behavior-specific as the given information allows."""


def _user_message(
    product_name: str, category: str, target_audience: str, usp: str, benefits: list[str],
    primary_problem: str, contract_block: str = "",
) -> str:
    return (
        f"{contract_block}\n"
        f"Product: {product_name}\n"
        f"Category: {category}\n"
        f"Target audience (as given): {target_audience}\n"
        f"USP: {usp or 'not given'}\n"
        f"Key benefits: {', '.join(benefits) or 'not given'}\n"
        f"Primary problem it addresses (if given): {primary_problem or 'not given'}\n"
    )


def discover_insight(
    *,
    product_name: str,
    category: str,
    target_audience: str,
    usp: str = "",
    benefits: list[str] | None = None,
    primary_problem: str = "",
    contract_block: str = "",
) -> HumanInsight | None:
    """Returns None (never raises) if discovery genuinely fails — the caller
    proceeds without an explicit insight block, falling back to the
    pre-existing AUDIENCE step already baked into the main generation
    prompt's creative-direction chain-of-thought."""
    user_msg = _user_message(product_name, category, target_audience, usp, benefits or [], primary_problem, contract_block)
    try:
        for attempt in range(2):
            text = call_openrouter_with_retry(
                lambda: generate_text(
                    system_instruction=_SYSTEM_PROMPT,
                    contents=[user_msg if attempt == 0 else user_msg + (
                        "\n\nYour previous attempt's insight_statement was too generic/a restated "
                        "benefit. Find a genuinely more specific, behavior-anchored insight this time."
                    )],
                    model=settings.creative_model,
                    max_output_tokens=600,
                    json_mode=True,
                    label="creative_insight",
                ),
                label="creative_insight",
            )
            data = json.loads(text)
            statement = str(data.get("insight_statement") or "")
            specific = not _is_generic(statement)
            if specific or attempt == 1:
                return HumanInsight(
                    target_person=str(data.get("target_person") or ""),
                    purchaser=str(data.get("purchaser") or ""),
                    user=str(data.get("user") or ""),
                    situation=str(data.get("situation") or ""),
                    behavior=str(data.get("behavior") or ""),
                    tension=str(data.get("tension") or ""),
                    unspoken_truth=str(data.get("unspoken_truth") or ""),
                    why_not_solved_already=str(data.get("why_not_solved_already") or ""),
                    insight_statement=statement,
                    is_specific=specific,
                )
    except Exception as e:
        logger.warning("Human insight discovery failed, proceeding without an explicit insight: %s", e)
    return None
