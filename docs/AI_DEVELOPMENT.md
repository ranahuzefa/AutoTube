# AI Development and Maintenance Runbook

This is the detailed handoff for future AI maintainers. `AGENTS.md` contains the
mandatory rules. This document describes the code that exists on 2026-08-20; it
must be updated when architecture, commands, or verified blockers change.

## System Overview

AutoTube Creator is a proprietary Windows-first Python 3.10+ application with a
PySide6 desktop GUI and an `argparse` CLI. It converts a script and voiceover
into a final MP4 using transcription, keyword generation, stock media, FFmpeg,
captions, and an optional manually authored timeline. The installed console
script `autotube` maps to `autotube.cli:main`; no CLI action launches the GUI.

Headless `--run` checks FFmpeg/FFprobe, validates the stored offline license,
loads `ProjectState`, builds transcription, AI/stock, media, and timeline
services, then calls `PipelineOrchestrator`. The orchestrator is the authoritative
full render path: it owns stage dispatch, cancellation checks, persistence after
stage transitions, resume/force behavior, timeline routing, and final media
validation. `services/pipeline.py` is a smaller registered-runner abstraction,
not a competing top-level render workflow.

## Nine Pipeline Stages

The names and order are persisted compatibility contracts in `state.py`:

| Order | Stage | Responsibility |
| --- | --- | --- |
| 1 | `transcribed` | Transcribe the voiceover and store transcription metadata |
| 2 | `segments_ready` | Establish timed segment state |
| 3 | `keywords_ready` | Generate local or validated AI visual keywords |
| 4 | `assets_ready` | Search/select/download stock candidates |
| 5 | `clips_ready` | Normalize selected clips or timeline visual assets |
| 6 | `composed` | Assemble the video-only base track |
| 7 | `audio_ready` | Mix voiceover with optional background music |
| 8 | `captions_ready` | Generate/burn SRT or timeline ASS captions |
| 9 | `completed` | Mux, probe, validate, and record the final MP4 |

Completed and skipped stages are not repeated unless forced. Failures are saved
and resumable. In timeline mode, stages 1-4 are explicitly `SKIPPED`; stages 5-9
are the timeline render stages. Audio and captions remain first-class stages.

## Module Responsibilities

| Path | Responsibility |
| --- | --- |
| `src/autotube/cli.py`, `__main__.py` | CLI parsing, GUI launch, project/run/license commands |
| `models.py`, `state.py` | Domain dataclasses, stage/segment state, explicit serialization |
| `storage.py`, `config.py`, `secrets.py` | Atomic stores, settings/env overrides, secure secrets |
| `services/orchestrator.py` | Authoritative nine-stage execution and persistence |
| `transcription/` | faster-whisper config/model/device, segmentation, workflow |
| `ai/` | Keyword AI engine, typed validation, providers, registries; image/video scaffolds |
| `stock/` | Keyword fallback, provider registry, scoring, cache, download, workflow |
| `media/` | FFmpeg/FFprobe detection, commands, subprocesses, atomic output, validation |
| `timeline/` | SRT/ASS, assets, animations, transitions, missing slots, fingerprints, composer |
| `gui/` | PySide6 tabs, dialogs, worker wiring, safe user-facing errors |
| `licensing/` | Client token verification, key lookup, storage, device hash, enforcement |
| `licensing_server/` | Private key generation, issuance/signing, database, admin/local server |
| `packaging/` | PyInstaller spec, installer, version metadata, artifact security audit |
| `tests/` | Offline unit/contract tests plus opt-in real integrations by domain |

## Persistence and Serialization

`ProjectState` contains the project inputs, render settings, all nine stage
states, segments, transcription metadata, optional `TimelineState`, last error,
timestamps, and schema version. Domain objects are dataclasses with explicit
`to_dict`/`from_dict`; enum values and paths are serialized as strings.

`ProjectStore` and `SettingsStore` use `AtomicFileWriter`: a temporary file in
the destination directory is written, flushed, fsynced, then installed with
`os.replace`. Preserve this boundary. New persisted fields must be additive,
have safe defaults when absent, round-trip, and load legacy payloads. Never
rename stage values or silently reinterpret authoritative timestamps.

Settings live under `%APPDATA%\AutoTube` on Windows. API keys are excluded from
`Settings.to_dict`, stored separately through the DPAPI-backed secret store, and
loaded with environment overrides taking precedence. Clearing a secret means
deleting the stored value. Project JSON must not contain app-level license state.

## Timeline Architecture

