import httpx
import pytest

from anondrop import Anondrop, set_client_key
from anondrop.api import BASE_URL
from anondrop.exceptions import AnondropError, ServerError

from helpers import (
    TEST_KEY,
    FakeResponse,
    FakeStream,
    RequestRecorder,
    StreamRecorder,
    make_status_error,
)

BAD_KEYS = [None, "", "   ", "\t\n", 123, 1.5, b"key"]


# ---------------------------------------------------------------------------
# client key
# ---------------------------------------------------------------------------


class TestClientKey:
    def test_set_client_key_is_used_by_methods(self, monkeypatch):
        rec = RequestRecorder([FakeResponse('{"files": []}')])
        monkeypatch.setattr("anondrop.api.httpx.request", rec)
        monkeypatch.setattr("anondrop.config.user_key", None)

        set_client_key("abc")
        client = Anondrop()

        assert client.files() == '{"files": []}'
        assert rec.calls[0]["kwargs"]["params"] == {"key": "abc"}


# ---------------------------------------------------------------------------
# _request
# ---------------------------------------------------------------------------


class TestRequest:
    def test_returns_response_and_sets_timeout(self, client, monkeypatch):
        rec = RequestRecorder([FakeResponse("ok")])
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        response = client._request("GET", "https://example.com")

        assert response.text == "ok"
        assert rec.calls[0]["method"] == "GET"
        assert rec.calls[0]["url"] == "https://example.com"
        assert rec.calls[0]["kwargs"]["timeout"] == 10.0

    def test_forwards_extra_kwargs(self, client, monkeypatch):
        rec = RequestRecorder()
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        client._request("POST", "https://example.com", params={"a": 1})

        assert rec.calls[0]["kwargs"]["params"] == {"a": 1}

    def test_http_status_error_becomes_server_error(self, client, monkeypatch):
        rec = RequestRecorder([make_status_error(404)])
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        with pytest.raises(ServerError) as excinfo:
            client._request("GET", "https://example.com")

        assert excinfo.value.status_code == 404
        assert isinstance(excinfo.value, AnondropError)

    def test_timeout_becomes_anondrop_error(self, client, monkeypatch):
        rec = RequestRecorder([httpx.TimeoutException("timed out")])
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        with pytest.raises(AnondropError, match="Connection timed out"):
            client._request("GET", "https://example.com")

    def test_request_error_becomes_anondrop_error(self, client, monkeypatch):
        rec = RequestRecorder([httpx.ConnectError("no route")])
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        with pytest.raises(AnondropError, match="Request failed"):
            client._request("GET", "https://example.com")


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


class TestRegister:
    def test_extracts_user_key(self, client, monkeypatch):
        html = (
            "Created account, redirecting\n\n<script>\n\n"
            "    localStorage.setItem('userkey', '1234567890');\n"
            "</script>\n"
        )
        rec = RequestRecorder([FakeResponse(html)])
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        assert client.register() == "1234567890"
        assert rec.calls[0]["method"] == "GET"
        assert rec.calls[0]["url"] == f"{BASE_URL}/register"
        assert rec.calls[0]["kwargs"]["timeout"] == 10.0

    def test_handles_double_quotes(self, client, monkeypatch):
        rec = RequestRecorder(
            [FakeResponse('localStorage.setItem("userkey", "abcdef")')]
        )
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        assert client.register() == "abcdef"

    def test_missing_user_key_raises(self, client, monkeypatch):
        rec = RequestRecorder([FakeResponse("<html>no key here</html>")])
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        with pytest.raises(AnondropError, match="Could not extract user key"):
            client.register()


# ---------------------------------------------------------------------------
# files
# ---------------------------------------------------------------------------


class TestFiles:
    def test_returns_body_and_sends_key(self, keyed_client, monkeypatch):
        rec = RequestRecorder([FakeResponse("[]")])
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        assert keyed_client.files() == "[]"
        assert rec.calls[0]["method"] == "GET"
        assert rec.calls[0]["url"] == f"{BASE_URL}/files"
        assert rec.calls[0]["kwargs"]["params"] == {"key": TEST_KEY}

    @pytest.mark.parametrize("bad_key", BAD_KEYS)
    def test_rejects_missing_key(self, client, recorder, monkeypatch, bad_key):
        monkeypatch.setattr("anondrop.config.user_key", bad_key)

        with pytest.raises(AnondropError, match="Key missing"):
            client.files()

        assert recorder.calls == []


