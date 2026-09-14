"""Product-aware script generation — verifies the additive
_product_library_block() helper: empty (byte-for-byte no-op) when no
product is selected, and correctly surfaces approved/prohibited claims,
tone, CTA, and reference-script style-only guidance when one is."""

from app.models.product import ProductContext
from app.services.script_service import _product_library_block


def _context(**overrides) -> ProductContext:
    defaults = dict(
        product_id="p1",
        name="Aayush Wellness Herbal Masala",
        category="herbal_health",
        short_description="",
        usp="100% tobacco-free herbal blend",
        target_audience="Adults seeking a tobacco-free alternative",
        primary_problem="",
        positioning="",
        ingredients=["fennel", "cardamom"],
        benefits=["tobacco-free"],
        approved_claims=["tobacco-free herbal alternative"],
        prohibited_claims=["cures addiction", "medically proven"],
        mandatory_wording="",
        preferred_tone="warm, trustworthy",
        preferred_language="",
        cta_text="Try it today",
        winning_hooks=["Ready for a tobacco-free habit?"],
        reference_script_excerpts=["OLD_SCRIPT_TEXT_EXCERPT"],
        primary_asset_url="/product-uploads/p1/pack.png",
    )
    defaults.update(overrides)
    return ProductContext(**defaults)


def test_no_product_context_produces_empty_block():
    assert _product_library_block(None) == ""


def test_product_context_includes_approved_and_prohibited_claims():
    block = _product_library_block(_context())
    assert "Aayush Wellness Herbal Masala" in block
    assert "tobacco-free herbal alternative" in block
    assert "APPROVED CLAIMS" in block
    assert "PROHIBITED CLAIMS" in block
    assert "cures addiction" in block
    assert "medically proven" in block


def test_reference_scripts_are_marked_style_only_not_verbatim():
    block = _product_library_block(_context())
    assert "OLD_SCRIPT_TEXT_EXCERPT" in block
    assert "Do NOT copy sentences, claims, or the exact creative idea verbatim" in block


def test_missing_optional_fields_are_omitted_cleanly():
    block = _product_library_block(_context(usp="", winning_hooks=[], mandatory_wording="", reference_script_excerpts=[]))
    assert "USP:" not in block
    assert "Winning hooks" not in block
    assert "Mandatory wording" not in block
    assert "reference script excerpts" not in block.lower()
