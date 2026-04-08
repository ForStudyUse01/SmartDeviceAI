from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SmartDeviceAI API"
    mongodb_uri: str = Field(default="mongodb://127.0.0.1:27017", alias="MONGODB_URI")
    mongodb_db: str = Field(default="ai_dashboard", alias="MONGODB_DB")
    jwt_secret: str = Field(default="change-this-secret", alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_expiration_days: int = 7
    cors_origin: str = Field(default="http://127.0.0.1:5173", alias="CORS_ORIGIN")
    cors_origins: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173,http://192.168.1.10:5173",
        alias="CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        values = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
        if self.cors_origin and self.cors_origin not in values:
            values.append(self.cors_origin)
        return values or ["http://127.0.0.1:5173", "http://localhost:5173"]


settings = Settings()