# ---------------------------------------------------------------------------
# direct_upload
# ---------------------------------------------------------------------------


class TestDirectUpload:
    LINK = "https://anondrop.net/1234567890"

    def test_uploads_file_and_extracts_link(
        self, keyed_client, monkeypatch, tmp_path
    ):
        source = tmp_path / "hello.txt"
        source.write_bytes(b"hello world")
        rec = RequestRecorder(
            [
                FakeResponse(
                    f"Finished! File Link: <a href='{self.LINK}'>{self.LINK}</a>"
                )
            ]
        )
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        assert keyed_client.direct_upload(str(source)) == self.LINK

        call = rec.calls[0]
        assert call["method"] == "POST"
        assert call["url"] == f"{BASE_URL}/upload"
        assert call["kwargs"]["params"] == {"key": TEST_KEY}
        uploaded = call["kwargs"]["files"]["file"]
        assert uploaded == b"hello world"

    def test_missing_link_raises(self, keyed_client, monkeypatch, tmp_path):
        source = tmp_path / "hello.txt"
        source.write_bytes(b"data")
        rec = RequestRecorder([FakeResponse("uploaded but no link")])
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        with pytest.raises(AnondropError, match="Could not extract file link"):
            keyed_client.direct_upload(str(source))

    @pytest.mark.parametrize("bad_key", BAD_KEYS)
    def test_rejects_missing_key(
        self, client, recorder, monkeypatch, tmp_path, bad_key
    ):
        monkeypatch.setattr("anondrop.config.user_key", bad_key)
        source = tmp_path / "hello.txt"
        source.write_bytes(b"data")

        with pytest.raises(AnondropError, match="Key missing"):
            client.direct_upload(str(source))

        assert recorder.calls == []

    def test_missing_file_raises(self, keyed_client, recorder, tmp_path):
        with pytest.raises(FileNotFoundError):
            keyed_client.direct_upload(str(tmp_path / "nope.txt"))

        assert recorder.calls == []


# ---------------------------------------------------------------------------
# remote_upload
# ---------------------------------------------------------------------------


class TestRemoteUpload:
    LINK = "https://anondrop.net/1556813442663448616"
    SUCCESS_CHUNKS = [
        "Starting...",
        "Downloaded: 0 Bytes",
        "Progress: 6624 Bytes (6.47 KB)",
        f"Finished! File Link: <a href='{LINK}'>{LINK}</a>",
    ]

    def test_streams_and_returns_link(self, keyed_client, stream_recorder):
        stream_recorder.outcomes.append(FakeStream(self.SUCCESS_CHUNKS))

        result = keyed_client.remote_upload(
            "https://example.com/file.bin", "file.bin"
        )

        assert result == self.LINK
        call = stream_recorder.calls[0]
        assert call["method"] == "GET"
        assert call["url"] == f"{BASE_URL}/remoteuploadurl"
        assert call["kwargs"]["params"] == {
            "key": TEST_KEY,
            "url": "https://example.com/file.bin",
            "filename": "file.bin",
        }
        assert call["kwargs"]["timeout"] == 60.0

    def test_parses_link_from_single_chunk(self, keyed_client, stream_recorder):
        stream_recorder.outcomes.append(
            FakeStream(
                [f"Finished! File Link: <a href='{self.LINK}'>{self.LINK}</a>"]
            )
        )

        assert keyed_client.remote_upload("u", "f") == self.LINK

    def test_aborted_stream_without_link_raises(
        self, keyed_client, stream_recorder
    ):
        stream_recorder.outcomes.append(
            FakeStream(
                ["Starting..."],
                body_error=httpx.RemoteProtocolError("incomplete chunked read"),
            )
        )

        with pytest.raises(AnondropError, match="server closed the stream"):
            keyed_client.remote_upload("u", "f")

    def test_aborted_stream_with_link_returns_link(
        self, keyed_client, stream_recorder
    ):
        stream_recorder.outcomes.append(
            FakeStream(
                ["Starting...", f"<a href='{self.LINK}'>{self.LINK}</a>"],
                body_error=httpx.RemoteProtocolError("incomplete chunked read"),
            )
        )

        assert keyed_client.remote_upload("u", "f") == self.LINK

    def test_missing_link_raises(self, keyed_client, stream_recorder):
        stream_recorder.outcomes.append(
            FakeStream(["Starting...", "Progress: 1 Bytes"])
        )

        with pytest.raises(AnondropError, match="Could not extract file link"):
            keyed_client.remote_upload("u", "f")

    def test_http_status_error_becomes_server_error(
        self, keyed_client, stream_recorder
    ):
        stream_recorder.outcomes.append(FakeStream([], status_code=500))

        with pytest.raises(ServerError) as excinfo:
            keyed_client.remote_upload("u", "f")

        assert excinfo.value.status_code == 500

    def test_timeout_becomes_anondrop_error(self, keyed_client, stream_recorder):
        stream_recorder.outcomes.append(httpx.TimeoutException("timed out"))

        with pytest.raises(AnondropError, match="Connection timed out"):
            keyed_client.remote_upload("u", "f")

    def test_request_error_becomes_anondrop_error(
        self, keyed_client, stream_recorder
    ):
        stream_recorder.outcomes.append(httpx.ConnectError("no route"))

        with pytest.raises(AnondropError, match="Request failed"):
            keyed_client.remote_upload("u", "f")

    @pytest.mark.parametrize("bad_key", BAD_KEYS)
    def test_rejects_missing_key(self, client, recorder, monkeypatch, bad_key):
        monkeypatch.setattr("anondrop.config.user_key", bad_key)

        with pytest.raises(AnondropError, match="Key missing"):
            client.remote_upload("https://example.com/f", "f")

        assert recorder.calls == []


