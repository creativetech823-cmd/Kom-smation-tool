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

    hf_motion_model: str = "Wan-AI/Wan2.1-I2V-14B-480P"
    hf_motion_provider: str = "wavespeed"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
