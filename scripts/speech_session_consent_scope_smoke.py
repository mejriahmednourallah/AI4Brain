"""Session-scoped consent lookup regression across multiple learner sessions."""
from __future__ import annotations

import sys
import tempfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import HTTPException
from backend.app.coach_routes import CoachRequest, _training_context
from backend.app.speech_service import _session_and_consent
from backend.app.storage import Store, utc_now


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ai4brain-consent-scope-") as temp:
        store = Store(Path(temp) / "consent-scope.sqlite3")
        unrelated = store.create_session("unrelated-session", "demo-user")
        current = store.create_session("current-session", "demo-user")
        # Add a later unrelated consent event to another session; the current-session
        # lookup must still resolve exactly its own immutable consent record.
        unrelated_id = "unrelated-consent-later"
        store.add_event(unrelated_id, unrelated["id"], "consent_recorded", {
            "event_id": unrelated_id, "session_id": unrelated["id"], "learner_id": "demo-user",
            "event_type": "consent_recorded", "consent": {"accepted": True},
            "sample_data": False, "recorded_at": utc_now(),
        })
        body = CoachRequest(session_id=current["id"], message="Summarize the current evidence.")
        context = _training_context(store, body, None)
        assert context["consent_event_id"] == f"consent-{current['id']}"
        session, consent = _session_and_consent(store, current["id"])
        assert session["id"] == current["id"] and consent["event_id"] == f"consent-{current['id']}"

        # A session without its own consent remains unconsented even though the
        # learner has accepted consent events in two other sessions.
        with closing(store.connect()) as db:
            db.execute("INSERT INTO sessions(id,learner_id,started_at,status,dashboard_mode) VALUES(?,?,?,'active','analytics')",
                       ("no-consent-session", "demo-user", utc_now()))
        no_consent = False
        try:
            _session_and_consent(store, "no-consent-session")
        except HTTPException as error:
            no_consent = error.status_code == 409
        assert no_consent, "consent from another session must not authorize voice"
        assert store.events(session_id=current["id"])[0]["event_id"] == f"consent-{current['id']}"
        print("PASS session consent scope: current consent selected; unrelated session consent ignored; unconsented session remains blocked")


if __name__ == "__main__":
    main()
