import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx

from . import config
from .exceptions import AnondropError, ServerError

BASE_URL = "https://anondrop.net"


class Anondrop:
    def _require_key(self) -> str:
        key = config.get_client_key()

        if not isinstance(key, str) or not key.strip():
            raise AnondropError("Key missing")

        return key

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        try:
            response = httpx.request(
                method,
                url,
                timeout=10.0,
                **kwargs,
            )

            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as err:
            raise ServerError(err.response.status_code) from err

        except httpx.TimeoutException as err:
            raise AnondropError("Connection timed out") from err

        except httpx.RequestError as err:
            raise AnondropError("Request failed") from err

    def register(self) -> str:
        response = self._request(
            "GET",
            f"{BASE_URL}/register",
        )

        match = re.search(
            r"localStorage\.setItem\(\s*['\"]userkey['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
            response.text,
        )
        if not match:
            raise AnondropError("Could not extract user key")

        return match.group(1)

    def files(self) -> str:
        key = self._require_key()

        response = self._request(
            "GET",
            f"{BASE_URL}/files",
            params={"key": key},
        )

        return response.text

    def direct_upload(self, path: str):
        key = self._require_key()

        with open(path, "rb") as file:
            response = self._request(
                "POST",
                f"{BASE_URL}/upload",
                params={"key": key},
                files={"file": file},
            )

        match = re.search(r"<a\s+href=['\"]([^'\"]+)['\"]>", response.text)

        if not match:
            raise AnondropError("Could not extract file link")

        return match.group(1)

    def remote_upload(self, url: str, filename: str) -> str:
        key = self._require_key()

        chunks: list[str] = []
        aborted = False

        try:
            with httpx.stream(
                "GET",
                f"{BASE_URL}/remoteuploadurl",
                params={
                    "key": key,
                    "url": url,
                    "filename": filename,
                },
                timeout=60.0,
            ) as response:
                response.raise_for_status()

                try:
                    chunks.extend(response.iter_text())
                except httpx.RemoteProtocolError:
                    aborted = True

        except httpx.HTTPStatusError as err:
            raise ServerError(err.response.status_code) from err

        except httpx.TimeoutException as err:
            raise AnondropError("Connection timed out") from err

        except httpx.RequestError as err:
            raise AnondropError("Request failed") from err

        match = re.search(r"<a\s+href=['\"]([^'\"]+)['\"]>", "".join(chunks))

        if not match:
            if aborted:
                raise AnondropError("Remote upload failed: server closed the stream")
            raise AnondropError("Could not extract file link")

        return match.group(1)

    def chunked_upload(self, path: str) -> str:
        key = self._require_key()

        filename = Path(path).name

        response = self._request(
            "GET",
            f"{BASE_URL}/initiateupload",
            params={
                "key": key,
                "filename": filename,
            },
        )

        session_hash = response.text.strip()

        if not session_hash:
            raise AnondropError("Server did not return a session hash")

        with open(path, "rb") as file:
            while chunk := file.read(1024 * 1024):
                self._request(
                    "POST",
                    f"{BASE_URL}/uploadchunk",
                    params={"session_hash": session_hash},
                    files={"file": chunk},
                )

        response = self._request(
            "GET",
            f"{BASE_URL}/endupload",
            params={"session_hash": session_hash},
        )

        match = re.search(r"<a\s+href=['\"]([^'\"]+)['\"]>", response.text)

        if not match:
            raise AnondropError("Could not extract file link")

        return match.group(1)

    def delete_file(self, FILE_ID: str) -> str:
        key = self._require_key()

        response = self._request(
            "POST",
            f"{BASE_URL}/delete/{FILE_ID}",
            params={"key": key},
        )

        match = re.search(r"^\s*deleted\s*$", response.text)

        if not match:
            raise AnondropError("Could not delete file")

        return response.text

    def edit_file(
        self,
        file_id: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        key = self._require_key()

        data = dict(metadata or {})

        response = self._request(
            "POST",
            f"{BASE_URL}/editform/{file_id}",
            params={"key": key},
            json=data,
        )

        match = re.search(r"^\s*Ready to edit\s*$", response.text)

        if not match:
            raise AnondropError("Could not edit file")

        return response.text
