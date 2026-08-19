# AutoTube Creator Packaging

AutoTube Creator ships as a Windows one-folder application built with
PyInstaller and wrapped in an Inno Setup installer.

## FFmpeg / FFprobe location strategy

FFmpeg and FFprobe are **not bundled by default**. Bundling them would require
redistribution review of their respective licenses, and AutoTube does not
silently download binaries.

The application resolves the media tools in this order:

1. `ffmpeg` / `ffprobe` on `PATH`.
2. Bundled binaries next to the frozen executable:
   - `<dist>/autotube/ffmpeg/ffmpeg.exe`
   - `<dist>/autotube/ffmpeg/ffprobe.exe`

If neither is available, the CLI exits with a clear error and the GUI shows an
error dialog before any pipeline/render work starts.

## Version and icon

- Application version: `src/autotube/__init__.py` (`__version__`).
- PyInstaller version resource: `packaging/version_info.txt`.
- Application icon: `packaging/app.ico`.

Keep these values in sync when bumping a release.

## Build

```powershell
.venv\Scripts\python.exe -m PyInstaller --clean packaging\autotube.spec
```

The output is written to `dist\autotube\`.

## Create a fully portable build

After building, copy your own licensed FFmpeg/FFprobe binaries into the bundled
directory:

```powershell
New-Item -ItemType Directory -Force dist\autotube\ffmpeg
Copy-Item C:\path\to\ffmpeg.exe dist\autotube\ffmpeg\
Copy-Item C:\path\to\ffprobe.exe dist\autotube\ffmpeg\
```

## Licensing public key

The distributed client verifies signed activation tokens with the licensing
server's **public** Ed25519 key. The private signing key must never be bundled
or embedded in the client. Configure the public key using one of:

1. `AUTOTUBE_LICENSE_PUBLIC_KEY` environment variable (PEM text).
2. `AUTOTUBE_LICENSE_PUBLIC_KEY_FILE` environment variable (path to a PEM file).
3. A bundled `license_public.pem` next to the module (or, for frozen builds,
   next to `autotube.exe`).

Export the server key after running the server's `init-keypair`:

```powershell
.venv\Scripts\python.exe -m licensing_server export-public-key --out license_public.pem
```

The client fails closed with a licensing configuration error if no key is
available; it never falls back to a placeholder.

## Artifact security audit

Before shipping, run:

```powershell
.venv\Scripts\python.exe packaging\verify_artifact.py dist\autotube
```

This fails if the artifact contains tests, pytest, `_pytest`, the licensing
server, private key material, `.env` files, or raw API-key/secret patterns.

## Installer (Inno Setup)

With the Inno Setup compiler on `PATH`:

```powershell
ISCC.exe packaging\installer.iss
```

This produces `dist\AutoTube Creator Setup 1.0.0.exe` with a Start Menu shortcut,
an optional Desktop shortcut, and an uninstaller. User data under
`%APPDATA%\AutoTube` is preserved across upgrades and uninstall.

## Code signing

Authenticode signing is a manual release-time step using a valid certificate.
The build/installer configuration does not embed a signing certificate or
private key.

Example (Windows SDK `signtool`):

```powershell
signtool sign /fd SHA256 /a /f cert.pfx /p <password> "dist\AutoTube Creator Setup 1.0.0.exe"
```

## Smoke test

```powershell
dist\autotube\autotube.exe --version
```

See `docs/RELEASE.md` for the full v1.0 acceptance checklist.
