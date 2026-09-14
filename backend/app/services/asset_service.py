import json
import logging
from pathlib import Path

import httpx
from PIL import Image

from app.config import settings
from app.models.product import AssetCandidate, AssetSourcingInput, ProductContext, SelectedAsset
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text, image_part

logger = logging.getLogger("asset_service")


class AssetProviderAuthError(Exception):
    """Raised when Pexels/Pixabay reject our API key — a configuration
    problem, not a legitimate "search found nothing" outcome. Kept distinct
    from a plain empty-results list so callers never confuse the two."""


# Candidates below this in either dimension are thumbnail-grade — rejecting
# them before they ever reach Gemini Vision is a cheap, deterministic quality
# floor; the actual relevance/quality judgment call still belongs to Vision.
_MIN_DIMENSION = 400

# Below this many candidates for a tag, the search is "weak" even if not
# literally empty — Gemini has too little to meaningfully compare, so it's
# worth spending one broaden_tag call to widen the pool (see source_asset_for_line).
_MIN_CANDIDATES_FOR_RANKING = 2

_BROADEN_SYSTEM_PROMPT = """You broaden an overly specific stock-photo search query into a more
generic one likely to return results, while staying visually relevant. If the query includes an
Indian-context modifier (e.g. "Indian man", "Indian woman", "Indian family", "Indian office worker"),
KEEP that modifier — generalize the rest of the query instead of dropping it.
Example: "elaichi green pods closeup" -> "cardamom closeup" -> "spice macro".
Example: "Indian man exhausted slumped at his desk after work" -> "Indian man tired at work" ->
"Indian office worker tired".
Return ONLY the broadened query text, nothing else — no quotes, no punctuation, no explanation."""

_VISION_SYSTEM_PROMPT = """You are an art director selecting the best stock photo for one line of a
short-form social-media advertisement (a vertical video ad or static creative). You will see a target
visual description and a numbered list of candidate images downloaded from Pexels/Pixabay.

Judge every candidate on ALL of these, not just whether it matches the words:
1. Scene relevance — does it actually depict the described scene?
2. Subject/action relevance — the right person doing the right thing?
3. Indian-context relevance — when the target description implies an Indian audience/setting (e.g.
   "Indian man", "Indian family", an Indian home/office/lifestyle moment), a candidate that genuinely
   shows Indian people/settings is a STRONG POSITIVE signal. This is a preference, not a hard rule —
   never pick a much lower-quality or less-relevant image just because it happens to show an Indian
   subject. The goal is the best realistic visual for this Indian advertisement, not merely "any image
   containing an Indian person."
4. Real-photography authenticity — a genuine photograph, not an illustration, cartoon, 3D render, or
   obviously synthetic/AI-looking image.
5. Natural human appearance — believable proportions, normal hands/faces, natural skin texture, not
   distorted or uncanny.
6. Commercial/ad suitability — could this plausibly appear in a real ad campaign?
7. Image quality — sharp, not blurry or pixelated; no visible watermark; no excessive text baked in.
8. Composition — well-framed, not an awkward crop.
9. Lighting — natural-looking, not harsh, flat, or artificial.
10. Resolution — prefer a higher-resolution, cleaner image over a soft/tiny one.
11. Emotional match — does the mood/expression match the line's emotional beat?
12. Ad-worthiness — would this work as a scroll-stopping social-ad visual?

Strongly penalize (rank below any reasonable alternative): unrelated people, the wrong action, the
wrong emotion, a generic landscape when a person is required, illustrations/cartoons/3D renders,
obviously artificial-looking images, blurry or very low-resolution images, awkward crops, strange
anatomy, watermarks, or an image that simply doesn't communicate the line.

Pick the single best match. In "reasoning", explain SPECIFICALLY why the winner beats the others —
name the concrete visual reason (e.g. "shows an Indian man naturally resting after work, matching the
exhaustion beat, with realistic lighting and a clean composition"), never a generic line like "this
image is relevant and visually appealing."

Return ONLY valid JSON, no markdown fences:
{"best_index": number, "reasoning": string}
"best_index" is the 0-based index of the best candidate."""


