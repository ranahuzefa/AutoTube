# AutoTube Creator v1.0.0 Release Notes

AutoTube Creator v1.0.0 is the first production release. It converts a script
and voiceover into a ready-to-upload YouTube video with transcription,
segmentation, keyword generation, stock footage search/download, clip
processing, composition, audio mixing, captions, timeline rendering,
transitions/SFX, and missing-visual-slot handling.

## What's included

- Resumable 9-stage pipeline with atomic project persistence.
- PySide6 GUI (Project, Workflow, Timeline, Settings, License, Log).
- Headless CLI.
- Pexels/Pixabay stock providers with deterministic fallback ordering.
- Optional AI keyword generation (OpenRouter/DashScope) with local fallback.
- faster-whisper transcription with CPU/CUDA detection.
- Timeline composer with transitions, animations, and missing-slot handling.
- Product licensing (activation, re-validation, offline grace, revocation).
- Windows DPAPI secure API-key storage.
- Rotating production logs with secret redaction.
- Windows installer and PyInstaller one-folder artifact.

## Final acceptance checklist

- [ ] Application version is `1.0.0` everywhere.
- [ ] PyInstaller one-folder build succeeds.
- [ ] Artifact security audit passes (no tests/pytest/`_pytest`, licensing
      server, private keys, `.env`, or raw secrets).
- [ ] Frozen executable: `--version`, `--license-status`, `--new`, `--resume`,
      and missing-FFmpeg behavior verified.
- [ ] Inno Setup installer compiles and preserves `%APPDATA%\AutoTube`.
- [ ] Licensing client remains verification-only.
- [ ] DPAPI secrets and rotating logs work from the frozen executable.
- [ ] Real-FFmpeg end-to-end, timeline, transition, and missing-slot render
      tests pass where FFmpeg is available.
- [ ] Full offline regression suite passes.
- [ ] Documentation is current.

## Manual release steps

- Apply Authenticode code signing with a valid certificate.
- Optionally swap `packaging/app.ico` for final branded art.
- Perform a clean-machine install/launch test on a real VM/machine.
