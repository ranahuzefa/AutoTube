# AutoTube Creator

AutoTube Creator converts a script and voiceover into a ready-to-upload YouTube
video. It transcribes the voiceover, detects segments, generates visual keywords,
searches stock footage (Pexels with Pixabay fallback), downloads and processes
clips, then composes the final MP4 with voiceover, background music, and captions.

## Status

**v1.0.0** — production release.

## Requirements

- Windows 10/11.
- FFmpeg and FFprobe available (see [FFmpeg](#ffmpeg)).
- A product license for rendering/exporting (see [Licensing](#licensing)).

## Installation

Download and run the `AutoTube Creator Setup 1.0.0.exe` installer. It installs a
per-user application with a Start Menu shortcut and an optional Desktop shortcut.

Your projects and application settings are stored under `%APPDATA%\AutoTube`
and are preserved across upgrades.

## FFmpeg

AutoTube uses FFmpeg and FFprobe for all media processing. They are **not**
bundled with the installer.

The application resolves them in this order:

1. `ffmpeg` / `ffprobe` on `PATH`.
2. `ffmpeg.exe` / `ffprobe.exe` in `<install-dir>\ffmpeg\`.

Install FFmpeg (both `ffmpeg.exe` and `ffprobe.exe`) and ensure they are on
`PATH`, or drop them into the `ffmpeg` folder next to the application. If they
are missing, the application shows a clear error before any render work starts.

## First-run setup

1. Launch AutoTube Creator.
2. In **Settings**, configure the stock providers you want to use:
   - Pexels API key
   - Pixabay API key
   Keys are stored with Windows DPAPI, not in plaintext.
3. Optionally enable AI keyword generation and configure its provider/model.
4. Activate your product license in the **License** tab (see below).

The first transcription run downloads the selected Whisper model. This requires
network access and disk space, and happens only once per model.

## Licensing

Rendering and exporting require an activated license. Use the **License** tab
(or `autotube --activate-key <key>`) to activate. License state is stored
separately from projects and settings. The distributed client is
verification-only: it contains only the licensing server's public key, never
private signing material.

## CLI

```powershell
autotube --version
autotube --new --name "My Video" --script script.txt --voiceover voice.mp3
autotube --resume path\to\project.json
autotube --run path\to\project.json
autotube --license-status
autotube --activate-key ATK-XXXXX-XXXXX-XXXXX-XXXXX-X
```

Run with no command to launch the GUI.

## API provider configuration

Stock and AI providers use environment variables where possible:

- Pexels: `PEXELS_API_KEY`
- Pixabay: `PIXABAY_API_KEY`
- AI keyword generation: provider-specific key via the configured env var
  (default `OPENROUTER_API_KEY`).

Environment-variable overrides always take precedence over stored settings.

## Troubleshooting

- **"Required media tools are missing"** — install FFmpeg/FFprobe (see above).
- **"License required"** — activate a valid license before rendering.
- **"License validation is unavailable"** — check network connectivity; the
  application may enter a bounded offline-grace window.
- **Unexpected errors** — see `%APPDATA%\AutoTube\logs\autotube.log`. Logs are
  rotated and secret values are redacted.

## Tests

Development only:

```powershell
pytest
```

See `docs/architecture.md` for design and `docs/RELEASE.md` for v1.0 notes.
