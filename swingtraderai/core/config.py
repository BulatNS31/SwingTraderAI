from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	model_config = SettingsConfigDict(
		env_file=".env", env_ignore_empty=True, extra="ignore"
	)

	SECRET_KEY: str
	ALGORITHM: str
	DATABASE_URL: str
	REDIS_URL: str
	ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
	REFRESH_TOKEN_EXPIRE_DAYS: int = 7
	CORS_ALLOWED_ORIGINS: list[str] = []


settings = Settings()