`TimelineState` owns subtitles, timed visual assets, a global animation preset,
transition settings, and render fingerprint metadata. `SRTParser` supplies
subtitles. `VisualAssetScanner` parses Windows-safe timestamp filenames and
returns warnings for invalid inputs. Explicit timestamps are authoritative;
overlaps and missing slots are reported rather than silently corrected.

`TimelineComposer` validates inputs, processes image/video assets, constructs
the base track, composes audio, generates ASS captions, and validates the final
render. Animation and transition variants use registries/presets. Transition
effect/sound randomization is deterministically seeded by project identity.
Missing visual slots require manual replacement unless `allow_missing` permits
black output. Cleanup owns only recognizable partial files.

`timeline_input_fingerprint` hashes timeline metadata and render settings, not
media bytes. A changed fingerprint resets only `clips_ready` through `completed`.
All timeline enum fields must remain enum instances in memory; persisted strings
are converted in `from_dict`. The current GUI violates this at one boundary; see
`Current Known Issues`.

## AI Provider Architecture

Keyword generation is optional. `AIKeywordProvider` is the capability protocol;
`AIProviderSpec`/`AIProviderRegistry` and the factory create configured providers.
The default registry contains OpenAI-compatible/OpenRouter and DashScope
adapters implemented with stdlib HTTP, not vendor SDKs.

`AIKeywordEngine` batches within configured segment/input limits, supports
cancellation, validates returned IDs, timestamps, keyword count/content, and
falls back deterministically to `LocalKeywordService` for disabled,
misconfigured, invalid, or failed AI calls. Results are applied after validation,
not persisted as raw provider responses. Image and video generation have
separate protocols/configs/registries, but their default registries are empty
scaffolding; do not document them as implemented providers.

To add an AI provider, extend the relevant registry/spec and adapter, reuse the
existing config/env-var pattern, add registry/config/provider tests, and leave
the engine/workflow and local fallback unchanged. Bound timeout, retries,
backoff, `Retry-After`, request size, and output size; keep TLS verification and
redaction enabled.

## Stock Provider Architecture

`StockProviderProtocol` is implemented by Pexels and Pixabay. The registry owns
provider metadata/factories; `Settings.stock_providers` controls deterministic
order. The factory resolves a standard provider environment variable first,
then the legacy `AUTOTUBE_<FIELD>` override, then the in-memory legacy settings
field loaded from secure storage. Providers without keys and unknown IDs are
skipped.

`StockManager` tries providers in order until one returns candidates, filters
for the target format, scores candidates deterministically, downloads through
`DownloadManager`/`AssetCache`, and validates media with FFprobe. Total provider
failure is an explicit error, never fake success. New providers require a
protocol implementation, registry spec/factory, secret/env configuration,
redaction-safe errors, and registry/fallback/integration tests; workflows should
not gain provider-specific branches.

## Offline Licensing Design

The distributed client is local verification-only. The value entered as a
product key is an Ed25519-signed activation token issued separately by
`licensing_server`. `OfflineLicensingService.activate` verifies signature,
device binding, expiry, and entitlements, then `LicenseStore` persists client
license state separately from settings/projects. `ensure_usable_and_fresh`
re-verifies the stored token locally on each gated operation and `LicenseGuard`
requires `ACTIVATED`, non-expired state with a `render` entitlement. No network
call occurs in the current production licensing runtime.

The public key resolution order is:

1. `AUTOTUBE_LICENSE_PUBLIC_KEY` PEM text.
2. `AUTOTUBE_LICENSE_PUBLIC_KEY_FILE` path.
3. Bundled `license_public.pem` beside the module or frozen executable.

Missing or invalid verification material fails closed. Raw device identifiers
are namespace-hashed; do not collect usernames, hostnames, MAC addresses, or
hardware serials.

`licensing_server/` owns raw-key generation, SHA-256 key hashes/redacted database
records, Ed25519 private signing keys, token issuance, revocation data, and admin
commands. The raw generated key is shown once and never stored. Client code must
never import this package, and PyInstaller plus the artifact audit exclude it.

## GUI and Core Boundary

GUI tabs collect inputs and display concise safe errors. `gui/workers.py` runs
blocking work on `QThreadPool`, logs tracebacks, and emits finished/failed/
cancelled/progress signals. GUI entry points call core workflows and licensing
gates; core modules must not import Qt. Cancellation events must propagate into
network, transcription, timeline, and FFmpeg work, and partial outputs must be
cleaned without losing resumable state.

When testing GUI state, exercise the real Qt data conversion boundary rather
than only constructing domain dataclasses. `str, Enum` values can be converted
to plain strings by Qt `QVariant`, which is the source of a current timeline bug.

## FFmpeg and Media Rules

