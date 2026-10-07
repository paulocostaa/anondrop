import anondrop
from anondrop import config


class TestConfig:
    def teardown_method(self):
        config.user_key = None

    def test_defaults_to_none(self):
        assert config.get_client_key() is None

    def test_set_and_get(self):
        config.set_client_key("my-key")

        assert config.user_key == "my-key"
        assert config.get_client_key() == "my-key"

    def test_set_overwrites(self):
        config.set_client_key("first")
        config.set_client_key("second")

        assert config.get_client_key() == "second"

    def test_reexported_from_package(self):
        assert anondrop.set_client_key is config.set_client_key
        assert anondrop.setClientKey is config.set_client_key

    def test_public_function_sets_state(self):
        anondrop.set_client_key("public-key")

        assert config.get_client_key() == "public-key"

    def test_alias_sets_state(self):
        anondrop.setClientKey("alias-key")

        assert config.get_client_key() == "alias-key"
