import hashlib
import hmac


def verify_github_signature(*, secret: str, payload: bytes, signature: str | None) -> bool:
    """Verify the GitHub X-Hub-Signature-256 value against the raw request body."""
    if not secret or not signature:
        return False

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_dashboard_token(*, expected: str, supplied: str | None) -> bool:
    """Constant-time token comparison for optional dashboard protection."""
    if not expected:
        return True
    if not supplied:
        return False
    return hmac.compare_digest(expected, supplied)