# ---------------------------------------------------------------------------
# chunked_upload
# ---------------------------------------------------------------------------


class TestChunkedUpload:
    CHUNK = 1024 * 1024
    LINK = "https://anondrop.net/1556815268104249355"

    def test_single_chunk_flow(self, keyed_client, monkeypatch, tmp_path):
        source = tmp_path / "small.bin"
        payload = b"a" * 100
        source.write_bytes(payload)
        rec = RequestRecorder(
            [
                FakeResponse(" session-hash\n"),  # initiateupload
                FakeResponse(""),  # uploadchunk
                FakeResponse(
                    f"File Link: <a href='{self.LINK}'>{self.LINK}</a>"
                ),  # endupload
            ]
        )
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        assert keyed_client.chunked_upload(str(source)) == self.LINK

        assert [c["method"] for c in rec.calls] == ["GET", "POST", "GET"]
        assert [c["url"] for c in rec.calls] == [
            f"{BASE_URL}/initiateupload",
            f"{BASE_URL}/uploadchunk",
            f"{BASE_URL}/endupload",
        ]
        assert rec.calls[0]["kwargs"]["params"] == {
            "key": TEST_KEY,
            "filename": "small.bin",
        }
        assert rec.calls[1]["kwargs"]["params"] == {
            "session_hash": "session-hash"
        }
        assert rec.calls[1]["kwargs"]["files"]["file"] == payload
        assert rec.calls[2]["kwargs"]["params"] == {
            "session_hash": "session-hash"
        }

    def test_splits_into_megabyte_chunks(
        self, keyed_client, monkeypatch, tmp_path
    ):
        source = tmp_path / "big.bin"
        payload = b"x" * (self.CHUNK * 2 + 5)
        source.write_bytes(payload)
        outcomes = (
            [FakeResponse("hash")]
            + [FakeResponse("")] * 3
            + [
                FakeResponse(
                    f"File Link: <a href='{self.LINK}'>{self.LINK}</a>"
                )
            ]
        )
        rec = RequestRecorder(outcomes)
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        assert keyed_client.chunked_upload(str(source)) == self.LINK

        chunk_calls = [
            c for c in rec.calls if c["url"] == f"{BASE_URL}/uploadchunk"
        ]
        assert len(chunk_calls) == 3
        sizes = [len(c["kwargs"]["files"]["file"]) for c in chunk_calls]
        assert sizes == [self.CHUNK, self.CHUNK, 5]

    def test_empty_session_hash_raises(self, keyed_client, monkeypatch, tmp_path):
        source = tmp_path / "file.bin"
        source.write_bytes(b"data")
        rec = RequestRecorder([FakeResponse("  \n")])
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        with pytest.raises(AnondropError, match="session hash"):
            keyed_client.chunked_upload(str(source))

        # No chunk or end call should follow a failed initiation.
        assert len(rec.calls) == 1

    def test_missing_link_raises(self, keyed_client, monkeypatch, tmp_path):
        source = tmp_path / "file.bin"
        source.write_bytes(b"data")
        rec = RequestRecorder(
            [
                FakeResponse("hash"),
                FakeResponse(""),
                FakeResponse("Finished without a link"),
            ]
        )
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        with pytest.raises(AnondropError, match="Could not extract file link"):
            keyed_client.chunked_upload(str(source))

    @pytest.mark.parametrize("bad_key", BAD_KEYS)
    def test_rejects_missing_key(
        self, client, recorder, monkeypatch, tmp_path, bad_key
    ):
        monkeypatch.setattr("anondrop.config.user_key", bad_key)
        source = tmp_path / "file.bin"
        source.write_bytes(b"data")

        with pytest.raises(AnondropError, match="Key missing"):
            client.chunked_upload(str(source))

        assert recorder.calls == []


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------


