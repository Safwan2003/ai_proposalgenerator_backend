
from pydantic_settings import BaseSettings

from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str
    API_V1_STR: str
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    GROQ_API_KEY: str
    PIXABAY_API_KEY: str

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
