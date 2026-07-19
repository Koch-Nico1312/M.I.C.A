"""M.I.C.A action gateway for the optional video-use production helpers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from core.video_production import get_video_production_manager


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _helper_root(params: dict[str, Any]) -> Path | None:
    raw = str(params.get("helper_root") or os.getenv("MICA_VIDEO_USE_ROOT") or "").strip()
    if not raw:
        return None
    root = Path(raw).expanduser()
    return root.resolve() if root.exists() else None


def _status(params: dict[str, Any]) -> dict[str, Any]:
    root = _helper_root(params)
    return {
        "configured": root is not None,
        "helper_root": str(root) if root else None,
        "ffmpeg": shutil.which("ffmpeg"),
        "ffprobe": shutil.which("ffprobe"),
        "elevenlabs_key": bool(os.getenv("ELEVENLABS_API_KEY")),
        "external_execution": "opt-in via helper_root or MICA_VIDEO_USE_ROOT",
    }


def _run_helper(params: dict[str, Any], project: dict[str, Any], stage: str) -> dict[str, Any]:
    root = _helper_root(params)
    if root is None:
        raise ValueError("video-use helpers are not configured; use setup_preview")
    helpers = root / "helpers"
    edit_dir = Path(project["edit_dir"])
    commands: dict[str, list[str]] = {
        "transcribe": [sys.executable, str(helpers / "transcribe_batch.py"), project["source_dir"]],
        "pack": [sys.executable, str(helpers / "pack_transcripts.py"), "--edit-dir", str(edit_dir)],
        "preview": [
            sys.executable,
            str(helpers / "render.py"),
            str(edit_dir / "edl.json"),
            "-o",
            str(edit_dir / "preview.mp4"),
            "--preview",
            "--build-subtitles",
        ],
        "render": [
            sys.executable,
            str(helpers / "render.py"),
            str(edit_dir / "edl.json"),
            "-o",
            str(edit_dir / "final.mp4"),
            "--build-subtitles",
        ],
    }
    if stage not in commands:
        raise ValueError("run_stage must be transcribe, pack, preview, or render")
    command = commands[stage]
    if not Path(command[1]).is_file():
        raise ValueError(f"video-use helper is missing: {command[1]}")
    if stage in {"preview", "render"} and not (edit_dir / "edl.json").is_file():
        raise ValueError("edit/edl.json is required before rendering")
    completed = subprocess.run(
        command,
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=max(30, min(3600, int(params.get("timeout", 1800)))),
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "video helper failed")[-4000:])
    artifacts = {
        "transcripts": str(edit_dir / "transcripts"),
        "packed_transcript": str(edit_dir / "takes_packed.md"),
        "preview": str(edit_dir / "preview.mp4"),
        "render": str(edit_dir / "final.mp4"),
    }
    return {
        "command": command,
        "stdout": completed.stdout[-4000:],
        "artifact": artifacts[stage],
    }


def video_production(parameters: dict, player=None, speak=None, **kwargs) -> str:
    params = parameters or {}
    action = str(params.get("action") or "status").strip().lower().replace("-", "_")
    manager = get_video_production_manager()

    try:
        if action == "status":
            return _json({**_status(params), **manager.list()})
        if action == "setup_preview":
            return _json(
                {
                    "automatic_changes": False,
                    "steps": [
                        "Review browser-use/video-use and its MIT license.",
                        "Install ffmpeg/ffprobe and video-use in a separate local directory.",
                        "Set MICA_VIDEO_USE_ROOT to that directory.",
                        "Set ELEVENLABS_API_KEY only when transcription is approved.",
                    ],
                }
            )
        if action == "create":
            return _json(manager.create(str(params.get("source_dir") or ""), name=str(params.get("name") or "")))
        if action == "list":
            return _json(manager.list())
        project_id = str(params.get("project_id") or "").strip()
        if action == "get":
            return _json(manager.get(project_id))
        if action == "plan":
            return _json(
                manager.propose(
                    project_id,
                    str(params.get("strategy") or ""),
                    params.get("specifications") if isinstance(params.get("specifications"), dict) else {},
                )
            )
        if action in {"approve", "reject"}:
            return _json(manager.approve(project_id, action == "approve", note=str(params.get("note") or "")))
        if action == "run_stage":
            project = manager.get(project_id)
            if not project.get("approved_at"):
                raise ValueError("video strategy must be approved before execution")
            stage = str(params.get("stage") or "").strip().lower()
            result = _run_helper(params, project, stage)
            updated = manager.record_stage(
                project_id,
                stage,
                artifacts={stage: result["artifact"]},
                note="video-use helper completed",
            )
            return _json({"project": updated, "execution": result})
        if action == "evaluate":
            return _json(
                manager.record_evaluation(
                    project_id,
                    passed=bool(params.get("passed", False)),
                    issues=params.get("issues") if isinstance(params.get("issues"), list) else [],
                    evidence=params.get("evidence") if isinstance(params.get("evidence"), dict) else {},
                )
            )
        if action == "finalize":
            return _json(manager.finalize(project_id, str(params.get("final_path") or "")))
        raise ValueError("unknown action")
    except Exception as exc:
        return _json({"success": False, "error": str(exc), "action": action})


TOOL_DECLARATION = {
    "name": "video_production",
    "description": "Plans and runs an approval-gated, self-evaluating local video production pipeline.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "status | setup_preview | create | list | get | plan | approve | reject | run_stage | evaluate | finalize"},
            "project_id": {"type": "STRING"},
            "source_dir": {"type": "STRING"},
            "name": {"type": "STRING"},
            "strategy": {"type": "STRING"},
            "specifications": {"type": "OBJECT"},
            "stage": {"type": "STRING", "description": "transcribe | pack | preview | render"},
            "passed": {"type": "BOOLEAN"},
            "issues": {"type": "ARRAY", "items": {"type": "STRING"}},
            "evidence": {"type": "OBJECT"},
            "final_path": {"type": "STRING"},
        },
        "required": [],
    },
}
