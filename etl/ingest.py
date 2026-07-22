from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
import yt_dlp
from psycopg.types.json import Jsonb
from youtube_transcript_api import YouTubeTranscriptApi

from etl.evidence import extract_claims
from etl.matcher import SalesCatalogue, pair_key


PLAYLISTS = {
    "PLlJFhpC4T6dIzSUQTmDX0QT7GmwAlHu2q": "walkthrough",
    "PLlJFhpC4T6dJjkBX4zMAgMpUV-iyrzUfE": "test_drive",
}

NODE_RUNTIME = "/Users/adrianstock/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"


def discover_playlists() -> list[dict[str, Any]]:
    videos: dict[str, dict[str, Any]] = {}
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True, "skip_download": True, "js_runtimes": {"node": {"path": NODE_RUNTIME}}}) as ydl:
        for playlist_id, video_type in PLAYLISTS.items():
            url = f"https://www.youtube.com/playlist?list={playlist_id}"
            info = ydl.extract_info(url, download=False)
            for position, item in enumerate(info.get("entries") or []):
                video_id = item["id"]
                video = videos.setdefault(video_id, {
                    "youtube_video_id": video_id,
                    "title": item.get("title") or "",
                    "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                    "playlists": [],
                })
                video["playlists"].append({
                    "youtube_playlist_id": playlist_id,
                    "playlist_title": info.get("title") or playlist_id,
                    "video_type": video_type,
                    "position": position,
                    "source_url": url,
                })
    return list(videos.values())


