from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import psycopg


BASE = os.getenv("TEST_API_URL", "http://127.0.0.1:8001")
DATABASE_URL = os.environ["DATABASE_URL"]


def request(path: str, method: str = "GET", body=None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Resume-Token"] = token
    payload = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=payload, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.status, json.loads(response.read())


status, created = request("/api/sessions", "POST")
assert status == 200
session_id = created["public_id"]
token = created["resume_token"]
assert f"?session={session_id}#token={token}" in created["resume_url"]
assert "&token=" not in created["resume_url"]

decisions = {
    "country": ("AU", "Australia"),
    "water": ("offshore", "Offshore"),
    "overnight": ("required", "Yes, it is essential"),
    "people": ("4", "Three or four"),
    "helm": ("enclosed", "Fully enclosed"),
    "storage": ("marina", "Marina berth"),
    "priority": ("exploring", "Exploring"),
    "length": ("30-34", "30-34 feet"),
    "budget": ("unsure", "Not sure yet"),
    "condition": ("either", "Either"),
    "timing": ("3-months", "Within three months"),
}

for question_id, (value, label) in decisions.items():
    response_status, saved = request(
        f"/api/sessions/{session_id}/decisions",
        "POST",
        {"question_id": question_id, "answer_value": value, "answer_label": label},
        token,
    )
    assert response_status == 200 and saved["ok"]

# Editing keeps the old decision as history and makes the revision current.
request(
    f"/api/sessions/{session_id}/decisions",
    "POST",
    {"question_id": "length", "answer_value": "35-39", "answer_label": "35-39 feet"},
    token,
)

try:
    request(f"/api/sessions/{session_id}", token="wrong-token")
except urllib.error.HTTPError as exc:
    assert exc.code == 404
else:
    raise AssertionError("A wrong resume token was accepted")

status, restored = request(f"/api/sessions/{session_id}", token=token)
assert status == 200
assert restored["answers"]["length"]["value"] == "35-39"
assert restored["results"]
assert all(result["make"] and result["model"] and result["length_feet"] for result in restored["results"])

status, completed = request(
    f"/api/sessions/{session_id}/complete",
    "POST",
    {
        "first_name": "Release QA",
        "email": "qa@example.com",
        "phone": None,
        "buyer_country_code": "AU",
        "marketing_consent": False,
    },
    token,
)
assert status == 200 and completed["ok"]
assert completed["email_status"] == "queued"
assert "#token=" in completed["resume_url"]

status, restored_after_completion = request(f"/api/sessions/{session_id}", token=token)
assert restored_after_completion["status"] == "completed"

with psycopg.connect(DATABASE_URL) as conn:
    row = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM guide_decisions d WHERE d.session_id = s.id) AS decision_revisions,
          (SELECT COUNT(*) FROM guide_decisions d WHERE d.session_id = s.id AND d.is_current) AS current_decisions,
          (SELECT COUNT(*) FROM guide_results r WHERE r.session_id = s.id) AS results,
          (SELECT COUNT(*) FROM email_outbox e WHERE e.session_id = s.id AND e.status = 'queued') AS queued_email,
          (SELECT COUNT(*) FROM guide_events ge WHERE ge.session_id = s.id) AS events
        FROM guide_sessions s WHERE s.public_id = %s
        """,
        (session_id,),
    ).fetchone()

assert row == (12, 11, 5, 1, 15)
print(json.dumps({
    "session": session_id,
    "decision_revisions": row[0],
    "current_decisions": row[1],
    "results": row[2],
    "queued_email": row[3],
    "events": row[4],
    "resume_secret_in_fragment": True,
}, indent=2))
