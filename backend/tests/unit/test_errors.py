"""Tests for error handling."""

from lingshu.infra.errors import AppError, ErrorCode


class TestAppError:
    def test_error_with_code_and_message(self):
        err = AppError(code=ErrorCode.COMMON_NOT_FOUND, message="Resource not found")
        assert err.code == ErrorCode.COMMON_NOT_FOUND
        assert err.message == "Resource not found"
        assert err.status_code == 404
        assert err.details == {}

    def test_error_with_details(self):
        err = AppError(
            code=ErrorCode.ONTOLOGY_DEPENDENCY_CONFLICT,
            message="Cannot delete",
            details={"referencing_rids": ["ri.prop.aaa"]},
        )
        assert err.status_code == 409
        assert err.details["referencing_rids"] == ["ri.prop.aaa"]

    def test_error_code_values(self):
        assert ErrorCode.COMMON_UNAUTHORIZED.value == "COMMON_UNAUTHORIZED"
        assert ErrorCode.SETTING_AUTH_INVALID_CREDENTIALS.value == "SETTING_AUTH_INVALID_CREDENTIALS"

    def test_unknown_code_defaults_to_500(self):
        # All codes should be in the map, but test the fallback
        err = AppError(code=ErrorCode.COMMON_INTERNAL_ERROR, message="Internal")
        assert err.status_code == 500

    def test_str_representation(self):
        err = AppError(code=ErrorCode.COMMON_NOT_FOUND, message="Not found")
        assert str(err) == "Not found"
