from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import Optional


class Settings(BaseSettings):
    # JWT Settings
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Guidini Pay Settings
    GUIDINI_APP_KEY: Optional[str] = None
    GUIDINI_API_KEY: Optional[str] = None

    # Twilio Settings
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None

    # Database
    DATABASE_URL: str

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = []
    BACKEND_CORS_ORIGIN_REGEX: str = (
        r"https?://(localhost(:\d+)?|.*\.mayda\.app|.*\.vercel\.app)"
    )

    # Environment
    ENVIRONMENT: str = "development"

    # AI Services
    RECOMMENDATION_SERVICE_URL: str = "http://recommendation:8101"
    SEARCH_SERVICE_URL: str = "http://search-llm:8102"
    INVENTORY_SERVICE_URL: str = "http://inventory:8103"
    VOICE_SERVICE_URL: str = "http://voice-chef:8104"
    ANOMALY_SERVICE_URL: str = "http://anomaly:8105"
    SERVICE_TOKEN: str = ""

    @model_validator(mode="after")
    def _validate_service_token(self) -> "Settings":
        if not self.SERVICE_TOKEN:
            raise ValueError("SERVICE_TOKEN must be set — add it to your .env file")
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