def _is_usable_candidate(url: str, thumbnail_url: str, width: int, height: int) -> bool:
    """Lightweight, deterministic quality floor applied before a candidate
    ever reaches Gemini Vision — missing media or a thumbnail-grade image are
    rejected outright; every actual relevance/quality judgment beyond that
    stays Vision's call, not regex/heuristics."""
    return bool(url) and bool(thumbnail_url) and width >= _MIN_DIMENSION and height >= _MIN_DIMENSION


def search_pexels(query: str, per_page: int = 5) -> list[AssetCandidate]:
    if not settings.pexels_api_key:
        return []
    resp = httpx.get(
        "https://api.pexels.com/v1/search",
        # orientation="portrait" matches the vertical (1080x1920) ad
        # composition — fewer awkward crops than defaulting to Pexels' mixed
        # orientation results.
        params={"query": query, "per_page": per_page, "orientation": "portrait"},
        headers={"Authorization": settings.pexels_api_key},
        timeout=15,
    )
    if resp.status_code in (401, 403):
        raise AssetProviderAuthError(
            f"Pexels rejected the configured API key (HTTP {resp.status_code}) — check PEXELS_API_KEY."
        )
    resp.raise_for_status()
    photos = resp.json().get("photos", [])
    return [
        AssetCandidate(
            source="pexels",
            url=p["src"]["large"],
            thumbnail_url=p["src"]["tiny"],
            width=p["width"],
            height=p["height"],
        )
        for p in photos
        if _is_usable_candidate(p["src"]["large"], p["src"]["tiny"], p["width"], p["height"])
    ]


def search_pixabay(query: str, per_page: int = 5) -> list[AssetCandidate]:
    if not settings.pixabay_api_key:
        return []
    resp = httpx.get(
        "https://pixabay.com/api/",
        params={
            "key": settings.pixabay_api_key,
            "q": query,
            "per_page": max(per_page, 3),  # Pixabay's hard minimum
            "orientation": "vertical",  # matches the 1080x1920 ad composition
            "image_type": "photo",  # excludes Pixabay's illustration/vector/clipart results
            "safesearch": "true",
        },
        timeout=15,
    )
    # Pixabay returns HTTP 400 (not 401/403) for an invalid/missing key, with
    # a body like "[ERROR 400] Invalid or missing API key" — verified live.
    # Only treat a 400 as an auth failure when the body actually says so, so
    # an unrelated bad request isn't misclassified as a credentials problem.
    if resp.status_code in (401, 403) or (
        resp.status_code == 400 and "api key" in resp.text.lower()
    ):
        raise AssetProviderAuthError(
            f"Pixabay rejected the configured API key (HTTP {resp.status_code}) — check PIXABAY_API_KEY."
        )
    resp.raise_for_status()
    hits = resp.json().get("hits", [])
    return [
        AssetCandidate(
            source="pixabay",
            url=h["largeImageURL"],
            thumbnail_url=h["previewURL"],
            width=h["imageWidth"],
            height=h["imageHeight"],
        )
        for h in hits[:per_page]
        if _is_usable_candidate(h["largeImageURL"], h["previewURL"], h["imageWidth"], h["imageHeight"])
    ]


def broaden_tag(tag: str) -> str:
    text = call_openrouter_with_retry(
        lambda: generate_text(
            system_instruction=_BROADEN_SYSTEM_PROMPT,
            contents=[tag],
            model=settings.openrouter_text_model,
            max_output_tokens=256,
        ),
        label="broaden_tag",
    )
    return text.strip().strip('"')


def _download_bytes(url: str) -> tuple[str, bytes] | None:
    """Fetch an image ourselves rather than letting Gemini fetch the URL —
    stock sites like Pixabay serve redirect/CDN URLs that a server-side
    fetch can't reliably reach."""
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        media_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]
        return media_type, resp.content
    except Exception:
        return None


