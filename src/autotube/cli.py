"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .licensing.device import current_device_id_hash
from .licensing.offline import OfflineLicensingService
from .licensing.storage import LicenseStore
from .logging_setup import setup_logging
from .models import Project, RenderSettings
from .state import ProjectState, STAGE_ORDER
from .storage import ProjectStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autotube",
        description="AutoTube Creator — script + voiceover to YouTube video.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--gui", action="store_true", help="Launch the PySide6 GUI (default).")
    parser.add_argument("--new", action="store_true", help="Create a new project.json.")
    parser.add_argument("--name", help="Project name (with --new).")
    parser.add_argument("--script", help="Path to script file (with --new).")
    parser.add_argument("--voiceover", help="Path to voiceover file (with --new).")
    parser.add_argument("--music", help="Optional background music file (with --new).")
    parser.add_argument("--output", default="output", help="Output directory (with --new).")
    parser.add_argument("--resume", metavar="PROJECT", help="Show next pending stage for a project.")
    parser.add_argument("--run", metavar="PROJECT", help="Run the full pipeline headlessly.")
    parser.add_argument("--force", action="store_true", help="With --run, re-run all stages.")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="With --run, render unresolved timeline visual slots as black.",
    )
    parser.add_argument("--license-status", action="store_true", help="Show license status.")
    parser.add_argument("--activate-key", help="Activate a product key (never logged).")
    parser.add_argument("--device-id", action="store_true", help="Show the machine device binding ID.")
    return parser


def _cmd_new(args: argparse.Namespace) -> int:
    from .models import validate_project, validate_render_settings

    project = Project(
        name=args.name or "Untitled",
        script_path=Path(args.script) if args.script else None,
        voiceover_path=Path(args.voiceover) if args.voiceover else None,
        music_path=Path(args.music) if args.music else None,
    )
    render = RenderSettings(output_dir=Path(args.output))

    try:
        validate_project(project)
        validate_render_settings(render)
    except Exception as exc:  # noqa: BLE001 - report validation clearly
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    state = ProjectState(project=project, render_settings=render)
    out_path = Path(f"{state.project_id}.json")
    ProjectStore().save(state, out_path)
    print(out_path)
    return 0


def _cmd_resume(args: argparse.Namespace) -> int:
    path = Path(args.resume)
    try:
        state = ProjectStore().load(path)
    except Exception as exc:  # noqa: BLE001 - report load error
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    next_stage = state.next_pending_stage()
    if next_stage is None:
        print("Pipeline complete.")
    else:
        print(next_stage.value)
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    from .config import load_settings
    from .media.detection import require_media_tooling
    from .media.service import FFmpegMediaService
    from .services.orchestrator import PipelineOrchestrator
    from .stock.cache import AssetCache
    from .stock.download import DownloadManager
    from .stock.factory import build_stock_providers
    from .stock.manager import StockManager
    from .stock.workflow import StockWorkflow
    from .timeline.composer import TimelineComposer
    from .transcription.workflow import TranscriptionWorkflow

    try:
        require_media_tooling()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 4

    try:
        from .licensing.runtime import ensure_usable_and_fresh

        ensure_usable_and_fresh(LicenseStore().load())
    except Exception as exc:  # noqa: BLE001 - non-sensitive license block
        print(f"License required: {exc}", file=sys.stderr)
        return 3

    path = Path(args.run)
    try:
        state = ProjectStore().load(path)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    settings = load_settings()
    media = FFmpegMediaService()

    transcription = TranscriptionWorkflow(project_path=None)
    from .ai import build_keyword_service

    keyword_service = build_keyword_service(settings)
    stock = StockWorkflow(
        keyword_service=keyword_service,
        stock_manager=StockManager(
            providers=build_stock_providers(settings),
            downloader=DownloadManager(AssetCache(Path("stock_cache"))),
            cache=AssetCache(Path("stock_cache")),
            media_service=media,
        ),
        project_path=None,
    )

    orchestrator = PipelineOrchestrator(
        transcription_workflow=transcription,
        stock_workflow=stock,
        media_service=media,
        store=ProjectStore(),
        project_path=path,
        timeline_composer=TimelineComposer(media),
    )

    try:
        orchestrator.run(state, force=args.force, allow_missing=args.allow_missing)
    except Exception as exc:  # noqa: BLE001 - report pipeline failure
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        return 1

    print(f"Pipeline complete: {state.stage(list(STAGE_ORDER)[-1]).artifacts}")
    return 0


def _cmd_license_status() -> int:
    state = LicenseStore().load()
    print(state.status.value)
    return 0


def _cmd_activate_key(key: str) -> int:
    if not key:
        print("Error: a product key is required.", file=sys.stderr)
        return 2
    try:
        state = OfflineLicensingService().activate(
            key, current_device_id_hash(), __version__
        )
        LicenseStore().save(state)
    except Exception as exc:  # noqa: BLE001 - never log the raw key
        print(f"Activation failed: {exc}", file=sys.stderr)
        return 1
    print(state.status.value)
    return 0


def _cmd_device_id() -> int:
    print(current_device_id_hash())
    return 0


def _cmd_gui() -> int:
    from .gui import run_app

    return run_app()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    import logging

    setup_logging()
    logger = logging.getLogger("autotube")

    try:
        if args.license_status:
            return _cmd_license_status()
        if args.activate_key:
            return _cmd_activate_key(args.activate_key)
        if args.device_id:
            return _cmd_device_id()
        if args.new:
            return _cmd_new(args)
        if args.resume:
            return _cmd_resume(args)
        if args.run:
            return _cmd_run(args)
        return _cmd_gui()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - top-level CLI boundary
        logger.exception("Unhandled CLI error")
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
