"""Asset Sourcing error-handling tests (Step 5 hardening).

Covers the three required cases without needing real Pexels/Pixabay keys:
  A. invalid/misconfigured provider credentials -> provider_error, not "no match"
  C. legitimate zero results (both providers return empty, no auth error) -> plain "not found"

Case B (valid credentials returning real results, broadening, and Gemini
Vision ranking) cannot be verified here without real API keys — see the
implementation report for why that case is reported as untested rather than
claimed to pass.
"""

from unittest.mock import MagicMock, patch

import httpx

from app.models.product import AssetSourcingInput, ProductContext
from app.services import asset_service
from app.services.asset_service import AssetProviderAuthError, search_pexels, search_pixabay, source_asset_for_line


def _product_context(**overrides) -> ProductContext:
    defaults = dict(
        product_id="prod123",
        name="Aayush Wellness Herbal Masala",
        category="herbal_health",
        short_description="",
        usp="",
        target_audience="",
        primary_problem="",
        positioning="",
        ingredients=[],
        benefits=[],
        approved_claims=[],
        prohibited_claims=[],
        mandatory_wording="",
        preferred_tone="",
        preferred_language="",
        cta_text="",
        winning_hooks=[],
        reference_script_excerpts=[],
        primary_asset_url="/product-uploads/prod123/pack.png",
    )
    defaults.update(overrides)
    return ProductContext(**defaults)


def _fake_response(status_code: int, json_body: dict | None = None, text: str = "") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.text = text
    resp.raise_for_status.side_effect = (
        httpx.HTTPStatusError("error", request=MagicMock(), response=resp) if status_code >= 400 else None
    )
    return resp


def test_search_pexels_raises_provider_auth_error_on_401():
    with patch.object(asset_service.settings, "pexels_api_key", "xxxxxxxx"):
        with patch("httpx.get", return_value=_fake_response(401, text="Invalid API key")):
            try:
                search_pexels("cardamom")
                assert False, "expected AssetProviderAuthError"
            except AssetProviderAuthError as e:
                assert "Pexels" in str(e)


def test_search_pixabay_raises_provider_auth_error_on_400_with_api_key_message():
    with patch.object(asset_service.settings, "pixabay_api_key", "xxxxxxxx"):
        with patch(
            "httpx.get",
            return_value=_fake_response(400, text="[ERROR 400] Invalid or missing API key"),
        ):
            try:
                search_pixabay("cardamom")
                assert False, "expected AssetProviderAuthError"
            except AssetProviderAuthError as e:
                assert "Pixabay" in str(e)


def test_search_pixabay_bare_400_without_api_key_message_is_not_misclassified():
    # A 400 for an unrelated reason (e.g. malformed param) must NOT be
    # treated as a credentials problem.
    with patch.object(asset_service.settings, "pixabay_api_key", "real-looking-key"):
        with patch("httpx.get", return_value=_fake_response(400, text="[ERROR 400] per_page out of range")):
            try:
                search_pixabay("cardamom")
                assert False, "expected a plain HTTPStatusError, not AssetProviderAuthError"
            except AssetProviderAuthError:
                assert False, "misclassified an unrelated 400 as a credentials error"
            except httpx.HTTPStatusError:
                pass


def test_search_pexels_returns_empty_list_when_key_missing():
    with patch.object(asset_service.settings, "pexels_api_key", ""):
        assert search_pexels("cardamom") == []


# --- Case A: invalid credentials must surface as provider_error, never "no match" ---
def test_source_asset_reports_provider_error_when_both_providers_reject_key():
    payload = AssetSourcingInput(line_id="hook", visual_tags=["cardamom closeup"])
    with patch.object(asset_service, "search_pexels", side_effect=AssetProviderAuthError("Pexels rejected the configured API key (HTTP 401).")):
        with patch.object(asset_service, "search_pixabay", side_effect=AssetProviderAuthError("Pixabay rejected the configured API key (HTTP 400).")):
            with patch.object(asset_service, "broaden_tag", return_value="spice macro") as mock_broaden:
                result = source_asset_for_line(payload)
    assert result.candidate is None
    assert result.provider_error is True
    assert "authentication failed" in result.reasoning.lower()
    # A rejected API key can't be fixed by a broader query — broadening (a
    # paid OpenRouter call) must be skipped once auth has already failed.
    mock_broaden.assert_not_called()


