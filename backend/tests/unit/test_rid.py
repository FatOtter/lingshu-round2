"""Tests for RID generation and validation."""

import pytest

from lingshu.infra.rid import generate_rid, parse_rid, validate_rid, validate_rid_type


class TestGenerateRid:
    def test_generates_valid_format(self):
        rid = generate_rid("obj")
        assert rid.startswith("ri.obj.")
        assert validate_rid(rid)

    def test_generates_unique_ids(self):
        rids = {generate_rid("user") for _ in range(100)}
        assert len(rids) == 100

    def test_all_resource_types(self):
        for rtype in ["obj", "link", "iface", "action", "shprop", "prop", "snap",
                       "conn", "func", "workflow", "session", "model", "skill",
                       "mcp", "subagent", "user", "tenant"]:
            rid = generate_rid(rtype)
            assert rid.startswith(f"ri.{rtype}.")

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown resource type"):
            generate_rid("invalid")


class TestValidateRid:
    def test_valid_rid(self):
        assert validate_rid("ri.obj.550e8400-e29b-41d4-a716-446655440000")

    def test_invalid_prefix(self):
        assert not validate_rid("rx.obj.550e8400-e29b-41d4-a716-446655440000")

    def test_invalid_uuid(self):
        assert not validate_rid("ri.obj.not-a-uuid")

    def test_empty_string(self):
        assert not validate_rid("")

    def test_uppercase_rejected(self):
        assert not validate_rid("ri.OBJ.550e8400-e29b-41d4-a716-446655440000")


class TestParseRid:
    def test_parse_valid(self):
        rtype, uid = parse_rid("ri.user.550e8400-e29b-41d4-a716-446655440000")
        assert rtype == "user"
        assert uid == "550e8400-e29b-41d4-a716-446655440000"

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid RID format"):
            parse_rid("bad-rid")


class TestValidateRidType:
    def test_matching_type(self):
        rid = generate_rid("obj")
        assert validate_rid_type(rid, "obj")

    def test_wrong_type(self):
        rid = generate_rid("obj")
        assert not validate_rid_type(rid, "user")

    def test_invalid_rid(self):
        assert not validate_rid_type("bad", "obj")
