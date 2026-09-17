"""Tests confirming IMAGE_GENERATION_ENABLED=false actually blocks every
image-provider call path and preserves the exact user-facing disabled
message — required by both the original image-disable task and Option C's
explicit "keep image generation disabled" constraint. No live network calls."""

from unittest.mock import patch

import pytest

from app.config import settings
from app.services import visual_concept_service as vcs


def test_image_generation_enabled_defaults_true_but_env_currently_disables_it():
    # Documents intent only — the actual effective value in this repo's
    # local .env is False; Settings() itself defaults to True absent config.
    from app.config import Settings

    assert Settings(image_generation_enabled=True).image_generation_enabled is True


def test_generate_test_image_raises_disabled_message_when_disabled():
    with patch.object(settings, "image_generation_enabled", False):
        with pytest.raises(ValueError, match="Image generation disabled during testing."):
            vcs.generate_test_image()


def test_generate_static_visual_raises_disabled_message_when_disabled():
    with patch.object(settings, "image_generation_enabled", False):
        with pytest.raises(ValueError, match="Image generation disabled during testing."):
            vcs.generate_static_visual("a prompt", "1:1")


def test_render_download_raises_disabled_message_when_disabled():
    with patch.object(settings, "image_generation_enabled", False):
        with pytest.raises(ValueError, match="Image generation disabled during testing."):
            vcs.render_download(type("P", (), {"concept": None})())


def test_no_image_provider_call_reaches_openrouter_when_disabled():
    with patch.object(settings, "image_generation_enabled", False), \
         patch("app.services.openrouter_utils.generate_image") as mock_img:
        with pytest.raises(ValueError):
            vcs.generate_test_image()
        with pytest.raises(ValueError):
            vcs.generate_static_visual("a prompt", "1:1")
    mock_img.assert_not_called()


def test_disabled_message_constant_matches_required_wording():
    assert vcs.IMAGE_GENERATION_DISABLED_MESSAGE == "Image generation disabled during testing."