def test_source_asset_keeps_healthy_provider_results_when_the_other_fails_auth():
    """One provider being misconfigured must not discard real results the
    other provider found — this is the per-provider isolation fix."""
    from app.models.product import AssetCandidate

    real_candidate = AssetCandidate(source="pixabay", url="http://x/img.jpg", thumbnail_url="http://x/thumb.jpg", width=100, height=100)
    payload = AssetSourcingInput(line_id="hook", visual_tags=["cardamom closeup"])
    with patch.object(asset_service, "search_pexels", side_effect=AssetProviderAuthError("Pexels rejected the configured API key (HTTP 401).")):
        with patch.object(asset_service, "search_pixabay", return_value=[real_candidate]):
            with patch.object(asset_service, "rank_with_vision", return_value=(0, "best match")):
                result = source_asset_for_line(payload)
    assert result.candidate is not None
    assert result.candidate.url == "http://x/img.jpg"
    assert result.provider_error is False


def test_source_asset_keeps_pexels_results_when_pixabay_fails_auth():
    """Symmetric to the test above: Pixabay misconfigured must not discard
    Pexels' real results either — provider isolation isn't one-directional."""
    from app.models.product import AssetCandidate

    real_candidate = AssetCandidate(source="pexels", url="http://x/pexels.jpg", thumbnail_url="http://x/thumb.jpg", width=200, height=200)
    payload = AssetSourcingInput(line_id="hook", visual_tags=["cardamom closeup"])
    with patch.object(asset_service, "search_pixabay", side_effect=AssetProviderAuthError("Pixabay rejected the configured API key (HTTP 400).")):
        with patch.object(asset_service, "search_pexels", return_value=[real_candidate]):
            with patch.object(asset_service, "rank_with_vision", return_value=(0, "best match")):
                result = source_asset_for_line(payload)
    assert result.candidate is not None
    assert result.candidate.url == "http://x/pexels.jpg"
    assert result.provider_error is False


# --- Case C: legitimate zero results must stay a plain "not found", no provider_error ---
def test_source_asset_reports_plain_not_found_when_providers_are_healthy_but_empty():
    payload = AssetSourcingInput(line_id="hook", visual_tags=["extremely obscure query"])
    with patch.object(asset_service, "search_pexels", return_value=[]):
        with patch.object(asset_service, "search_pixabay", return_value=[]):
            with patch.object(asset_service, "broaden_tag", return_value="still obscure") as mock_broaden:
                result = source_asset_for_line(payload)
    assert result.candidate is None
    assert result.provider_error is False
    assert "no candidates found" in result.reasoning.lower()
    # A genuinely empty (non-auth) result IS worth broadening.
    mock_broaden.assert_called_once_with("extremely obscure query")


# --- Quality-floor filtering (asset quality hardening) ---
def test_search_pexels_filters_out_low_resolution_candidates():
    good_photo = {
        "src": {"large": "http://x/good.jpg", "tiny": "http://x/good_tiny.jpg"},
        "width": 1080,
        "height": 1920,
    }
    tiny_photo = {
        "src": {"large": "http://x/tiny.jpg", "tiny": "http://x/tiny_tiny.jpg"},
        "width": 150,
        "height": 200,
    }
    resp = _fake_response(200, json_body={"photos": [good_photo, tiny_photo]})
    with patch.object(asset_service.settings, "pexels_api_key", "real-looking-key"):
        with patch("httpx.get", return_value=resp):
            results = search_pexels("indian man tired after work")
    assert len(results) == 1
    assert results[0].url == "http://x/good.jpg"


def test_search_pixabay_filters_out_low_resolution_candidates():
    good_hit = {"largeImageURL": "http://x/good.jpg", "previewURL": "http://x/good_p.jpg", "imageWidth": 1280, "imageHeight": 1920}
    tiny_hit = {"largeImageURL": "http://x/tiny.jpg", "previewURL": "http://x/tiny_p.jpg", "imageWidth": 100, "imageHeight": 100}
    resp = _fake_response(200, json_body={"hits": [good_hit, tiny_hit]})
    with patch.object(asset_service.settings, "pixabay_api_key", "real-looking-key"):
        with patch("httpx.get", return_value=resp):
            results = search_pixabay("indian man tired after work")
    assert len(results) == 1
    assert results[0].url == "http://x/good.jpg"


