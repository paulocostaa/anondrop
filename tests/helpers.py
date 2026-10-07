"""Shared test doubles for the anondrop test-suite."""

import httpx

TEST_KEY = "test-key"


class FakeResponse:
    """Minimal stand-in for ``httpx.Response``."""

    def __init__(self, text: str = "", status_code: int = 200):
        self.text = text
        self.status_code = status_code
        self.raise_for_status_calls = 0
        # ``Anondrop._request`` inspects these for its debug output.
        self.request = httpx.Request("GET", "https://www.anondrop.net")
        self.headers = httpx.Headers()

    def raise_for_status(self) -> None:
        self.raise_for_status_calls += 1
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://www.anondrop.net")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                "error", request=request, response=response
            )


class RequestRecorder:
    """Records calls and replays a queued response or raises an exception."""

    def __init__(self, outcomes=None):
        self.calls: list[dict] = []
        self.outcomes = list(outcomes or [])

    def __call__(self, method, url, **kwargs):
        # Snapshot uploaded file handles while they are still open, since the
        # caller closes them as soon as the request returns.
        files = kwargs.get("files")
        if files:
            kwargs["files"] = {
                name: value.read() if hasattr(value, "read") else value
                for name, value in files.items()
            }
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        if not self.outcomes:
            return FakeResponse()
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def make_status_error(status_code: int) -> httpx.HTTPStatusError:
    """Build a real ``httpx.HTTPStatusError`` carrying ``status_code``."""

    request = httpx.Request("GET", "https://www.anondrop.net")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


class FakeStream:
    """Stand-in for the response object returned by ``httpx.stream``."""

    def __init__(self, chunks=None, *, status_code=200, body_error=None):
        self.chunks = list(chunks or [])
        self.status_code = status_code
        self.body_error = body_error

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://www.anondrop.net")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                "error", request=request, response=response
            )

    def iter_text(self):
        yield from self.chunks
        if self.body_error is not None:
            raise self.body_error


class StreamRecorder:
    """Records ``httpx.stream`` calls and replays queued stream objects."""

    def __init__(self, outcomes=None):
        self.calls: list[dict] = []
        self.outcomes = list(outcomes or [])

    def __call__(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        if not self.outcomes:
            return FakeStream()
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
