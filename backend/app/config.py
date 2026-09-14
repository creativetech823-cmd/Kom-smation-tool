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
    references_dir: str = "./references"
    # Kill switch for actual image-generation provider calls (script/scene
    # text generation — including ai_image_prompt/visual_direction — is
    # unaffected either way). Defaults to enabled; set to false in .env to
    # stop image API usage/cost while iterating on script generation.
    image_generation_enabled: bool = True

    max_reference_upload_mb: int = 30
    jina_reader_timeout_seconds: int = 25

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
 