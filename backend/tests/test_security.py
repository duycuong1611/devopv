import hashlib
import hmac

from app.security import verify_dashboard_token, verify_github_signature


def test_valid_github_signature_is_accepted() -> None:
    secret = "test-secret"
    payload = b'{"hello":"relayops"}'
    signature = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()

    assert verify_github_signature(
        secret=secret,
        payload=payload,
        signature=signature,
    )


def test_invalid_github_signature_is_rejected() -> None:
    assert not verify_github_signature(
        secret="test-secret",
        payload=b"payload",
        signature="sha256=not-a-real-signature",
    )


def test_dashboard_token_is_optional_when_unconfigured() -> None:
    assert verify_dashboard_token(expected="", supplied=None)


def test_dashboard_token_requires_exact_match() -> None:
    assert verify_dashboard_token(expected="dashboard-secret", supplied="dashboard-secret")
    assert not verify_dashboard_token(expected="dashboard-secret", supplied="wrong")
