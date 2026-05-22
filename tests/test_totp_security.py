from app.core.security import _totp_at, totp_provisioning_uri, verify_totp_code


def test_totp_verifies_current_and_adjacent_windows() -> None:
    secret = "JBSWY3DPEHPK3PXP"
    code = _totp_at(secret, 1_000)

    assert verify_totp_code(secret, code, at_time=30_000)
    assert verify_totp_code(secret, code, at_time=30_030)
    assert not verify_totp_code(secret, code, at_time=30_090)


def test_totp_provisioning_uri_is_1password_compatible() -> None:
    uri = totp_provisioning_uri("JBSWY3DPEHPK3PXP", "agent@example.com")

    assert uri.startswith("otpauth://totp/THOR%20HelpDesk%3Aagent%40example.com?")
    assert "secret=JBSWY3DPEHPK3PXP" in uri
    assert "issuer=THOR%20HelpDesk" in uri
    assert "digits=6" in uri
