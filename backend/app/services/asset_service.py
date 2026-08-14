import json

import httpx
from google.genai import types as genai_types

from app.config import settings
from app.models.product import AssetCandidate, AssetSourcingInput, SelectedAsset
from app.services.gemini_utils import call_gemini_with_retry, generate_text

_BROADEN_SYSTEM_PROMPT = """You broaden an overly specific stock-photo search query into a more
generic one likely to return results, while staying visually relevant.
Example: "elaichi green pods closeup" -> "cardamom closeup" -> "spice macro".
Return ONLY the broadened query text, nothing else — no quotes, no punctuation, no explanation."""

_VISION_SYSTEM_PROMPT = """You are selecting the best stock image for a video ad line.
You will see a target visual description and a numbered list of candidate images.
Pick the single best match. Return ONLY valid JSON, no markdown fences:
{"best_index": number, "reasoning": string}
"best_index" is the 0-based index of the best candidate."""


def search_pexels(query: str, per_page: int = 3) -> list[AssetCandidate]:
    if not settings.pexels_api_key:
        return []
    resp = httpx.get(
        "https://api.pexels.com/v1/search",
        params={"query": query, "per_page": per_page},
        headers={"Authorization": settings.pexels_api_key},
        timeout=15,
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
    ]


def search_pixabay(query: str, per_page: int = 3) -> list[AssetCandidate]:
    if not settings.pixabay_api_key:
        return []
    resp = httpx.get(
        "https://pixabay.com/api/",
        params={"key": settings.pixabay_api_key, "q": query, "per_page": max(per_page, 3)},
        timeout=15,
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
    ]


def broaden_tag(tag: str) -> str:
    text = call_gemini_with_retry(
        lambda: generate_text(
            system_instruction=_BROADEN_SYSTEM_PROMPT,
            contents=[tag],
            model=settings.gemini_text_model,
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
        content.append(genai_types.Part.from_bytes(data=data, mime_type=media_type))
        downloadable_indices.append(i)

    if not downloadable_indices:
        return 0, "No candidate images could be downloaded — defaulted to first candidate."

    try:
        text = call_gemini_with_retry(
            lambda: generate_text(
                system_instruction=_VISION_SYSTEM_PROMPT,
                contents=content,
                model=settings.gemini_text_model,
                max_output_tokens=512,
                json_mode=True,
            ),
            label="rank_with_vision",
        )
        data = json.loads(text)
        return data["best_index"], data.get("reasoning", "")
    except Exception:
        return downloadable_indices[0], "Vision ranking unavailable — defaulted to first downloadable candidate."


def source_asset_for_line(payload: AssetSourcingInput) -> SelectedAsset:
    """Stage 8 — search tags in order, auto-broaden on zero results, then
    have Gemini Vision pick the best match among gathered candidates."""

    for tag in payload.visual_tags:
        candidates = search_pexels(tag) + search_pixabay(tag)
        broadened = False

        if not candidates:
            broader_query = broaden_tag(tag)
            candidates = search_pexels(broader_query) + search_pixabay(broader_query)
            broadened = True
            tag = broader_query

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

    return SelectedAsset(
        line_id=payload.line_id,
        tag_used=payload.visual_tags[-1],
        candidate=None,
        reasoning="No candidates found across any tag, even after broadening.",
    )