# --- Weak (non-zero but too few) candidates should still trigger broadening,
# and the original candidates must be kept, not discarded (Part A9). ---
def test_weak_nonzero_candidates_trigger_broadening_and_are_combined():
    from app.models.product import AssetCandidate

    weak_candidate = AssetCandidate(source="pexels", url="http://x/first.jpg", thumbnail_url="http://x/t1.jpg", width=1000, height=1500)
    broadened_candidate = AssetCandidate(source="pixabay", url="http://x/second.jpg", thumbnail_url="http://x/t2.jpg", width=1000, height=1500)

    payload = AssetSourcingInput(line_id="hook", visual_tags=["very specific indian man tag"])

    with patch.object(asset_service, "search_pexels", side_effect=[[weak_candidate], []]):
        with patch.object(asset_service, "search_pixabay", side_effect=[[], [broadened_candidate]]):
            with patch.object(asset_service, "broaden_tag", return_value="broader tag") as mock_broaden:
                with patch.object(asset_service, "rank_with_vision", return_value=(1, "best match")) as mock_rank:
                    result = source_asset_for_line(payload)

    mock_broaden.assert_called_once_with("very specific indian man tag")
    # Both the original weak candidate AND the broadened one were passed to ranking.
    ranked_candidates = mock_rank.call_args[0][1]
    assert len(ranked_candidates) == 2
    assert {c.url for c in ranked_candidates} == {"http://x/first.jpg", "http://x/second.jpg"}
    assert result.candidate.url == "http://x/second.jpg"
    assert result.broadened is True


# --- exclude_urls: avoid repeating an asset already used on another line ---
def test_exclude_urls_steers_away_from_already_used_candidate():
    from app.models.product import AssetCandidate

    used_elsewhere = AssetCandidate(source="pexels", url="http://x/used.jpg", thumbnail_url="http://x/t1.jpg", width=1000, height=1500)
    fresh = AssetCandidate(source="pexels", url="http://x/fresh.jpg", thumbnail_url="http://x/t2.jpg", width=1000, height=1500)

    payload = AssetSourcingInput(line_id="body_1", visual_tags=["indian man tired"], exclude_urls=["http://x/used.jpg"])
    with patch.object(asset_service, "search_pexels", return_value=[used_elsewhere, fresh]):
        with patch.object(asset_service, "search_pixabay", return_value=[]):
            with patch.object(asset_service, "rank_with_vision", return_value=(0, "best match")) as mock_rank:
                result = source_asset_for_line(payload)

    # The already-used candidate must not even be offered to ranking.
    ranked_candidates = mock_rank.call_args[0][1]
    assert len(ranked_candidates) == 1
    assert ranked_candidates[0].url == "http://x/fresh.jpg"
    assert result.candidate.url == "http://x/fresh.jpg"


def test_exclude_urls_falls_back_to_full_list_when_everything_is_excluded():
    from app.models.product import AssetCandidate

    only_option = AssetCandidate(source="pexels", url="http://x/only.jpg", thumbnail_url="http://x/t1.jpg", width=1000, height=1500)

    payload = AssetSourcingInput(line_id="body_1", visual_tags=["indian man tired"], exclude_urls=["http://x/only.jpg"])
    with patch.object(asset_service, "search_pexels", return_value=[only_option]):
        with patch.object(asset_service, "search_pixabay", return_value=[]):
            with patch.object(asset_service, "rank_with_vision", return_value=(0, "best match")):
                result = source_asset_for_line(payload)

    # A duplicate is still better than no image at all.
    assert result.candidate is not None
    assert result.candidate.url == "http://x/only.jpg"


# --- Product-aware asset priority (Part B: Real Product Asset System) ---


def test_product_intro_section_uses_real_product_asset_without_calling_providers():
    payload = AssetSourcingInput(
        line_id="body_0",
        visual_tags=["Indian kitchen table with product"],
        section="product_intro",
        product_context=_product_context(),
    )
    with patch.object(asset_service, "search_pexels") as mock_pexels:
        with patch.object(asset_service, "search_pixabay") as mock_pixabay:
            with patch.object(asset_service, "rank_with_vision") as mock_rank:
                with patch.object(asset_service, "_real_image_dimensions", return_value=(1080, 1920)):
                    result = source_asset_for_line(payload)
    mock_pexels.assert_not_called()
    mock_pixabay.assert_not_called()
    mock_rank.assert_not_called()  # never re-ranked/second-guessed by Vision
    assert result.candidate is not None
    assert result.candidate.source == "product_library"
    # Absolute (backend_base_url-prefixed) so both the browser preview and
    # Remotion's render subprocess can actually fetch it — not just requests
    # made from the backend's own origin.
    assert result.candidate.url == "http://127.0.0.1:8000/product-uploads/prod123/pack.png"
    assert result.provider_error is False


