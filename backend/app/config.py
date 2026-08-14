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

    hf_motion_model: str = "Wan-AI/Wan2.1-I2V-14B-480P"
    hf_motion_provider: str = "wavespeed"

    gemini_api_key: str = ""
    gemini_image_model: str = "gemini-2.5-flash-image"
    # "gemini-flash-latest" handles the high-frequency/latency-sensitive text
    # calls (structuring, scripts, rewrites, etc). "gemini-pro-latest" is used
    # only for compliance auditing, preserving the original design intent of
    # an independent, higher-scrutiny model reviewing the writer's output —
    # note it can't run with thinking disabled, so it's slower by design.
    gemini_text_model: str = "gemini-flash-latest"
    gemini_compliance_model: str = "gemini-pro-latest"
    visuals_output_dir: str = "./visuals"

    max_reference_upload_mb: int = 30
    jina_reader_timeout_seconds: int = 25

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
 