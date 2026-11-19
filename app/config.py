"""Application configuration loaded from .env."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SERVICE_URL: str = os.environ.get(
        "SERVICE_URL",
        "https://api.aws-c1.dcls.saas.ibm.com/20260519-2040-0213-6007-20006a73b966",
    )
    API_KEY: str = os.environ.get("API_KEY", "")
    PORT: int = int(os.environ.get("PORT", "5000"))
    MAX_CONTENT_LENGTH: int = 50 * 1024 * 1024  # 50 MB upload limit


config = Config()
