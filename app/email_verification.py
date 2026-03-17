"""Email verification: signed tokens and sending via Amazon SES."""
import logging
import sys
import boto3
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

logger = logging.getLogger(__name__)


def make_verification_token(secret_key: str, username: str, email: str, max_age_seconds: int = 86400) -> str:
    """Generate a signed token (valid 24h by default)."""
    s = URLSafeTimedSerializer(secret_key)
    return s.dumps({"username": username, "email": email}, salt="email-verify")


def verify_token(secret_key: str, token: str, max_age_seconds: int = 86400) -> tuple[str | None, str | None]:
    """Return (username, email) if token valid, else (None, None)."""
    s = URLSafeTimedSerializer(secret_key)
    try:
        data = s.loads(token, salt="email-verify", max_age=max_age_seconds)
        return data.get("username"), data.get("email")
    except (BadSignature, SignatureExpired):
        return None, None


def send_verification_email(
    from_email: str,
    to_email: str,
    username: str,
    verify_url: str,
    region: str = "us-east-1",
) -> bool:
    """Send verification email via Amazon SES. Returns True if sent successfully.
    Uses default credentials (e.g. EC2 instance role). From address must be verified in SES.
    """
    if not from_email or not from_email.strip():
        return False
    html = f"""
    <p>Hi {username},</p>
    <p>Thanks for signing up for FreeFits. Please verify your email by clicking the link below:</p>
    <p><a href="{verify_url}">{verify_url}</a></p>
    <p>This link expires in 24 hours. If you didn't create an account, you can ignore this email.</p>
    <p>— FreeFits</p>
    """.strip()
    try:
        logger.info("SES: sending verification email to %s (from=%s region=%s)", to_email, from_email, region)
        client = boto3.client("ses", region_name=region)
        client.send_email(
            Source=from_email.strip(),
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": "Verify your FreeFits email", "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html, "Charset": "UTF-8"},
                },
            },
        )
        return True
    except Exception as e:
        logger.warning("SES send_verification_email failed: %s", e, exc_info=True)
        # Also print to stderr so it shows in journalctl even if logging isn't configured
        print("FreeFits SES ERROR:", type(e).__name__, str(e), file=sys.stderr, flush=True)
        return False
