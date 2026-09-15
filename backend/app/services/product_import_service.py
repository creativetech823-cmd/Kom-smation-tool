"""AyushWellness Product Library — URL-based product import (V1).

`import_product_from_url` is "the URL importer" referenced in the Product
Library UX brief: paste a public product page URL, get back a best-effort,
NEVER-INVENTED draft (`ProductImportResult`) for the user to review/edit
before anything is saved. A future Shopify Admin API importer would live
alongside this as a sibling function (e.g. `import_product_from_shopify`)
returning the exact same `ProductImportResult` shape, so the router/frontend
review-step code never needs to change — that's the whole "ProductImporter"
abstraction the brief asks for; no class hierarchy needed for one
implementation.

Two independent extraction passes, combined:
1. Deterministic image-candidate extraction (regex over the fetched
   markdown, no LLM) — reliable and free, but can't read prose.
2. A single lightweight LLM extraction pass over a *focused* excerpt of the
   page (not the raw firehose — product pages bury the actual description/
   ingredients/usage far past any fixed char-count truncation, verified
   against a real Shopify PDP where "About the Product" first appears at
   ~40,000 characters in) for the fields regex can't get: description,
   ingredients, benefits, usage, price, brand.

Both passes are told, repeatedly, to leave a field empty rather than guess —
see `_SYSTEM_PROMPT`. Nothing here downloads/stores images; that's a
separate, explicit user action (see `product_library_service.
download_asset_from_url`), so importing never silently creates files.
"""

import json
import logging
import re
from urllib.parse import urljoin, urlparse, parse_qs

from app.config import settings
from app.models.product_library import ProductImportImageCandidate, ProductImportResult
from app.services.content_extraction_service import fetch_url_as_text
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text

logger = logging.getLogger("product_import")

_MIN_IMAGE_WIDTH = 400  # same quality floor asset_service.py uses for stock imagery
_MAX_IMAGE_CANDIDATES = 12
_STOPWORDS = {"the", "a", "an", "of", "and", "for", "with", "by", "to", "in", "on"}

