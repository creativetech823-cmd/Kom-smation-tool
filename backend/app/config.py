from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str
    claude_structuring_model: str = "claude-sonnet-5"
    claude_compliance_model: str = "claude-haiku-4-5-20251001"

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

    max_reference_upload_mb: int = 30
    jina_reader_timeout_seconds: int = 25

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
 