"""Category -> banned/high-risk claim rules for the Stage 7 compliance pass.

This is a starter list, not a legal reference. Expand per-category as real
categories are onboarded (consult legal/compliance for anything regulated —
pan masala, supplements, pharma, financial products, etc).
"""

DEFAULT_RULES = [
    "No absolute medical/cure claims (e.g. 'cures', 'treats disease', 'guaranteed to heal').",
    "No unverified superlatives implying regulatory or scientific endorsement "
    "(e.g. 'doctor recommended', 'clinically proven') unless explicitly provided in the source data.",
    "No guaranteed-outcome language for weight loss, income, or performance ('guaranteed results').",
]

CATEGORY_RULES: dict[str, list[str]] = {
    "supplements": [
        "No claims that the product diagnoses, treats, cures, or prevents any disease.",
        "Avoid 'FDA approved' or similar regulatory-approval language unless verified.",
    ],
    "tobacco": [
        "No health claims of any kind.",
        "No language minimizing health risk.",
        "No appeal to minors or imagery/language suggesting youth appeal.",
    ],
    "pan masala": [
        "No health claims of any kind.",
        "No language minimizing health risk or implying safety.",
        "No claims of being 'less harmful' than alternatives.",
    ],
    "finance": [
        "No guaranteed-return or guaranteed-profit language.",
        "No implication of risk-free investment.",
    ],
}


def rules_for_category(category: str) -> list[str]:
    key = category.strip().lower()
    return DEFAULT_RULES + CATEGORY_RULES.get(key, [])
