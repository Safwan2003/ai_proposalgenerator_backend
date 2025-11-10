
from pydantic_settings import BaseSettings

from typing import List, Optional

class Settings(BaseSettings):
    PROJECT_NAME: str
    API_V1_STR: str
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]
    GROQ_API_KEY: str
    PIXABAY_API_KEY: str
    PEXELS_API_KEY: Optional[str] = None
    GROQ_MODEL_DIAGRAM: str = "mixtral-8x7b-32768"
    GROQ_MODEL_DEFAULT: str = "llama-3.1-8b-instant"

    # Database settings
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "proposal_generator"

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+asyncmy://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
