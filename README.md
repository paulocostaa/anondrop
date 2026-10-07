# anondrop

A small Python client for the [anondrop.net](https://anondrop.net) file hosting
API. It wraps account registration, uploads (direct, remote, and chunked),
listing, editing, and deletion behind a single synchronous `Anondrop` class.

All upload methods return the public link to the uploaded file. The client
speaks plain HTTP via [httpx](https://www.python-httpx.org/).

## Requirements

- Python 3.14 or newer
- `httpx` (installed automatically)

## Installation

With [uv](https://docs.astral.sh/uv/):

```bash
uv add anondrop
```

Or with pip:

```bash
pip install anondrop
```

## Quick start

Register an account to get a user key, then use that key for every other call.

```python
from anondrop import Anondrop

client = Anondrop()

key = client.register()
print(key)  # e.g. "1556698775525916834"
```

```python
from anondrop import Anondrop

client = Anondrop()
key = "1556698775525916834"

link = client.direct_upload(key, "hello.txt")
print(link)  # https://anondrop.net/1556815268104249355
```

## API

Every method raises `AnondropError` (or its subclass `ServerError`) on failure.

| Method | Description | Returns |
| --- | --- | --- |
| `register()` | Creates a new account. | User key |
| `files(key)` | Lists the account's files. | Raw JSON string |
| `direct_upload(key, path)` | Uploads a local file in one request. | File link |
| `remote_upload(key, url, filename)` | Asks the server to fetch a file from a URL. | File link |
| `chunked_upload(path, key)` | Uploads a local file in 1 MiB chunks. | File link |
| `delete_file(file_id, key)` | Deletes a file. | Status message |
| `edit_file(file_id, key, *, metadata=None)` | Updates a file's metadata. | Status message |

> **Note:** the argument order of `chunked_upload` is `(path, key)`, unlike the
> other upload methods which take `key` first.

### Register

```python
key = client.register()
```

Extracts the user key from the registration page.

### List files

```python
import json

data = json.loads(client.files(key))
for item in data["files"]:
    print(item["id"], item["name"])
```

### Direct upload

Uploads a local file as a single multipart request.

```python
link = client.direct_upload(key, "photo.png")
```

### Remote upload

Asks anondrop.net to download a file from a URL and store it under `filename`.
The response is a Server-Sent-Events stream; the client consumes it and returns
the resulting link.

```python
link = client.remote_upload(key, "https://example.com/data.csv", "data.csv")
```

If the server aborts the stream before producing a link, an `AnondropError` with
the message `Remote upload failed: server closed the stream` is raised.

### Chunked upload

Uploads a local file in 1 MiB chunks, which is friendlier for large files.

```python
link = client.chunked_upload("big-video.mp4", key)
```

### Delete a file

```python
client.delete_file("1556815268104249355", key)  # -> "deleted"
```

Raises `AnondropError` when the server reports `not deleted`.

### Edit a file

```python
client.edit_file("1556815268104249355", key, metadata={"name": "renamed.mp4"})
```

`metadata` is sent as the JSON request body.

## Error handling

```python
from anondrop import Anondrop, AnondropError, ServerError

client = Anondrop()
try:
    client.files("bad-key")
except ServerError as err:
    print("HTTP error", err.status_code)
except AnondropError as err:
    print("Request failed:", err)
```

- `ServerError` — the server returned a non-2xx status; carries `status_code`.
- `AnondropError` — connection timeouts, network failures, missing keys, or
  responses that could not be parsed.

## Development

Run the test suite:

```bash
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
