from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Telegram(BaseModel):
    token: str = Field(..., description="Telegram Bot Token")


class Database(BaseModel):
    engine: str = Field("sqlite", description="Database engine: sqlite or postgresql")
    name: str = Field("db.sqlite3", description="Database name or file")
    user: str = Field("user", description="Database user")
    password: str = Field("password", description="Database password")
    host: str = Field("localhost", description="Database host")
    port: int = Field(5432, description="Database port")
    url: str | None = None  # Optional: explicit SQLAlchemy URL

    def build_url(self) -> str:
        if self.url:
            return self.url
        if self.engine == "sqlite":
            return f"sqlite:///{self.name}"
        return f"postgresql+psycopg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class LLM(BaseModel):
    openai_api_key: str | None = None


class BaseConfiguration(BaseSettings):
    telegram: Telegram
    database: Database = Database()
    llm: LLM = LLM()
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )
