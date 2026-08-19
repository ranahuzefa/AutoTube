"""Security checks for the licensing server and client separation."""

from __future__ import annotations

import sys


def test_client_package_has_no_private_signing() -> None:
    import autotube.licensing.token as client_token

    source = open(client_token.__file__, encoding="utf-8").read()
    assert "Ed25519PrivateKey" not in source
    assert "def sign_activation_token" not in source


def test_client_public_key_resolver_has_no_private_signing() -> None:
    import autotube.licensing.keysource as keysource

    source = open(keysource.__file__, encoding="utf-8").read()
    assert "Ed25519PrivateKey" not in source
    assert "def sign_activation_token" not in source
    assert "serialization.load_pem_private_key" not in source


def test_licensing_server_owns_private_signing() -> None:
    import licensing_server.issuance as issuance

    source = open(issuance.__file__, encoding="utf-8").read()
    assert "Ed25519PrivateKey" in source
    assert "def sign_activation_token" in source


def test_client_does_not_import_licensing_server() -> None:
    import autotube.licensing

    for name in list(sys.modules):
        if name.startswith("autotube") and "licensing_server" in name:
            raise AssertionError("client imported licensing_server")
