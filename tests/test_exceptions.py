import pytest

from anondrop.exceptions import AnondropError, ServerError


class TestAnondropError:
    def test_is_exception(self):
        assert issubclass(AnondropError, Exception)

    def test_carries_message(self):
        assert str(AnondropError("boom")) == "boom"


class TestServerError:
    def test_is_anondrop_error(self):
        assert issubclass(ServerError, AnondropError)

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 500, 503])
    def test_stores_status_code(self, status_code):
        error = ServerError(status_code)

        assert error.status_code == status_code

    def test_message_includes_status_code(self):
        assert str(ServerError(418)) == "Server returned HTTP 418"
