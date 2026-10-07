import pytest

from anondrop import Anondrop, config, set_client_key

from helpers import TEST_KEY, RequestRecorder, StreamRecorder


@pytest.fixture
def client(monkeypatch) -> Anondrop:
    """A client with no client key set (isolated per test)."""

    monkeypatch.setattr(config, "user_key", None)
    return Anondrop()


@pytest.fixture
def keyed_client(monkeypatch) -> Anondrop:
    """A client with a valid client key set via the public API."""

    monkeypatch.setattr(config, "user_key", None)
    set_client_key(TEST_KEY)
    return Anondrop()


@pytest.fixture
def recorder(monkeypatch) -> RequestRecorder:
    """Patch the ``httpx`` symbol used by ``anondrop.api`` with a recorder."""

    rec = RequestRecorder()
    monkeypatch.setattr("anondrop.api.httpx.request", rec)
    return rec


@pytest.fixture
def stream_recorder(monkeypatch) -> StreamRecorder:
    """Patch ``httpx.stream`` used by ``anondrop.api`` with a recorder."""

    rec = StreamRecorder()
    monkeypatch.setattr("anondrop.api.httpx.stream", rec)
    return rec
