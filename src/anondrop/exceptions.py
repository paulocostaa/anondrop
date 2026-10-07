class AnondropError(Exception):
    pass


class ServerError(AnondropError):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"Server returned HTTP {status_code}")
