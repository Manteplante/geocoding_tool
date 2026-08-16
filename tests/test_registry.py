"""Provider selection and the guards that stop a backend arming itself."""

from __future__ import annotations

import pytest

from geocoding_tool.base import GeocoderConfigError, UnknownProviderError
from geocoding_tool.registry import PROVIDERS, get_geocoder


def test_unknown_provider_lists_the_valid_ones():
    with pytest.raises(UnknownProviderError, match="nominatim, google"):
        get_geocoder("mapbox")


def test_provider_name_is_case_insensitive(monkeypatch, cache):
    monkeypatch.setenv("NOMINATIM_USER_AGENT", "test-suite/1.0 (ci@example.com)")
    assert get_geocoder("  NOMINATIM  ", cache=cache).name == "nominatim"


class TestNominatimGuards:
    def test_missing_user_agent_is_rejected(self, cache):
        with pytest.raises(GeocoderConfigError, match="unique User-Agent"):
            get_geocoder("nominatim", cache=cache)

    def test_placeholder_user_agent_is_rejected(self, cache):
        with pytest.raises(GeocoderConfigError, match="unique User-Agent"):
            get_geocoder(
                "nominatim",
                user_agent="geocoding-tool/0.1 (you@example.com)",
                cache=cache,
            )

    def test_rate_limit_stays_above_one_per_second(self, monkeypatch, cache):
        """The OSM usage policy caps clients at 1 request/second."""
        monkeypatch.setenv("NOMINATIM_USER_AGENT", "test-suite/1.0 (ci@example.com)")
        geocoder = get_geocoder("nominatim", cache=cache)
        assert geocoder._call.min_delay_seconds > 1.0


class TestGoogleGuards:
    def test_api_key_alone_does_not_arm_the_backend(self, monkeypatch, cache):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake-key")
        with pytest.raises(GeocoderConfigError, match="GOOGLE_GEOCODING_CONFIRM"):
            get_geocoder("google", cache=cache)

    def test_confirmation_without_key_is_rejected(self, monkeypatch, cache):
        monkeypatch.setenv("GOOGLE_GEOCODING_CONFIRM", "1")
        with pytest.raises(GeocoderConfigError, match="GOOGLE_MAPS_API_KEY"):
            get_geocoder("google", cache=cache)

    def test_both_signals_present_builds_the_backend(self, monkeypatch, cache):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake-key")
        monkeypatch.setenv("GOOGLE_GEOCODING_CONFIRM", "1")
        monkeypatch.setenv("GOOGLE_REGION", "no")

        geocoder = get_geocoder("google", cache=cache)

        assert geocoder.name == "google"
        assert geocoder.components == {"country": "no"}

    def test_confirm_must_be_exactly_one(self, monkeypatch, cache):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake-key")
        monkeypatch.setenv("GOOGLE_GEOCODING_CONFIRM", "true")
        with pytest.raises(GeocoderConfigError):
            get_geocoder("google", cache=cache)


def test_every_provider_carries_attribution(monkeypatch, cache):
    monkeypatch.setenv("NOMINATIM_USER_AGENT", "test-suite/1.0 (ci@example.com)")
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake-key")
    monkeypatch.setenv("GOOGLE_GEOCODING_CONFIRM", "1")

    for provider in PROVIDERS:
        assert get_geocoder(provider, cache=cache).attribution