class TestDeleteFile:
    def test_posts_to_file_url(self, keyed_client, monkeypatch):
        rec = RequestRecorder([FakeResponse("deleted")])
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        assert keyed_client.delete_file("FILE123") == "deleted"
        call = rec.calls[0]
        assert call["method"] == "POST"
        assert call["url"] == f"{BASE_URL}/delete/FILE123"
        assert call["kwargs"]["params"] == {"key": TEST_KEY}

    def test_not_deleted_raises(self, keyed_client, monkeypatch):
        rec = RequestRecorder([FakeResponse("not deleted")])
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        with pytest.raises(AnondropError, match="Could not delete file"):
            keyed_client.delete_file("FILE123")

    @pytest.mark.parametrize("bad_key", BAD_KEYS)
    def test_rejects_missing_key(self, client, recorder, monkeypatch, bad_key):
        monkeypatch.setattr("anondrop.config.user_key", bad_key)

        with pytest.raises(AnondropError, match="Key missing"):
            client.delete_file("FILE123")

        assert recorder.calls == []


# ---------------------------------------------------------------------------
# edit_file
# ---------------------------------------------------------------------------


class TestEditFile:
    def test_sends_metadata_as_json(self, keyed_client, monkeypatch):
        rec = RequestRecorder([FakeResponse("Ready to edit")])
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        result = keyed_client.edit_file(
            "FILE123", metadata={"name": "new.txt", "private": True}
        )

        assert result == "Ready to edit"
        call = rec.calls[0]
        assert call["method"] == "POST"
        assert call["url"] == f"{BASE_URL}/editform/FILE123"
        assert call["kwargs"]["params"] == {"key": TEST_KEY}
        assert call["kwargs"]["json"] == {"name": "new.txt", "private": True}

    def test_defaults_to_empty_json(self, keyed_client, monkeypatch):
        rec = RequestRecorder([FakeResponse("Ready to edit")])
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        keyed_client.edit_file("FILE123")

        assert rec.calls[0]["kwargs"]["json"] == {}

    def test_metadata_is_copied_not_mutated(self, keyed_client, monkeypatch):
        rec = RequestRecorder([FakeResponse("Ready to edit")])
        monkeypatch.setattr("anondrop.api.httpx.request", rec)
        metadata = {"name": "a.txt"}

        keyed_client.edit_file("FILE123", metadata=metadata)

        assert metadata == {"name": "a.txt"}
        assert rec.calls[0]["kwargs"]["json"] is not metadata

    def test_unexpected_response_raises(self, keyed_client, monkeypatch):
        rec = RequestRecorder([FakeResponse("Something went wrong")])
        monkeypatch.setattr("anondrop.api.httpx.request", rec)

        with pytest.raises(AnondropError, match="Could not edit file"):
            keyed_client.edit_file("FILE123")

    @pytest.mark.parametrize("bad_key", BAD_KEYS)
    def test_rejects_missing_key(self, client, recorder, monkeypatch, bad_key):
        monkeypatch.setattr("anondrop.config.user_key", bad_key)

        with pytest.raises(AnondropError, match="Key missing"):
            client.edit_file("FILE123")

        assert recorder.calls == []
