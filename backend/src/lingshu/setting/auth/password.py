"""Password hashing and verification using bcrypt."""

import re

import bcrypt

PASSWORD_MIN_LENGTH = 8
PASSWORD_PATTERN = re.compile(r"^(?=.*[a-zA-Z])(?=.*\d).{8,}$")


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt (cost 12)."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def validate_password_strength(password: str) -> str | None:
    """Validate password meets strength requirements.

    Returns None if valid, or an error message string.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
    if not PASSWORD_PATTERN.match(password):
        return "Password must contain at least one letter and one number"
    return None