FFmpeg and FFprobe are required but not bundled by default. Detection checks
`PATH`, then `<install-dir>\ffmpeg\ffmpeg.exe` and `ffprobe.exe`. All media
subprocesses go through `FFmpegRunner` with argument lists, `shell=False`,
bounded stderr, timeouts, cancellation, terminate/grace/kill handling, and
redacted errors. Use paths and probe metadata instead of loading media bytes.

Atomic media outputs use application-owned partial paths and promote only on
success. Re-encode when frame accuracy or normalization requires it. Stock audio
must never leak into the final output: visual clips are video-only and the final
audio comes only from voiceover plus optional music. Final validation checks
video/audio presence, exactly one audio stream, resolution, and FPS tolerance.

## Testing Strategy

Use the repository virtual environment. Run a focused baseline before changes,
the same test after each change, then the offline suite:

```powershell
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pytest tests\path\to\test_file.py -q
.venv\Scripts\python.exe -m pytest -m "not integration" -q
.venv\Scripts\python.exe -m pytest -q
```

The normal suite must require no network, real API credentials, user config
writes, or model downloads. Tests isolate `%APPDATA%` side effects through
fixtures. Never expose secret values while checking prerequisites; print only
set/unset. A skipped integration is unverified coverage, not a pass or failure.

Optional real integrations are gated as follows:

| Coverage | Gate and prerequisite |
| --- | --- |
| FFmpeg unit/integration | FFmpeg and FFprobe resolvable; `integration` marker |
| Whisper | `AUTOTUBE_RUN_WHISPER_TESTS=1`; `AUTOTUBE_TEST_SPEECH_WAV` and model access |
| Stock | `AUTOTUBE_RUN_STOCK_TESTS=1`; Pexels/Pixabay key(s) |
| AI | `AUTOTUBE_RUN_AI_TESTS=1`; selected provider key |
| Full pipeline | `AUTOTUBE_RUN_E2E_TESTS=1`; declared fixtures/tools |
| Timeline media | `AUTOTUBE_RUN_TIMELINE_TESTS=1`; FFmpeg/FFprobe |
| Timeline render | `AUTOTUBE_RUN_TIMELINE_RENDER_TESTS=1`; FFmpeg/FFprobe |
| Transitions | `AUTOTUBE_RUN_TRANSITION_TESTS=1`; FFmpeg/FFprobe |

Do not add an integration gate without registering its pytest marker where
appropriate. Never weaken unit tests because an optional integration is absent.

## Packaging and Release

The Windows one-folder build uses PyInstaller and is wrapped by Inno Setup.
FFmpeg is intentionally excluded unless licensed binaries are copied into the
documented bundled folder after build. Build and audit the actual artifact:

```powershell
.venv\Scripts\python.exe -m PyInstaller --clean packaging\autotube.spec
.venv\Scripts\python.exe packaging\verify_artifact.py dist\autotube
dist\autotube\autotube.exe --version
ISCC.exe packaging\installer.iss
```

The artifact audit must find no tests, pytest, `licensing_server`, private keys,
`.env`, or plausible raw secrets. Verify executable behavior with FFmpeg on
`PATH`, bundled fallback, and neither available. Keep version/product metadata
synchronized across `src/autotube/__init__.py`, `pyproject.toml`,
`packaging/version_info.txt`, and `packaging/installer.iss`. Authenticode signing
and clean-machine install/launch/render/uninstall checks are manual release gates;
user data under `%APPDATA%\AutoTube` must survive upgrades and default uninstall.

## Security Checklist

- API keys live in environment variables or DPAPI `secrets.json`, never normal
  settings, project JSON, logs, fixtures, source, or command output.
- Product keys, activation tokens, authorization headers, signed URL parameters,
  and traceback text pass through centralized source redaction plus logging
  filter and final formatter. Logging failure must not crash the app.
- TLS verification stays enabled. Retries are bounded with backoff and
  `Retry-After`; no unbounded loops or silent provider failures.
- The client contains public verification material only. Private signing keys,
  issuance, and licensing database state stay server-side and outside artifacts.
- Device binding transmits/persists only the stable namespace-hashed identifier.
- Cleanup is ownership-gated and never follows symlinks or deletes user media.

## Interrupted-Session Recovery

After any interruption, takeover, or suspected partial tool execution, do this
before editing:

1. Read the durable handoff and public architecture:

```powershell
Get-Content AGENTS.md
Get-Content docs\AI_DEVELOPMENT.md
Get-Content README.md
Get-Content docs\architecture.md
```

2. Inspect the actual workspace rather than assuming Git or the previous command
   succeeded:

