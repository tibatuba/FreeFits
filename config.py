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
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    MONGO_URI = os.getenv("MONGO_URI", "")
    GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
    IMAGGA_API_KEY = os.getenv("IMAGGA_API_KEY", "")
    IMAGGA_API_SECRET = os.getenv("IMAGGA_API_SECRET", "")
    # api4ai Fashion API
    API4AI_API_KEY = os.getenv("API4AI_API_KEY", "")
    # AWS Rekognition (RECOMMENDED - free tier: 5,000 images/month, reliable, part of AWS)
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")  # Default region
    # Set to 'rekognition' for AWS Rekognition (recommended), 'api4ai', or 'imagga'
    IMAGE_VALIDATION_API = os.getenv("IMAGE_VALIDATION_API", "rekognition")  # Default to AWS Rekognition
    # AWS S3 Configuration for image storage
    AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME", "")
    AWS_S3_REGION = os.getenv("AWS_S3_REGION", "")  # Optional, defaults to AWS_REGION if not set
    # Admin: username that can access /admin/listings to delete any listing (set in .env)
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
    # Email verification via Amazon SES (must verify sender in SES; From address required)
    VERIFICATION_FROM_EMAIL = os.getenv("VERIFICATION_FROM_EMAIL", "")
    # Behind nginx / ALB: trust X-Forwarded-* (set TRUST_PROXY=1 on production server)
    TRUST_PROXY = _env_truthy("TRUST_PROXY")
    # Trusted X-Forwarded-For entries from the right (ALB + nginx => 2). Use 1 if only nginx.
    TRUST_PROXY_HOPS = _proxy_hops()
    # Send session cookie with Secure flag (HTTPS only). Defaults on when TRUST_PROXY is on.
    SESSION_COOKIE_SECURE = (
        _env_truthy("SESSION_COOKIE_SECURE")
        if os.getenv("SESSION_COOKIE_SECURE", "").strip() != ""
        else TRUST_PROXY
    )


def get_config():
    return Config()


