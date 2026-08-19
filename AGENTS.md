# AutoTube Creator Agent Rules

Read `docs/AI_DEVELOPMENT.md` before planning or changing this repository. These
rules are mandatory. Current source and tests are authoritative over old phase
language in prose, but a source/test conflict must be surfaced, not guessed away.

## Required Workflow

1. Inspect the current filesystem, affected source, neighboring tests,
   serializers, and packaging impact before proposing work. After an interrupted
   session, follow the recovery procedure in `docs/AI_DEVELOPMENT.md`; never
   assume the previous operation completed or restart completed work.
2. Write or update a concrete plan before implementation. Run relevant baseline
   tests before edits, make the smallest coherent change, run focused tests after
   each change, then run the offline suite.
3. Never delete, disable, loosen, or mock away an existing test to make it pass.
   Distinguish failures from intentionally skipped integration coverage.
4. Stop for explicit user approval before changing major architecture, the
   persisted schema strategy, pipeline stages, licensing trust boundaries,
   dependency strategy, or the authoritative render path.
5. Preserve user changes and generated artifacts unless deletion was explicitly
   requested. Do not claim a clean worktree when Git was not actually available.

## Architecture Invariants

- Keep the nine persisted `PipelineStage` names and order stable: `transcribed`,
  `segments_ready`, `keywords_ready`, `assets_ready`, `clips_ready`, `composed`,
  `audio_ready`, `captions_ready`, `completed`. Reuse them unless an explicitly
  approved migration proves a change unavoidable.
- Preserve resumability: completed/skipped stages stay skipped unless forced,
  each stage is durably saved before dependants run, failed work remains
  resumable, and timeline input changes invalidate only render stages.
- Keep dataclasses with explicit `to_dict`/`from_dict`. Persist additively with
  safe defaults for missing keys, atomic temp-file plus flush/fsync plus
  `os.replace`, and legacy-payload and round-trip tests.
- Keep GUI widgets in `src/autotube/gui/`. Core, services, media, timeline,
  transcription, stock, AI, and licensing modules must not import GUI code.
  Blocking GUI work belongs in workers and must support cancellation.
- FFmpeg/FFprobe remain the media engine. Use direct argument lists with
  `shell=False`, paths rather than in-memory media, atomic outputs, bounded
  stderr, timeout/cancel terminate-kill behavior, and Windows-safe filenames.
- Visual assets remain video-only. Final audio is voiceover plus optional music,
  and the final mux must contain the intended video and exactly one audio stream.
- External capabilities stay behind domain-specific `Protocol`, registry/spec,
  config, and factory boundaries. Keep bounded requests/retries/timeouts,
  response validation, transactional state application, caching, deterministic
  fallback, and no core dependency on optional providers.
- `src/autotube/licensing/` is verification-only and offline at runtime.
  Generation, issuance, database access, and private signing keys stay solely in
  `licensing_server/`, which must never be imported or shipped by the client.
- Never log, print, commit, or persist raw API keys, product keys, activation
  tokens, signed URL credentials, private keys, or raw device identifiers. Use
  environment overrides, DPAPI secret storage, hashed identifiers, fail-closed
  public-key loading, and centralized defense-in-depth redaction.
- Avoid new dependencies unless the need and supported Windows/Python wheels are
  verified. Do not replace existing stdlib, FFmpeg, protocol, or registry
  infrastructure with a heavier framework without approval.
- Cleanup may remove only clearly application-owned partial files. Never remove
  user assets, final outputs, resumable intermediates, directories, or symlinks.

## Documentation Boundary

Keep this file short and mandatory. Put architecture details, commands, recovery
steps, extension procedures, and dated `Current Known Issues` in
`docs/AI_DEVELOPMENT.md`. Do not create another AI helper file unless it has a
genuinely separate purpose that cannot fit these two files.