def test_cta_section_uses_real_product_asset():
    payload = AssetSourcingInput(
        line_id="cta", visual_tags=["hero shot"], section="cta", product_context=_product_context()
    )
    with patch.object(asset_service, "_real_image_dimensions", return_value=(1080, 1920)):
        result = source_asset_for_line(payload)
    assert result.candidate.source == "product_library"


def test_ingredients_section_uses_real_product_asset():
    payload = AssetSourcingInput(
        line_id="body_1", visual_tags=["fennel and cardamom"], section="ingredients", product_context=_product_context()
    )
    with patch.object(asset_service, "_real_image_dimensions", return_value=(1080, 1920)):
        result = source_asset_for_line(payload)
    assert result.candidate.source == "product_library"


def test_lifestyle_scene_still_uses_stock_even_with_product_selected():
    """Section 'problem' (a lifestyle/human moment) must NOT be hijacked by
    the product asset just because a product is selected for the project —
    only product/ingredient-shaped scenes take priority."""
    real_candidate_source = "pexels"
    payload = AssetSourcingInput(
        line_id="hook",
        visual_tags=["Indian man tired after work"],
        section="problem",
        product_context=_product_context(),
    )
    from app.models.product import AssetCandidate

    stock_candidate = AssetCandidate(source=real_candidate_source, url="http://x/stock.jpg", thumbnail_url="http://x/t.jpg", width=1000, height=1500)
    with patch.object(asset_service, "search_pexels", return_value=[stock_candidate]):
        with patch.object(asset_service, "search_pixabay", return_value=[]):
            with patch.object(asset_service, "rank_with_vision", return_value=(0, "matches the lifestyle scene")):
                result = source_asset_for_line(payload)
    assert result.candidate.source == "pexels"


def test_product_name_mentioned_in_visual_tags_triggers_priority_even_outside_product_sections():
    payload = AssetSourcingInput(
        line_id="body_2",
        visual_tags=["Aayush Wellness Herbal Masala on a wooden table"],
        section="benefits",  # not in the hard-coded product-required section set
        product_context=_product_context(),
    )
    with patch.object(asset_service, "_real_image_dimensions", return_value=(1080, 1920)):
        result = source_asset_for_line(payload)
    assert result.candidate.source == "product_library"


def test_no_product_context_falls_through_to_stock_unchanged():
    from app.models.product import AssetCandidate

    stock_candidate = AssetCandidate(source="pexels", url="http://x/stock.jpg", thumbnail_url="http://x/t.jpg", width=1000, height=1500)
    payload = AssetSourcingInput(line_id="body_0", visual_tags=["Indian kitchen"], section="product_intro")
    with patch.object(asset_service, "search_pexels", return_value=[stock_candidate]):
        with patch.object(asset_service, "search_pixabay", return_value=[]):
            with patch.object(asset_service, "rank_with_vision", return_value=(0, "ok")):
                result = source_asset_for_line(payload)
    assert result.candidate.source == "pexels"


def test_product_selected_but_no_primary_asset_falls_through_to_stock():
    from app.models.product import AssetCandidate

    stock_candidate = AssetCandidate(source="pexels", url="http://x/stock.jpg", thumbnail_url="http://x/t.jpg", width=1000, height=1500)
    payload = AssetSourcingInput(
        line_id="body_0",
        visual_tags=["kitchen"],
        section="product_intro",
        product_context=_product_context(primary_asset_url=None),
    )
    with patch.object(asset_service, "search_pexels", return_value=[stock_candidate]):
        with patch.object(asset_service, "search_pixabay", return_value=[]):
            with patch.object(asset_service, "rank_with_vision", return_value=(0, "ok")):
                result = source_asset_for_line(payload)
    assert result.candidate.source == "pexels"