```powershell
Get-ChildItem -Force
Get-Item AGENTS.md,docs\AI_DEVELOPMENT.md | Select-Object FullName,Length,LastWriteTime
rg -n "Current Known Issues|in_progress|TODO|FIXME|TEMPORARY" AGENTS.md docs src tests
```

If `git` and `.git` exist, also run `git status --short` and inspect diffs. If
they do not, explicitly record that limitation and track touched files manually.

3. Re-open every file the interrupted task intended to change. Compare its
   contents and timestamps with the saved plan/output. Preserve completed work;
   fill only verified gaps. If an unexpected external edit conflicts with the
   task, stop and ask the user.
4. Reproduce the current baseline with the commands under `First Commands` and
   compare results with the dated issues below. Do not misclassify known failures
   as regressions or assume an old issue still exists.
5. Write/update the plan, state files in scope, security/migration/test impact,
   acceptance criteria, and non-goals. Stop for approval before major decisions.
6. During implementation, test the narrow path before and after edits, then the
   full offline suite. Before stopping again, verify intended files are durably
   saved, report exact commands/results, list unverified integration coverage,
   and leave a clear next command. Never claim completion with a required item
   missing.

## First Commands

Future agents should start with these read-only checks:

```powershell
.venv\Scripts\python.exe --version
Test-Path src\autotube\licensing\client.py
.venv\Scripts\python.exe -m pytest tests\licensing\test_runtime.py --collect-only -q
.venv\Scripts\python.exe -m pytest tests\timeline tests\gui\test_timeline_tab.py -m "not integration" -q
.venv\Scripts\python.exe -m pytest -m "not integration" -q
```

For the real timeline GUI boundary, run this from PowerShell:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.venv\Scripts\python.exe -c "from PySide6.QtWidgets import QApplication; from autotube.gui.timeline_tab import TimelineTab; from autotube.state import ProjectState; from autotube.timeline.staleness import timeline_input_fingerprint; app=QApplication.instance() or QApplication([]); tab=TimelineTab(); state=ProjectState(); tab.set_state(state); print(type(state.timeline.transition_settings.effect_mode).__name__); print(timeline_input_fingerprint(state))"
```

## Current Known Issues (2026-08-20)

1. **Licensing runtime test cannot collect.**
   `src/autotube/licensing/client.py` does not exist, but
   `tests/licensing/test_runtime.py` imports `LicensingClient` and
   `needs_revalidation`. Production `licensing/runtime.py` is explicitly
   offline-only and exposes no `needs_revalidation`; the test describes an older
   online revalidation/offline-grace contract. `pytest -q` stops at collection
   with `ModuleNotFoundError: No module named 'autotube.licensing.client'`.
2. **Timeline GUI stores strings where enums are required.**
   PySide6 returns plain `str` data for the `TransitionEffectMode` and
   `TransitionSoundMode` values added to `QComboBox`. `TimelineTab.set_state`
   triggers `_persist_transition_settings`, so `effect_mode`/`sound_mode` become
   strings. `timeline_input_fingerprint` then accesses `.value` and raises
   `AttributeError: 'str' object has no attribute 'value'`. The offscreen command
   above reproduces it. The existing offline timeline selection passes 105 tests
   because it does not exercise this GUI-to-fingerprint path.
3. **Current guard and older guard test disagree.**
   Current `LicenseGuard` requires `ACTIVATED`, a
   non-expired state, and the `render` entitlement. The older
   `test_activated_and_grace_allow` constructs entitlement-free `ACTIVATED` and
   `OFFLINE_GRACE` states and fails; the targeted module currently reports one
   failure and six passes. Resolve the intended contract explicitly rather than
   weakening the guard or test opportunistically.
4. **CLI tests have leaked project files into the repository root.**
   UUID-named JSON files are generated project states with temporary test paths.
   They are not maintained examples or design truth. Do not delete them without
   user instruction; future test work should verify isolation without hiding the
   underlying leak.

Re-verify every item before carrying it forward. Remove resolved entries and
date new findings. Do not turn a temporary defect into an architecture rule.

## Documentation Ownership

- `README.md`: user setup, commands, requirements, troubleshooting.
- `docs/architecture.md`: public layers, workflow, stage and state design.
- `docs/packaging.md`: build, installer, FFmpeg placement, artifact audit.
- `docs/RELEASE.md`: release acceptance and manual gates.
- `AGENTS.md`: short mandatory AI rules/invariants only.
- `docs/AI_DEVELOPMENT.md`: this detailed AI runbook and dated known issues.

Do not add another general AI helper document. Update these files when commands,
boundaries, extension patterns, recovery steps, or verified blockers change.