_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\((https?://[^)\s]+)\)")
_SECTION_MARKERS = [
    "about the product",
    "product description",
    "description",
    "suggested use",
    "how to use",
    "directions for use",
    "directions",
    "key ingredients",
    "ingredients",
    "key benefits",
    "benefits",
    "how it works",
]


def _significant_words(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _image_width(url: str) -> int:
    try:
        qs = parse_qs(urlparse(url).query)
        if "width" in qs:
            return int(qs["width"][0])
    except (ValueError, IndexError):
        pass
    return 0


def _base_key(url: str) -> str:
    """Same underlying image at different ?width=/?v= sizes should collapse
    to one candidate — dedupe key is the URL with those stripped."""
    parsed = urlparse(url)
    return f"{parsed.netloc}{parsed.path}"


def _extract_image_candidates(text: str, base_url: str, title: str) -> list[ProductImportImageCandidate]:
    title_words = _significant_words(title)
    min_overlap = 1 if len(title_words) <= 2 else 2

    best_by_key: dict[str, tuple[int, ProductImportImageCandidate]] = {}
    for alt, raw_url in _MD_IMAGE_RE.findall(text):
        url = urljoin(base_url, raw_url)
        width = _image_width(url)
        if width and width < _MIN_IMAGE_WIDTH:
            continue
        overlap = len(_significant_words(alt) & title_words) if title_words else 0
        # No title to match against (rare) — fall back to "reasonably large
        # image" alone rather than dropping every candidate.
        if title_words and overlap < min_overlap and width < 1000:
            continue
        key = _base_key(url)
        score = overlap * 1000 + width
        existing = best_by_key.get(key)
        if existing is None or score > existing[0]:
            best_by_key[key] = (score, ProductImportImageCandidate(url=url, alt=alt.strip()))

    ranked = sorted(best_by_key.values(), key=lambda pair: pair[0], reverse=True)
    return [candidate for _, candidate in ranked[:_MAX_IMAGE_CANDIDATES]]


def _build_focused_excerpt(text: str, title: str, max_total: int = 7000, window: int = 900) -> str:
    lower = text.lower()
    spans: list[tuple[int, int]] = []

    if title:
        idx = lower.find(title.lower()[:30])
        if idx >= 0:
            spans.append((idx, idx + window))

    for marker in _SECTION_MARKERS:
        pos = lower.find(marker)
        if pos != -1:
            spans.append((max(0, pos - 50), pos + window))

    if not spans:
        return text[:max_total]

    spans.sort()
    merged: list[list[int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1] + 200:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    excerpt = "\n...\n".join(text[s:e] for s, e in merged)
    return excerpt[:max_total]


_SYSTEM_PROMPT = """You extract a first-draft product profile from a real e-commerce product
page's raw content, for a product catalog. A human will review and correct every field before
anything is saved — this is a rough draft, not a final answer.

Return ONLY valid JSON matching this exact shape, no prose, no markdown fences:
{
  "short_description": string,
  "description": string,
  "price": string,
  "brand": string,
  "ingredients": [string],
  "benefits": [string],
  "usage": string,
  "variants": [string],
  "confidence": number between 0 and 1
}

Field notes:
- "short_description": one concise sentence.
- "description": 2-5 sentences, based only on what the page actually says.
- "price": the plain displayed price/range as text (e.g. "₹499" or "₹499 - ₹999"), or "" if unclear.
- "ingredients"/"benefits": short items, only ones the page explicitly lists — do not infer typical
  ingredients/benefits for this category of product from general knowledge.
- "usage": how the page says to use the product, in the page's own terms (dosage/frequency/method),
  or "" if not stated.
- "variants": short labels for distinct purchasable options if the page lists any (e.g. flavors,
  pack sizes), else [].

CRITICAL RULES:
- Do not invent, assume, or infer anything not directly present in the text.
- Never state or imply a medical claim, cure, guaranteed result, certification, or clinical outcome
  unless the page's own text says exactly that — and even then, keep the page's own phrasing rather
  than strengthening it.
- Do not turn marketing language into a stronger or more specific claim than the source text makes.
- Leave a field empty ("" or []) rather than guess when the page doesn't clearly say it.
"""


def _extract_via_llm(excerpt: str) -> dict:
    text = call_openrouter_with_retry(
        lambda: generate_text(
            system_instruction=_SYSTEM_PROMPT,
            contents=[excerpt],
            model=settings.openrouter_text_model,
            max_output_tokens=1024,
            json_mode=True,
        ),
        label="product_import",
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError("The AI returned malformed JSON while reading that product page — try again.") from e


def import_product_from_url(url: str) -> ProductImportResult:
    """The URL importer. Raises ExtractionError (already used by the
    reference-material URL flow) if the page can't be fetched at all —
    the router turns that into a clear, non-blocking error the user can
    retry or skip past into manual entry."""
    raw_text, title = fetch_url_as_text(url)

    warnings: list[str] = []
    images = _extract_image_candidates(raw_text, url, title)
    if not images:
        warnings.append("Couldn't confidently find product images on this page — add them manually below.")

    excerpt = _build_focused_excerpt(raw_text, title)
    try:
        data = _extract_via_llm(excerpt)
    except Exception as e:  # degrade to a manual-entry draft rather than hard-failing the import
        logger.warning("product_import LLM extraction failed for %s: %s", url, e)
        warnings.append("Couldn't read product details from this page automatically — fill them in manually.")
        data = {}

    return ProductImportResult(
        source_url=url,
        name=title or "",
        short_description=str(data.get("short_description") or "")[:500],
        description=str(data.get("description") or ""),
        price=(str(data.get("price")).strip() or None) if data.get("price") else None,
        brand=str(data.get("brand") or ""),
        ingredients=[str(i) for i in (data.get("ingredients") or []) if str(i).strip()][:20],
        benefits=[str(b) for b in (data.get("benefits") or []) if str(b).strip()][:20],
        usage=str(data.get("usage") or ""),
        variants=[str(v) for v in (data.get("variants") or []) if str(v).strip()][:20],
        images=images,
        confidence=float(data.get("confidence") or 0.0),
        warnings=warnings,
    )
