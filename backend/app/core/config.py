from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central app configuration. All values are read from environment
    variables (or a .env file) — never hardcode secrets here.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "AegisFlow SOAR Platform"
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql://aegisflow:aegisflow_dev_pw@localhost:5432/aegisflow"

    # Auth
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AI provider — "ollama" or "gemini"
    AI_PROVIDER: str = "ollama"
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"
    GEMINI_API_KEY: str = ""

    # Threat intel APIs (free tiers) — leave blank to use the simulator
    VIRUSTOTAL_API_KEY: str = ""
    ABUSEIPDB_API_KEY: str = ""


settings = Settings()
