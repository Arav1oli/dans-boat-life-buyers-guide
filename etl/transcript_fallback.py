from __future__ import annotations

import argparse
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

import certifi


ENDPOINT = "https://youtube-transcript.ai/transcript/{video_id}.txt"
TIMESTAMP = re.compile(r"^\[(?:(\d+):)?(\d+):(\d+)\]\s*(.*)$")


def collapse_tandem_repeats(text: str) -> str:
    """Remove exact adjacent repeated caption phrases without paraphrasing."""
    words = text.split()
    cleaned: list[str] = []
    index = 0
    while index < len(words):
        max_size = min(60, (len(words) - index) // 2)
        repeat_size = 0
        for size in range(max_size, 0, -1):
            if words[index:index + size] == words[index + size:index + (2 * size)]:
                repeat_size = size
                break
        if repeat_size:
            chunk = words[index:index + repeat_size]
            cleaned.extend(chunk)
            index += repeat_size
            while words[index:index + repeat_size] == chunk:
                index += repeat_size
        else:
            cleaned.append(words[index])
            index += 1
    return " ".join(cleaned)


def parse_markdown(markdown: str) -> list[dict]:
    blocks: list[tuple[float, str]] = []
    current_start: float | None = None
    current_text: list[str] = []
    in_transcript = False
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line == "## Transcript":
            in_transcript = True
            continue
        if not in_transcript:
            continue
        if line == "---":
            break
        match = TIMESTAMP.match(line)
        if match:
            if current_start is not None:
                blocks.append((current_start, collapse_tandem_repeats(" ".join(current_text))))
            hours = int(match.group(1) or 0)
            current_start = hours * 3600 + int(match.group(2)) * 60 + int(match.group(3))
            current_text = [match.group(4)]
        elif current_start is not None and line:
            current_text.append(line)
    if current_start is not None:
        blocks.append((current_start, collapse_tandem_repeats(" ".join(current_text))))
    return [
        {
            "sequence": index,
            "start": start,
            "duration": max((blocks[index + 1][0] - start) if index + 1 < len(blocks) else 5, 0.1),
            "text": text,
        }
        for index, (start, text) in enumerate(blocks)
        if text
    ]


def fetch(video_id: str, timeout: int = 45) -> str:
    request = urllib.request.Request(
        ENDPOINT.format(video_id=video_id),
        headers={"User-Agent": "DansBoatLifeGuide/1.0 (transcript research authorised by channel owner)"},
    )
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
        return response.read().decode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill blocked transcript records through a free timestamped caption endpoint")
    parser.add_argument("--input", default="data/raw/youtube")
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--retries", type=int, default=6)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    paths = sorted(Path(args.input).glob("*.json"))
    pending = []
    for path in paths:
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
            segments = []
            last_error = None
            for attempt in range(args.retries):
                try:
                    markdown = fetch(video_id)
                    segments = parse_markdown(markdown)
                    if segments:
                        break
                    last_error = f"no timestamped segments; response starts {markdown[:160]!r}"
                except urllib.error.HTTPError as exc:
                    last_error = f"HTTP {exc.code}"
                    if exc.code not in {429, 500, 502, 503, 504}:
                        raise
                if attempt + 1 < args.retries:
                    backoff = min(8 * (attempt + 1), 40)
                    print(f"[{index}/{len(pending)}] retry {video_id} in {backoff}s ({last_error})", flush=True)
                    time.sleep(backoff)
            if not segments:
                raise ValueError(last_error or "fallback returned no timestamped transcript segments")
            item["transcript_segments"] = segments
            item["transcript_source"] = "youtube-transcript.ai"
            item["transcript_error"] = None
            path.write_text(json.dumps(item, ensure_ascii=False))
            completed += 1
            print(f"[{index}/{len(pending)}] {video_id}: {len(segments)} segments", flush=True)
        except (OSError, urllib.error.URLError, ValueError) as exc:
            failures.append({"video_id": video_id, "error": f"{type(exc).__name__}: {exc}"})
            print(f"[{index}/{len(pending)}] FAILED {video_id}: {exc}", flush=True)
        time.sleep(args.delay)

    report_path = Path("data/reports/transcript-fallback.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({"pending": len(pending), "completed": completed, "failures": failures}, indent=2))
    print(json.dumps({"pending": len(pending), "completed": completed, "failed": len(failures)}, indent=2))


if __name__ == "__main__":
    main()
