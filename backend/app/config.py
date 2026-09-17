from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    pexels_api_key: str = ""
    pixabay_api_key: str = ""
    huggingface_api_token: str = ""

    remotion_project_dir: str = "../remotion"
    renders_output_dir: str = "./renders"
    audio_output_dir: str = "./audio"
    motion_output_dir: str = "./motion"
    reference_uploads_dir: str = "./reference_uploads"
    product_uploads_dir: str = "./product_uploads"
    max_product_upload_mb: int = 60
    # Remotion's headless-Chrome render process fetches image/video URLs over
    # real HTTP — a relative /product-uploads/... URL (from a Product Library
    # asset) needs resolving to an absolute one it can actually reach before
    # being handed to Remotion. Same host:port this backend itself listens on
    # in local dev; override via .env for a non-default deployment.
    backend_base_url: str = "http://127.0.0.1:8000"

    hf_motion_model: str = "Wan-AI/Wan2.1-I2V-14B-480P"
    hf_motion_provider: str = "wavespeed"

    gemini_api_key: str = ""
    gemini_image_model: str = "gemini-2.5-flash-image"
    gemini_text_model: str = "gemini-flash-latest"
    visuals_output_dir: str = "./visuals"

    openrouter_api_key: str = ""
    openrouter_text_model: str = ""
    openrouter_image_model: str = ""
    # Hybrid model routing (Option C) — each is optional; an unset value
    # falls back to openrouter_text_model, so existing deployments keep
    # working unchanged if these are never configured. Use the .creative_model
    # / .final_script_model / .validation_model properties below in business
    # logic, never these raw fields directly, so the fallback is never
    # duplicated across call sites.
    openrouter_creative_model: str = ""
    openrouter_final_script_model: str = ""
    openrouter_validation_model: str = ""
    references_dir: str = "./references"
    # Kill switch for actual image-generation provider calls (script/scene
    # text generation — including ai_image_prompt/visual_direction — is
    # unaffected either way). Defaults to enabled; set to false in .env to
    # stop image API usage/cost while iterating on script generation.
    image_generation_enabled: bool = True

    max_reference_upload_mb: int = 30
    jina_reader_timeout_seconds: int = 25

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def creative_model(self) -> str:
        """High-volume creative exploration (insight, territory, architecture
        selection, premise, hooks, beat outline) — cheap/fast model."""
        return self.openrouter_creative_model or self.openrouter_text_model

    @property
    def final_script_model(self) -> str:
        """The final creative-director evaluation, the main script-writing
        call, and the one "necessary rewrite" a quality/architecture gate
        triggers — the highest-value, lowest-volume calls."""
        return self.openrouter_final_script_model or self.openrouter_text_model

    @property
    def validation_model(self) -> str:
        """Cheap post-generation semantic validation (the quality gate's LLM
        check) — never used in place of a deterministic Python check."""
        return self.openrouter_validation_model or self.openrouter_text_model


settings = Settings()
 