from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str
    gemini_model: str = "gemini-3.5-flash-lite"
    temperature: float = 0.1

    input_csv: Path = BASE_DIR / "data" / "input_requests.csv"
    output_dir: Path = BASE_DIR / "output"

    max_retries: int = 2
    retry_backoff_seconds: float = 5.0


settings = Settings()