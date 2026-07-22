from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

import mlx_whisper
import static_ffmpeg
import yt_dlp

from etl.ingest import NODE_RUNTIME


DEFAULT_MODEL = "mlx-community/whisper-base.en-mlx"


def transcribe_video(item: dict, model: str) -> list[dict]:
    static_ffmpeg.add_paths()
    with tempfile.TemporaryDirectory(prefix="dbl-asr-") as temporary:
        outtmpl = str(Path(temporary) / "%(id)s.%(ext)s")
        options = {
            "quiet": True,
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": outtmpl,
            "js_runtimes": {"node": {"path": NODE_RUNTIME}},
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(item["youtube_url"], download=True)
            candidate = Path(ydl.prepare_filename(info))
        if not candidate.exists():
            matches = list(Path(temporary).glob(f"{item['youtube_video_id']}.*"))
            if not matches:
                raise FileNotFoundError("yt-dlp did not produce an audio file")
            candidate = matches[0]
        result = mlx_whisper.transcribe(
            str(candidate),
            path_or_hf_repo=model,
            language="en",
            verbose=False,
            temperature=0,
        )
        return [
            {
                "sequence": index,
                "start": float(segment["start"]),
                "duration": max(float(segment["end"]) - float(segment["start"]), 0.1),
                "text": segment["text"].strip(),
            }
            for index, segment in enumerate(result.get("segments") or [])
            if segment.get("text", "").strip()
        ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Locally transcribe playlist records whose caption tracks are unavailable or throttled")
    parser.add_argument("--input", default="data/raw/youtube")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--delay", type=float, default=0.4)
    args = parser.parse_args()

    pending = []
    for path in sorted(Path(args.input).glob("*.json")):
        item = json.loads(path.read_text())
        if not item.get("transcript_segments"):
            pending.append((path, item))
    if args.limit:
        pending = pending[:args.limit]

    completed = 0
    failures = []
    for index, (path, item) in enumerate(pending, 1):
        video_id = item["youtube_video_id"]
        try:
            segments = transcribe_video(item, args.model)
            if not segments:
                raise ValueError("local ASR returned no segments")
            item["transcript_segments"] = segments
            item["transcript_source"] = f"local_asr:{args.model}"
            item["transcript_error"] = None
            path.write_text(json.dumps(item, ensure_ascii=False))
            completed += 1
            print(f"[{index}/{len(pending)}] {video_id}: {len(segments)} ASR segments", flush=True)
        except Exception as exc:
            failures.append({"video_id": video_id, "error": f"{type(exc).__name__}: {exc}"})
            print(f"[{index}/{len(pending)}] FAILED {video_id}: {exc}", flush=True)
        time.sleep(args.delay)

    report_path = Path("data/reports/local-asr.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({"pending": len(pending), "completed": completed, "failures": failures}, indent=2))
    print(json.dumps({"pending": len(pending), "completed": completed, "failed": len(failures)}, indent=2))


if __name__ == "__main__":
    main()
