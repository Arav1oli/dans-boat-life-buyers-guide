from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

from .config import settings
from .db import connection
from .engine import score_boats
from .mailer import send_email


app = FastAPI(title="Dan's Boat Life Guide API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://arav1oli.github.io",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Resume-Token"],
)

ROOT = Path(__file__).resolve().parents[1]
GUIDE_DIR = ROOT / "guide"
ASSETS_DIR = ROOT / "assets"
app.mount("/guide", StaticFiles(directory=GUIDE_DIR, html=True), name="guide")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


class DecisionIn(BaseModel):
    question_id: str = Field(min_length=1, max_length=80)
    answer_value: Any
    answer_label: str = Field(min_length=1, max_length=240)


class CompleteIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    buyer_country_code: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    marketing_consent: bool = False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def require_session(public_id: UUID, token: str):
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM guide_sessions WHERE public_id = %s AND resume_token_hash = %s",
            (public_id, token_hash(token)),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Guide session not found")
    return row


def current_answers(session_id: UUID) -> dict[str, Any]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT question_id, answer_value, answer_label
            FROM guide_decisions
            WHERE session_id = %s AND is_current = true
            ORDER BY sequence
            """,
            (session_id,),
        ).fetchall()
    return {row["question_id"]: {"value": row["answer_value"], "label": row["answer_label"]} for row in rows}


@app.get("/")
def root():
    return FileResponse(ROOT / "index.html")


@app.get("/api/health")
def health():
    with connection() as conn:
        conn.execute("SELECT 1").fetchone()
    return {"ok": True}


@app.post("/api/sessions")
def create_session():
    token = secrets.token_urlsafe(32)
    with connection() as conn:
        row = conn.execute(
            "INSERT INTO guide_sessions (resume_token_hash) VALUES (%s) RETURNING id, public_id, started_at",
            (token_hash(token),),
        ).fetchone()
        conn.commit()
    return {
        "public_id": str(row["public_id"]),
        "resume_token": token,
        "started_at": row["started_at"],
        # Keep the secret in the URL fragment. Browsers do not send fragments in
        # HTTP requests or Referer headers; the guide JS forwards it explicitly.
        "resume_url": f"{settings.public_guide_url}?session={row['public_id']}#token={token}",
    }


@app.get("/api/sessions/{public_id}")
def get_session(public_id: UUID, x_resume_token: str = Header()):
    session = require_session(public_id, x_resume_token)
    answers = current_answers(session["id"])
    with connection() as conn:
        conn.execute(
            "INSERT INTO guide_events (session_id, event_type) VALUES (%s, 'session_resumed')",
            (session["id"],),
        )
        conn.commit()
    return {
        "public_id": str(session["public_id"]),
        "status": session["status"],
        "answers": answers,
        "results": score_boats(answers),
        "updated_at": session["updated_at"],
    }


@app.post("/api/sessions/{public_id}/decisions")
def save_decision(public_id: UUID, decision: DecisionIn, x_resume_token: str = Header()):
    with connection() as conn:
        session = conn.execute(
            "SELECT * FROM guide_sessions WHERE public_id = %s AND resume_token_hash = %s FOR UPDATE",
            (public_id, token_hash(x_resume_token)),
        ).fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="Guide session not found")
        conn.execute(
            "UPDATE guide_decisions SET is_current = false WHERE session_id = %s AND question_id = %s AND is_current = true",
            (session["id"], decision.question_id),
        )
        sequence = conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence FROM guide_decisions WHERE session_id = %s",
            (session["id"],),
        ).fetchone()["next_sequence"]
        conn.execute(
            """
            INSERT INTO guide_decisions (session_id, sequence, question_id, answer_value, answer_label)
            VALUES (%s, %s, %s, %s::jsonb, %s)
            """,
            (session["id"], sequence, decision.question_id, json.dumps(decision.answer_value), decision.answer_label),
        )
        conn.execute("UPDATE guide_sessions SET updated_at = now() WHERE id = %s", (session["id"],))
        conn.execute(
            "INSERT INTO guide_events (session_id, event_type, event_data) VALUES (%s, 'decision_saved', %s::jsonb)",
            (session["id"], json.dumps({"question_id": decision.question_id, "sequence": sequence})),
        )
        conn.commit()
    answers = current_answers(session["id"])
    return {"ok": True, "answers": answers, "results": score_boats(answers)}


@app.post("/api/sessions/{public_id}/complete")
def complete_session(public_id: UUID, details: CompleteIn, x_resume_token: str = Header()):
    session = require_session(public_id, x_resume_token)
    answers = current_answers(session["id"])
    results = score_boats(answers)
    resume_url = f"{settings.public_guide_url}?session={session['public_id']}#token={x_resume_token}"
    lines = [
        f"G'day {details.first_name},",
        "",
        "Here is the decision trail from your Dan's Boat Life Adventure Boat Guide.",
        "",
        "Your answers:",
        *[f"- {key.replace('_', ' ').title()}: {value['label']}" for key, value in answers.items()],
        "",
        "Your current shortlist:",
        *[f"{index}. {boat['full_name']} - {', '.join(boat['match_reasons'])}" for index, boat in enumerate(results, 1)],
        "",
        f"Resume or review your guide: {resume_url}",
        "",
        "This is independent decision support, not sales advice. Always inspect and sea trial a boat before committing.",
    ]
    body = "\n".join(lines)
    with connection() as conn:
        conn.execute(
            """
            UPDATE guide_sessions
            SET status = 'completed', first_name = %s, email = %s, phone = %s,
                buyer_country_code = %s, marketing_consent = %s,
                consent_recorded_at = CASE WHEN %s THEN now() ELSE NULL END,
                completed_at = now(), updated_at = now()
            WHERE id = %s
            """,
            (
                details.first_name,
                str(details.email),
                details.phone,
                details.buyer_country_code.upper() if details.buyer_country_code else None,
                details.marketing_consent,
                details.marketing_consent,
                session["id"],
            ),
        )
        conn.execute("DELETE FROM guide_results WHERE session_id = %s", (session["id"],))
        for rank, result in enumerate(results, 1):
            conn.execute(
                """
                INSERT INTO guide_results (session_id, result_rank, total_score, score_breakdown, explanation)
                VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)
                """,
                (session["id"], rank, result["total_score"], json.dumps(result["score_breakdown"]), json.dumps({"full_name": result["full_name"], "reasons": result["match_reasons"]})),
            )
        outbox = conn.execute(
            "INSERT INTO email_outbox (session_id, recipient, subject, text_body) VALUES (%s, %s, %s, %s) RETURNING id",
            (session["id"], str(details.email), "Your Dan's Boat Life adventure boat guide", body),
        ).fetchone()
        conn.execute(
            "INSERT INTO guide_events (session_id, event_type, event_data) VALUES (%s, 'guide_completed', %s::jsonb)",
            (session["id"], json.dumps({"email_status": "queued", "result_count": len(results)})),
        )
        conn.commit()

    email_status = "queued"
    try:
        send_email(str(details.email), "Your Dan's Boat Life adventure boat guide", body)
    except Exception as exc:
        with connection() as conn:
            conn.execute("UPDATE email_outbox SET attempts = 1, last_error = %s WHERE id = %s", (str(exc), outbox["id"]))
            conn.commit()
    else:
        email_status = "sent"
        with connection() as conn:
            conn.execute("UPDATE email_outbox SET status = 'sent', attempts = 1, sent_at = now() WHERE id = %s", (outbox["id"],))
            conn.commit()

    return {"ok": True, "results": results, "resume_url": resume_url, "email_status": email_status}
