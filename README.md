# anondrop

A small Python client for the [anondrop.net](https://anondrop.net) file hosting
API. It wraps account registration, uploads (direct, remote, and chunked),
listing, editing, and deletion behind a single synchronous `Anondrop` class.

The client key is stored globally, so you set it once with
`anondrop.set_client_key()` and every method uses it automatically. All upload
methods return the public link to the uploaded file. The client speaks plain
HTTP via [httpx](https://www.python-httpx.org/).

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

Register an account to get a user key, set it once, then use the client.

```python
import anondrop
from anondrop import Anondrop

client = Anondrop()

key = client.register()          # e.g. "1556698775525916834"
anondrop.set_client_key(key)

link = client.direct_upload("hello.txt")
print(link)                      # https://anondrop.net/1556815268104249355
```

If you already have a key, skip `register()` and set it directly:

```python
anondrop.set_client_key("1556698775525916834")
```

`set_client_key` also has a historical alias, `anondrop.setClientKey`, for
compatibility.

## API

Set the client key before calling anything other than `register()`; otherwise
the methods raise `AnondropError("Key missing")`. Every method can also raise
`AnondropError` (or its subclass `ServerError`) on failure.

| Method | Description | Returns |
| --- | --- | --- |
| `register()` | Creates a new account. | User key |
| `files()` | Lists the account's files. | Raw JSON string |
| `direct_upload(path)` | Uploads a local file in one request. | File link |
| `remote_upload(url, filename)` | Asks the server to fetch a file from a URL. | File link |
| `chunked_upload(path)` | Uploads a local file in 1 MiB chunks. | File link |
| `delete_file(file_id)` | Deletes a file. | Status message |
| `edit_file(file_id, *, metadata=None)` | Updates a file's metadata. | Status message |

### Register

```python
key = client.register()
anondrop.set_client_key(key)
```

Extracts the user key from the registration page.

### List files

```python
import json

data = json.loads(client.files())
for item in data["files"]:
    print(item["id"], item["name"])
```

### Direct upload

Uploads a local file as a single multipart request.

```python
link = client.direct_upload("photo.png")
```

### Remote upload

Asks anondrop.net to download a file from a URL and store it under `filename`.
The response is a Server-Sent-Events stream; the client consumes it and returns
the resulting link.

```python
link = client.remote_upload("https://example.com/data.csv", "data.csv")
```

If the server aborts the stream before producing a link, an `AnondropError` with
the message `Remote upload failed: server closed the stream` is raised.

### Chunked upload

Uploads a local file in 1 MiB chunks, which is friendlier for large files.

```python
link = client.chunked_upload("big-video.mp4")
```

### Delete a file

```python
client.delete_file("1556815268104249355")  # -> "deleted"
```

Raises `AnondropError` when the server reports `not deleted`.

### Edit a file

```python
client.edit_file("1556815268104249355", metadata={"name": "renamed.mp4"})
```

`metadata` is sent as the JSON request body.

## Error handling

```python
import anondrop
from anondrop import Anondrop, AnondropError, ServerError

client = Anondrop()
anondrop.set_client_key("1556698775525916834")

try:
    client.files()
except ServerError as err:
    print("HTTP error", err.status_code)
except AnondropError as err:
    print("Request failed:", err)
```

- `ServerError` — the server returned a non-2xx status; carries `status_code`.
- `AnondropError` — connection timeouts, network failures, a missing client
  key, or responses that could not be parsed.

## Development

Run the test suite:

```bash
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
