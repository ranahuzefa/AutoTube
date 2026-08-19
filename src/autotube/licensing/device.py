"""Privacy-conscious stable device identifier.

Only a salted SHA-256 hash of the OS machine identifier is ever returned by
``device_id_hash``; the raw identifier is read in memory and immediately
discarded. No username, hostname, MAC address, or other personal information
is collected.
"""

from __future__ import annotations

import hashlib
import platform
import subprocess

from ..exceptions import LicenseError

_APP_NAMESPACE = b"autotube-creator:v1"


def _windows_machine_guid() -> str:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value)
    except Exception as exc:  # noqa: BLE001 - fall back below
        raise LicenseError("Unable to read stable device identifier.") from exc


def _macos_platform_uuid() -> str:
    try:
        result = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stdout.splitlines():
            if "IOPlatformUUID" in line:
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    raise LicenseError("Unable to read stable device identifier.")


def _linux_machine_id() -> str:
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            value = open(path, encoding="utf-8").read().strip()  # noqa: SIM115
            if value:
                return value
        except OSError:
            continue
    raise LicenseError("Unable to read stable device identifier.")


def stable_device_id() -> str:
    """Return the raw OS machine id (for hashing only; never persist/transmit)."""
    system = platform.system()
    if system == "Windows":
        return _windows_machine_guid()
    if system == "Darwin":
        return _macos_platform_uuid()
    if system == "Linux":
        return _linux_machine_id()
    raise LicenseError(f"Unsupported platform for device binding: {system}")


def device_id_hash(namespace: bytes = _APP_NAMESPACE) -> str:
    """Return ``SHA-256(namespace || stable_device_id)`` as a hex digest."""
    raw = stable_device_id().encode("utf-8")
    return hashlib.sha256(namespace + raw).hexdigest()


def current_device_id_hash() -> str:
    return device_id_hash()
