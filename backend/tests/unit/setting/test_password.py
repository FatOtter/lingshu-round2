"""Tests for password hashing and validation."""

from lingshu.setting.auth.password import (
    hash_password,
    validate_password_strength,
    verify_password,
)


class TestHashPassword:
    def test_hash_returns_bcrypt(self):
        h = hash_password("testpass123")
        assert h.startswith("$2b$12$")

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("testpass123")
        h2 = hash_password("testpass123")
        assert h1 != h2  # bcrypt uses random salt


class TestVerifyPassword:
    def test_correct_password(self):
        h = hash_password("mypassword1")
        assert verify_password("mypassword1", h) is True

    def test_wrong_password(self):
        h = hash_password("mypassword1")
        assert verify_password("wrongpassword1", h) is False


class TestPasswordStrength:
    def test_valid_password(self):
        assert validate_password_strength("mypassword1") is None

    def test_too_short(self):
        result = validate_password_strength("ab1")
        assert result is not None
        assert "8 characters" in result

    def test_no_digit(self):
        result = validate_password_strength("abcdefghi")
        assert result is not None
        assert "letter and one number" in result

    def test_no_letter(self):
        result = validate_password_strength("12345678")
        assert result is not None
        assert "letter and one number" in result

    def test_exactly_eight_chars(self):
        assert validate_password_strength("abcdefg1") is None