def fetch_video(video: dict[str, Any], include_comments: bool = True) -> dict[str, Any]:
    options = {
        "quiet": True,
        "skip_download": True,
        "getcomments": include_comments,
        "extractor_args": {"youtube": {"comment_sort": ["top"], "max_comments": ["50"]}},
        "js_runtimes": {"node": {"path": NODE_RUNTIME}},
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(video["youtube_url"], download=False)

    transcript_segments: list[dict[str, Any]] = []
    transcript_error = None
    try:
        transcript = YouTubeTranscriptApi().fetch(video["youtube_video_id"], languages=["en"])
        transcript_segments = [
            {"sequence": index, "start": row.start, "duration": row.duration, "text": row.text}
            for index, row in enumerate(transcript)
        ]
    except Exception as exc:
        transcript_error = f"{type(exc).__name__}: {exc}"

    comments = []
    for rank, item in enumerate((info.get("comments") or [])[:50], 1):
        comments.append({
            "id": item.get("id"),
            "rank": rank,
            "text": item.get("text") or "",
            "like_count": item.get("like_count") or 0,
            "reply_count": item.get("reply_count") or 0,
            "timestamp": item.get("timestamp"),
        })

    return {
        **video,
        "title": info.get("title") or video["title"],
        "description": info.get("description") or "",
        "thumbnail_url": info.get("thumbnail"),
        "duration_seconds": info.get("duration"),
        "upload_date": info.get("upload_date"),
        "location": info.get("location"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "comment_count": info.get("comment_count"),
        "tags": info.get("tags") or [],
        "comments": comments,
        "transcript_segments": transcript_segments,
        "transcript_error": transcript_error,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def upload_date(value: str | None):
    if not value:
        return None
    return datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc)


def store_postgres(conn: psycopg.Connection, item: dict[str, Any], identity) -> None:
    conn.execute(
        """
        INSERT INTO source_videos (
          youtube_video_id, title, description, youtube_url, thumbnail_url, duration_seconds,
          published_at, location_text, view_count, like_count, comment_count,
          make, model, full_name, length_feet, identity_confidence, identity_method, identity_review_status, metadata, fetched_at
        ) VALUES (
          %(youtube_video_id)s, %(title)s, %(description)s, %(youtube_url)s, %(thumbnail_url)s,
          %(duration_seconds)s, %(published_at)s, %(location)s, %(view_count)s, %(like_count)s,
          %(comment_count)s, %(make)s, %(model)s, %(full_name)s, %(length_feet)s,
          %(confidence)s, %(method)s, %(review_status)s, %(metadata)s, now()
        )
        ON CONFLICT (youtube_video_id) DO UPDATE SET
          title = excluded.title, description = excluded.description, thumbnail_url = excluded.thumbnail_url,
          duration_seconds = excluded.duration_seconds, published_at = excluded.published_at,
          location_text = excluded.location_text, view_count = excluded.view_count,
          like_count = excluded.like_count, comment_count = excluded.comment_count,
          make = excluded.make, model = excluded.model, full_name = excluded.full_name,
          length_feet = excluded.length_feet, identity_confidence = excluded.identity_confidence,
          identity_method = excluded.identity_method, identity_review_status = excluded.identity_review_status,
          metadata = excluded.metadata, fetched_at = now()
        """,
        {
            **item,
            "published_at": upload_date(item.get("upload_date")),
            **asdict(identity),
            "review_status": "auto_accepted" if identity.make and identity.model and identity.length_feet and identity.confidence >= 0.84 else "needs_review",
            "metadata": Jsonb({"tags": item.get("tags", []), "transcript_error": item.get("transcript_error")}),
        },
    )
    boat_id = None
    if identity.make and identity.model and identity.length_feet is not None and identity.confidence >= 0.84:
        boat_id = conn.execute(
            """
            INSERT INTO boats (make, model, full_name, length_feet, evidence_confidence)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (make, model) DO UPDATE SET
              full_name = excluded.full_name,
              length_feet = COALESCE(boats.length_feet, excluded.length_feet),
              evidence_confidence = GREATEST(boats.evidence_confidence, excluded.evidence_confidence)
            RETURNING id
            """,
            (identity.make, identity.model, identity.full_name, identity.length_feet, identity.confidence),
        ).fetchone()[0]
    conn.execute(
        "INSERT INTO video_metric_snapshots (youtube_video_id, view_count, like_count, comment_count) VALUES (%s, %s, %s, %s)",
        (item["youtube_video_id"], item.get("view_count"), item.get("like_count"), item.get("comment_count")),
    )
    for playlist in item["playlists"]:
        conn.execute(
            """
            INSERT INTO source_playlists (youtube_playlist_id, title, video_type, source_url)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (youtube_playlist_id) DO UPDATE SET title = excluded.title, refreshed_at = now()
            """,
            (playlist["youtube_playlist_id"], playlist["playlist_title"], playlist["video_type"], playlist["source_url"]),
        )
        conn.execute(
            """
            INSERT INTO playlist_videos (youtube_playlist_id, youtube_video_id, playlist_position)
            VALUES (%s, %s, %s)
            ON CONFLICT (youtube_playlist_id, youtube_video_id) DO UPDATE SET playlist_position = excluded.playlist_position
            """,
            (playlist["youtube_playlist_id"], item["youtube_video_id"], playlist["position"]),
        )
        if boat_id:
            conn.execute(
                """
                INSERT INTO boat_videos (boat_id, youtube_video_id, video_type, match_confidence, match_method)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (boat_id, youtube_video_id, video_type) DO UPDATE SET
                  match_confidence = excluded.match_confidence, match_method = excluded.match_method
                """,
                (boat_id, item["youtube_video_id"], playlist["video_type"], identity.confidence, identity.method),
            )

    segments = item.get("transcript_segments") or []
    if segments:
        full_text = " ".join(segment["text"] for segment in segments)
        checksum = hashlib.sha256(full_text.encode()).hexdigest()
        conn.execute(
            """
            INSERT INTO video_transcripts (youtube_video_id, language, source, is_generated, full_text, checksum)
            VALUES (%s, 'en', %s, true, %s, %s)
            ON CONFLICT (youtube_video_id) DO UPDATE SET source = excluded.source,
              full_text = excluded.full_text, checksum = excluded.checksum, fetched_at = now()
            """,
            (item["youtube_video_id"], item.get("transcript_source") or "youtube_transcript_api", full_text, checksum),
        )
        conn.execute("DELETE FROM transcript_segments WHERE youtube_video_id = %s", (item["youtube_video_id"],))
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO transcript_segments (youtube_video_id, sequence, start_seconds, duration_seconds, segment_text)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [(item["youtube_video_id"], segment["sequence"], segment["start"], segment["duration"], segment["text"]) for segment in segments],
            )
        conn.execute("DELETE FROM evidence_claims WHERE youtube_video_id = %s", (item["youtube_video_id"],))
        if boat_id:
            claims = extract_claims(item)
            with conn.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO evidence_claims (
                      boat_id, youtube_video_id, start_seconds, end_seconds, claim_type,
                      topic, missions, evidence_text, confidence, editorial_status
                    ) VALUES (%s, %s, %s, %s, 'transcript_rule', %s, %s, %s, 0.800, 'pending')
                    """,
                    [
                        (
                            boat_id, item["youtube_video_id"], claim["start_seconds"], claim["end_seconds"],
                            claim["topic"], claim["missions"], claim["evidence_text"],
                        )
                        for claim in claims
                    ],
                )

    for comment in item.get("comments") or []:
        if not comment["id"]:
            continue
        published = datetime.fromtimestamp(comment["timestamp"], timezone.utc) if comment.get("timestamp") else None
        conn.execute(
            """
            INSERT INTO video_comments (youtube_comment_id, youtube_video_id, relevance_rank, comment_text, like_count, reply_count, published_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (youtube_comment_id) DO UPDATE SET relevance_rank = excluded.relevance_rank,
              comment_text = excluded.comment_text, like_count = excluded.like_count,
              reply_count = excluded.reply_count, fetched_at = now()
            """,
            (comment["id"], item["youtube_video_id"], comment["rank"], comment["text"], comment["like_count"], comment["reply_count"], published),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Dan's two power-boat playlists")
    parser.add_argument("--sales-db", required=True)
    parser.add_argument("--output", default="data/raw/youtube")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--skip-comments", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    catalogue = SalesCatalogue(args.sales_db)
    videos = discover_playlists()
    if args.limit:
        videos = videos[: args.limit]

    conn = psycopg.connect(args.database_url) if args.database_url else None
    report = {"discovered": len(videos), "imported": 0, "failed": 0, "failures": [], "unmatched": 0, "pairs": {}}
    try:
        for index, video in enumerate(videos, 1):
            destination = output / f"{video['youtube_video_id']}.json"
            try:
                if args.resume and destination.exists():
                    item = json.loads(destination.read_text())
                else:
                    item = fetch_video(video, include_comments=not args.skip_comments)
                    destination.write_text(json.dumps(item, ensure_ascii=False))
                identity = catalogue.match(item["title"], item.get("description") or "", item["youtube_video_id"])
                key = pair_key(identity)
                item["boat_identity"] = asdict(identity)
                destination.write_text(json.dumps(item, ensure_ascii=False))
                if key:
                    report["pairs"].setdefault(key, []).append({
                        "video_id": item["youtube_video_id"],
                        "types": [row["video_type"] for row in item["playlists"]],
                        "confidence": identity.confidence,
                    })
                else:
                    report["unmatched"] += 1
                if conn:
                    store_postgres(conn, item, identity)
                    conn.commit()
                report["imported"] += 1
                print(f"[{index}/{len(videos)}] {identity.full_name or 'REVIEW'} - {item['title']}", flush=True)
            except Exception as exc:
                if conn:
                    conn.rollback()
                report["failed"] += 1
                report["failures"].append({"video_id": video["youtube_video_id"], "title": video.get("title"), "error": f"{type(exc).__name__}: {exc}"})
                print(f"[{index}/{len(videos)}] FAILED {video['youtube_video_id']}: {exc}", flush=True)
            time.sleep(0.35)
    finally:
        if conn:
            conn.close()
        report["paired_models"] = sum(
            1 for videos_for_boat in report["pairs"].values()
            if {kind for video in videos_for_boat for kind in video["types"]} >= {"walkthrough", "test_drive"}
        )
        report_path = output.parent.parent / "reports" / "youtube-ingestion.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2))
        print(json.dumps({key: value for key, value in report.items() if key != "pairs"}, indent=2))


if __name__ == "__main__":
    main()
