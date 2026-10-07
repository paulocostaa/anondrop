user_key: str | None = None


def set_client_key(key: str) -> None:
    global user_key
    user_key = key


def get_client_key() -> str | None:
    return user_key
