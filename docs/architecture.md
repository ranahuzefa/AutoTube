# Architecture

## Overview

AutoTube Creator is a desktop application that turns a script + voiceover into a
YouTube-ready MP4. It is built in phases. Phase 1 establishes the data, state,
persistence, and service-contract foundations.

## Layered Structure

- **Models** — plain `dataclass` domain objects with explicit JSON serialization.
- **State** — resumable pipeline state (stage states + segment states).
- **Storage** — atomic JSON persistence for projects and app settings.
- **Services** — `typing.Protocol` contracts implemented in later phases.
- **Pipeline** — state-aware orchestrator that resumes without repeating completed stages.
- **GUI** — PySide6 shell (Project, Workflow, Settings, Log tabs).
- **CLI** — headless project creation, resume inspection, and version reporting.

## Pipeline Stage Model

Ordered stages map one-to-one to the master workflow:

1. `TRANSCRIBED` — Whisper transcription.
2. `SEGMENTS_READY` — segment boundaries/timings.
3. `KEYWORDS_READY` — per-segment visual keywords.
4. `ASSETS_READY` — stock search candidates.
5. `CLIPS_READY` — downloaded/trimmed/looped/cropped/scaled clips.
6. `COMPOSED` — base video assembled.
7. `AUDIO_READY` — voiceover + BGM mixed.
8. `CAPTIONS_READY` — captions rendered.
9. `COMPLETED` — final validation.

Audio mixing and captions are explicit stages, never hidden inside composition.

## State & Resume

Each `ProjectState` holds one `StageState` per stage plus segment states and error
information. Completed/skipped stages are not repeated unless forced. `project.json`
is written atomically so an interrupted run is never left half-written.