def rank_with_vision(target_description: str, candidates: list[AssetCandidate]) -> tuple[int, str]:
    """Gemini Vision picks the best-matching candidate. Falls back to the
    first downloadable candidate if the vision call fails for any reason —
    never blocks the pipeline."""
    content: list = [f"Target visual: {target_description}\n\nCandidates below, in order."]
    downloadable_indices: list[int] = []
    for i, c in enumerate(candidates):
        downloaded = _download_bytes(c.url)
        if downloaded is None:
            continue
        media_type, data = downloaded
        content.append(f"Candidate {i}:")
        content.append(image_part(data, media_type))
        downloadable_indices.append(i)

    if not downloadable_indices:
        return 0, "No candidate images could be downloaded — defaulted to first candidate."

    try:
        text = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_VISION_SYSTEM_PROMPT,
                contents=content,
                model=settings.openrouter_text_model,
                max_output_tokens=512,
                json_mode=True,
            ),
            label="rank_with_vision",
        )
        data = json.loads(text)
        return data["best_index"], data.get("reasoning", "")
    except Exception:
        return downloadable_indices[0], "Vision ranking unavailable — defaulted to first downloadable candidate."


def _search_both_providers(query: str, provider_errors: list[str]) -> tuple[list[AssetCandidate], bool]:
    """Runs Pexels and Pixabay independently so one provider rejecting our
    API key doesn't discard real results the other provider found. Any auth
    failure is recorded in provider_errors (deduped) rather than raised —
    the caller decides how to report it once all tags/providers are tried.
    Also returns whether THIS specific call hit an auth error, so a caller
    can tell "genuinely zero results" apart from "couldn't even search"."""
    results: list[AssetCandidate] = []
    had_auth_error = False
    for search_fn in (search_pexels, search_pixabay):
        try:
            results.extend(search_fn(query))
        except AssetProviderAuthError as e:
            had_auth_error = True
            if str(e) not in provider_errors:
                provider_errors.append(str(e))
    return results, had_auth_error


# Sections (ScriptSection values — see app/models/product.py) whose scene is
# ABOUT the physical product itself — these must show the real, unmodified
# product asset when one exists, never a stock substitute and never a
# Gemini Vision re-ranking that could second-guess it away.
_PRODUCT_REQUIRED_SECTIONS = {"product_intro", "cta"}
# Sections about the formula/ingredients — prefer a real product/ingredient
# asset too, but this is the softer of the two tiers.
_INGREDIENT_SECTIONS = {"ingredients"}


def _absolute_url(url: str) -> str:
    """Every other asset source (Pexels/Pixabay) already returns an absolute
    URL — a Product Library asset's relative /product-uploads/... path needs
    the same treatment so both the browser (Assets step preview) and
    Remotion's render subprocess can actually fetch it, not just requests
    made from the backend's own origin."""
    if url.startswith("/"):
        return settings.backend_base_url.rstrip("/") + url
    return url


def _real_image_dimensions(url: str) -> tuple[int, int]:
    """Product Library assets are served from our own /product-uploads mount
    — read real dimensions off disk rather than guessing, so the
    AssetCandidate's width/height are honest. Falls back to the vertical-ad
    composition's own resolution if the file can't be read for any reason
    (never blocks the pipeline over metadata)."""
    try:
        relative = url.split("/product-uploads/", 1)[1]
        path = Path(settings.product_uploads_dir).resolve() / relative
        with Image.open(path) as img:
            return img.width, img.height
    except Exception:
        return 1080, 1920


