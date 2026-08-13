import base64
import json

import httpx
from anthropic import Anthropic

from app.config import settings
from app.models.product import AssetCandidate, AssetSourcingInput, SelectedAsset
from app.services.claude_utils import extract_json_text

_client = Anthropic(api_key=settings.anthropic_api_key)

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
    response = _client.messages.create(
        model=settings.claude_compliance_model,
        max_tokens=64,
        system=_BROADEN_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": tag}],
        # Extended thinking is on by default and its tokens count against
        # max_tokens — disabled so tiny-budget calls don't get starved.
        extra_body={"thinking": {"type": "disabled"}},
    )
    text_block = next(b for b in response.content if b.type == "text")
    return text_block.text.strip().strip('"')


def _download_as_base64(url: str) -> tuple[str, str] | None:
    """Fetch an image ourselves rather than letting Claude fetch the URL —
    stock sites like Pixabay serve redirect/CDN URLs that Claude's server-side
    fetch can't reliably reach."""
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        media_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]
        return media_type, base64.b64encode(resp.content).decode("ascii")
    except Exception:
        return None


def rank_with_vision(target_description: str, candidates: list[AssetCandidate]) -> tuple[int, str]:
    """Claude Vision picks the best-matching candidate. Falls back to the
    first downloadable candidate if the vision call fails for any reason —
    never blocks the pipeline."""
    content = [
        {
            "type": "text",
            "text": f"Target visual: {target_description}\n\nCandidates below, in order.",
        }
    ]
    downloadable_indices: list[int] = []
    for i, c in enumerate(candidates):
        downloaded = _download_as_base64(c.url)
        if downloaded is None:
            continue
        media_type, b64_data = downloaded
        content.append({"type": "text", "text": f"Candidate {i}:"})
        content.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64_data},
            }
        )
        downloadable_indices.append(i)

    if not downloadable_indices:
        return 0, "No candidate images could be downloaded — defaulted to first candidate."

    try:
        response = _client.messages.create(
            model=settings.claude_structuring_model,
            max_tokens=256,
            system=_VISION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            # Extended thinking is on by default and its tokens count against
            # max_tokens — disabled so tiny-budget calls don't get starved.
            extra_body={"thinking": {"type": "disabled"}},
        )
        data = json.loads(extract_json_text(response.content))
        return data["best_index"], data.get("reasoning", "")
    except Exception:
        return downloadable_indices[0], "Vision ranking unavailable — defaulted to first downloadable candidate."


def source_asset_for_line(payload: AssetSourcingInput) -> SelectedAsset:
    """Stage 8 — search tags in order, auto-broaden on zero results, then
    have Claude Vision pick the best match among gathered candidates."""

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
