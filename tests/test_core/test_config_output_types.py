"""Tests for OUTPUT_TYPES configuration."""

from backend.core.config import Settings


class TestOutputTypes:
    def test_default_is_raw_model(self):
        s = Settings(_env_file=None)
        assert s.output_types == ["raw_model"]

    def test_comma_separated_string_parsed_to_list(self):
        s = Settings(_env_file=None, output_types="raw_model,spz,sog")
        assert s.output_types == ["raw_model", "spz", "sog"]

    def test_single_value(self):
        s = Settings(_env_file=None, output_types="raw_model")
        assert s.output_types == ["raw_model"]

    def test_empty_string_parsed_to_empty_list(self):
        s = Settings(_env_file=None, output_types="")
        assert s.output_types == []

    def test_invalid_value_raises_error(self):
        import pytest

        with pytest.raises(ValueError, match="invalid output type"):
            Settings(_env_file=None, output_types="invalid")
