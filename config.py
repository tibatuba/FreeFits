import os


def _env_truthy(name: str, default: str = "") -> bool:
    v = os.getenv(name, default)
    return (v or "").strip().lower() in ("1", "true", "yes", "on")


def _proxy_hops() -> int:
    raw = os.getenv("TRUST_PROXY_HOPS", "2") or "2"
    try:
        n = int(raw)
    except ValueError:
        n = 2
    return max(1, min(5, n))


class Config:
    """Load settings from the environment when instantiated (not at import time).

    Always use get_config() after load_dotenv so .env values are visible.
    """

    def __init__(self) -> None:
        self.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
        self.MONGO_URI = os.getenv("MONGO_URI", "")
        self.GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
        self.IMAGGA_API_KEY = os.getenv("IMAGGA_API_KEY", "")
        self.IMAGGA_API_SECRET = os.getenv("IMAGGA_API_SECRET", "")
        self.API4AI_API_KEY = os.getenv("API4AI_API_KEY", "")
        self.AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
        self.AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        self.AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
        self.IMAGE_VALIDATION_API = os.getenv("IMAGE_VALIDATION_API", "rekognition")
        self.AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME", "")
        self.AWS_S3_REGION = os.getenv("AWS_S3_REGION", "")
        self.ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
        self.VERIFICATION_FROM_EMAIL = os.getenv("VERIFICATION_FROM_EMAIL", "")
        self.TRUST_PROXY = _env_truthy("TRUST_PROXY")
        self.TRUST_PROXY_HOPS = _proxy_hops()
        if os.getenv("SESSION_COOKIE_SECURE", "").strip() != "":
            self.SESSION_COOKIE_SECURE = _env_truthy("SESSION_COOKIE_SECURE")
        else:
            self.SESSION_COOKIE_SECURE = self.TRUST_PROXY
        self.SESSION_COOKIE_HTTPONLY = True
        self.SESSION_COOKIE_SAMESITE = "Lax"


def get_config() -> Config:
    return Config()