
from pydantic_settings import BaseSettings

from typing import List, Optional

class Settings(BaseSettings):
    PROJECT_NAME: str
    API_V1_STR: str
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]
    GROQ_API_KEY: str
    PIXABAY_API_KEY: str
    GROQ_DIAGRAM_MODEL_NAME: Optional[str] = None
    GROQ_DEFAULT_MODEL_NAME: Optional[str] = None
    GROQ_MODEL_NAME: Optional[str] = None


    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
