"""Tests for SERVICE_ACCOUNTS config parsing."""

from backend.core.config import parse_service_accounts


class TestServiceAccountsConfig:
    def test_parse_comma_separated(self):
        assert parse_service_accounts("partner-a:sk-aaa,partner-b:sk-bbb") == {
            "partner-a": "sk-aaa",
            "partner-b": "sk-bbb",
        }

    def test_empty_returns_empty_dict(self):
        assert parse_service_accounts("") == {}

    def test_malformed_line_skipped(self):
        assert parse_service_accounts("valid:secret,no-separator,another:val") == {
            "valid": "secret",
            "another": "val",
        }

    def test_whitespace_handling(self):
        assert parse_service_accounts(" a : b , c : d ") == {"a": "b", "c": "d"}
