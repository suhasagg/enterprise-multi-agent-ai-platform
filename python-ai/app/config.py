from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-5.4"
    embedding_model: str = "text-embedding-3-small"
    database_url: str = "postgresql+asyncpg://agent:agent@localhost:5432/agents"
    redis_url: str = "redis://localhost:6379/0"
    java_mcp_url: str = "http://localhost:8081/mcp"
    log_level: str = "INFO"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