def _resolve_product_asset(payload: AssetSourcingInput) -> SelectedAsset | None:
    """Deterministic product-asset priority — no LLM call, no Gemini Vision
    re-ranking. A scene whose `section` is unambiguously about the physical
    product (product_intro, cta) or its ingredients, OR whose visual_tags
    explicitly name the product, uses the Product Library's real, approved
    asset directly and unmodified. Returns None for every other case (no
    product selected, product has no usable asset, or this is a generic
    lifestyle/environment scene) — the caller falls through to the existing
    Pexels/Pixabay/Gemini Vision flow unchanged."""
    ctx: ProductContext | None = payload.product_context
    if ctx is None or not ctx.primary_asset_url:
        return None

    section = (payload.section or "").lower()
    name_mentioned = any(ctx.name.lower() in tag.lower() for tag in payload.visual_tags) if ctx.name else False
    is_product_scene = section in _PRODUCT_REQUIRED_SECTIONS or section in _INGREDIENT_SECTIONS or name_mentioned
    if not is_product_scene:
        return None

    width, height = _real_image_dimensions(ctx.primary_asset_url)
    absolute_url = _absolute_url(ctx.primary_asset_url)
    candidate = AssetCandidate(
        source="product_library",
        url=absolute_url,
        thumbnail_url=absolute_url,
        width=width,
        height=height,
    )
    logger.info(
        "[asset_service] line=%s product=%s section=%s -> product_library asset (priority match)",
        payload.line_id,
        ctx.product_id,
        section or "(name match)",
    )
    return SelectedAsset(
        line_id=payload.line_id,
        tag_used=f"product_library:{ctx.name}",
        broadened=False,
        candidate=candidate,
        reasoning=(
            f"Used the real {ctx.name} product asset — this scene calls for the actual product, "
            "so the approved Product Library asset takes priority over stock photography."
        ),
    )


def source_asset_for_line(payload: AssetSourcingInput) -> SelectedAsset:
    """Stage 8 — search tags in order, auto-broaden when a search comes back
    empty OR weak (fewer than _MIN_CANDIDATES_FOR_RANKING candidates — not
    enough for Gemini Vision to meaningfully compare), then have Gemini
    Vision pick the best match among gathered candidates.

    Product-aware priority: when a Product Library product is selected AND
    this scene is about the actual product/ingredients, its real approved
    asset is used directly (see _resolve_product_asset) and the rest of this
    function — Pexels/Pixabay/broadening/Vision — never runs for that line."""

    product_match = _resolve_product_asset(payload)
    if product_match is not None:
        return product_match

    provider_errors: list[str] = []

    for tag in payload.visual_tags:
        candidates, had_auth_error = _search_both_providers(tag, provider_errors)
        broadened = False

        # Broadening rewrites the query to be less specific — it can only
        # help a genuinely-empty/weak search, never a rejected API key, so
        # skip the (paid) broaden_tag call once this attempt already hit an
        # auth error rather than burning it on a query that will fail the
        # same way. A non-empty but weak result (1 candidate) is still worth
        # broadening for — its candidates are ADDED to, not replaced by, the
        # broadened search's results, since the original find may still win.
        if not had_auth_error and len(candidates) < _MIN_CANDIDATES_FOR_RANKING:
            broader_query = broaden_tag(tag)
            broadened_candidates, _ = _search_both_providers(broader_query, provider_errors)
            broadened = True
            tag = broader_query
            seen_urls = {c.url for c in candidates}
            candidates = candidates + [c for c in broadened_candidates if c.url not in seen_urls]

        # Steer away from an asset already used elsewhere in this same script
        # when the caller knows what's already been picked (e.g. regenerating
        # one line after the rest already loaded). Only apply the exclusion
        # if it leaves something to rank — a duplicate is still better than
        # no image at all.
        if payload.exclude_urls:
            deduped = [c for c in candidates if c.url not in payload.exclude_urls]
            if deduped:
                candidates = deduped

        if candidates:
            best_index, reasoning = rank_with_vision(tag, candidates)
            best_index = max(0, min(best_index, len(candidates) - 1))
            return SelectedAsset(
                line_id=payload.line_id,
                tag_used=tag,
                broadened=broadened,
                candidate=candidates[best_index],
                reasoning=reasoning,
            )

    if provider_errors:
        # No candidates from ANY tag/provider, and at least one provider
        # rejected our key along the way — this is a configuration problem,
        # not a legitimate empty search, so it must not read as "No match
        # found" to the frontend.
        return SelectedAsset(
            line_id=payload.line_id,
            tag_used=payload.visual_tags[-1],
            candidate=None,
            provider_error=True,
            reasoning="Asset provider authentication failed: " + "; ".join(provider_errors),
        )

    return SelectedAsset(
        line_id=payload.line_id,
        tag_used=payload.visual_tags[-1],
        candidate=None,
        reasoning="No candidates found across any tag, even after broadening.",
    )
