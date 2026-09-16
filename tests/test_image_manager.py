"""Poster downloads tolerate transient failures without caching errors."""

from unittest.mock import Mock

import pytest
import requests

from jellyfix.core.image_manager import ImageManager
from jellyfix.core.metadata import Metadata
from jellyfix.utils.config import Config, set_config


@pytest.fixture
def image_download(tmp_path, monkeypatch):
    set_config(Config(fetch_metadata=False))
    session = Mock()
    monkeypatch.setattr("jellyfix.utils.http.get_session", lambda *args, **kwargs: session)
    return ImageManager(tmp_path / "cache"), session


@pytest.mark.parametrize("error", [requests.ConnectionError, requests.Timeout])
def test_poster_retries_transient_failure_and_caches_success(image_download, error):
    manager, session = image_download
    response = Mock(content=b"poster image")
    session.get.side_effect = [error("temporary failure"), response]
    metadata = Metadata(title="Movie", tmdb_id=637649, poster_path="/poster.jpg")

    path = manager.download_poster(metadata)

    assert path.read_bytes() == b"poster image"
    assert session.get.call_count == 2
    response.raise_for_status.assert_called_once_with()
    assert manager.download_poster(metadata) == path
    assert session.get.call_count == 2


def test_poster_stops_after_second_connection_failure(image_download):
    manager, session = image_download
    session.get.side_effect = requests.ConnectionError("unreachable")

    assert manager.download_poster(
        Metadata(title="Movie", tmdb_id=637649, poster_path="/poster.jpg")
    ) is None
    assert session.get.call_count == 2
    assert manager.cache.index == {}


def test_poster_does_not_retry_or_cache_http_errors(image_download):
    manager, session = image_download
    session.get.return_value.raise_for_status.side_effect = requests.HTTPError("404")

    assert manager.download_poster(
        Metadata(title="Movie", tmdb_id=637649, poster_path="/missing.jpg")
    ) is None
    session.get.assert_called_once()
    assert manager.cache.index == {}
