"""Disposable-database contract check for the independent Crystal form."""
from __future__ import annotations
import tempfile
from contextlib import closing
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app.storage import Store
from backend.app.crystal_reasoning import _config, register_crystal_routes

def main() -> None:
    for n in range(250):
        form=_config(f"seed-{n}")
        assert len(form["choices"]) == 4
        assert len({item["value"] for item in form["choices"]}) == 4
        assert len(form["grid"]) == 3 and form["grid"][2][2] is None
        assert form['grid'][1] == form['grid'][0][1:] + form['grid'][0][:1]
        assert form['grid'][2][:2] == [form['grid'][0][2], form['grid'][0][0]]
        assert {item['value'] for item in form['choices']} == {1, 2, 3, 4}
        assert "correct" not in form and "answer" not in form
    with tempfile.TemporaryDirectory(prefix="luna-crystal-") as temp:
        store=Store(Path(temp)/"qa.sqlite3")
        with closing(store.connect()) as db:
            db.execute("INSERT INTO sessions(id,learner_id,started_at,status) VALUES('s1','demo-user','2026-10-21T00:00:00Z','active')")
        app=FastAPI();register_crystal_routes(app,store)
        with TestClient(app) as client:
            first=client.post('/api/crystal/attempts',json={"event_id":"start-1","session_id":"s1","learner_id":"demo-user","seed":"fixed"})
            assert first.status_code==201,first.text
            started=first.json(); assert "correct" not in str(started["config"])
            exact=client.post('/api/crystal/attempts',json={"event_id":"start-1","session_id":"s1","learner_id":"demo-user","seed":"fixed"})
            assert exact.status_code==201 and exact.json()["attempt_id"]==started["attempt_id"]
            conflict=client.post('/api/crystal/attempts',json={"event_id":"start-1","session_id":"s1","learner_id":"demo-user","seed":"different"})
            assert conflict.status_code==409
            cfg=started["config"]; grid=cfg["grid"]; expected=grid[0][1]
            right=next(item["choice_id"] for item in cfg["choices"] if item["value"]==expected)
            response=client.post(f"/api/crystal/attempts/{started['attempt_id']}/answer",json={"event_id":"answer-1","choice_id":right})
            assert response.status_code==200 and response.json()["outcome"]["correct"] is True,response.text
            retry=client.post(f"/api/crystal/attempts/{started['attempt_id']}/answer",json={"event_id":"answer-1","choice_id":right})
            assert retry.status_code==200 and retry.json()["outcome"]==response.json()["outcome"]
            timing_conflict=client.post(f"/api/crystal/attempts/{started['attempt_id']}/answer",json={"event_id":"answer-1","choice_id":right,"response_time_ms":7})
            assert timing_conflict.status_code==409
            wrong=next(item["choice_id"] for item in cfg["choices"] if item["choice_id"]!=right)
            conflict=client.post(f"/api/crystal/attempts/{started['attempt_id']}/answer",json={"event_id":"answer-1","choice_id":wrong})
            assert conflict.status_code==409
            fetched=client.get(f"/api/crystal/attempts/{started['attempt_id']}")
            assert fetched.status_code==200 and fetched.json()["outcome"]==response.json()["outcome"]
            with closing(store.connect()) as db:
                assert db.execute("SELECT COUNT(*) FROM crystal_events").fetchone()[0]==2
                assert db.execute("SELECT COUNT(*) FROM crystal_outcomes").fetchone()[0]==1
                try: db.execute("UPDATE crystal_outcomes SET correct=0")
                except Exception: pass
                else: raise AssertionError("outcome immutability trigger did not fire")
    print("Luna crystal smoke passed: 250 unique four-choice forms, no answer-key leak, exact start/answer replay, conflicts, evidence/outcome persistence.")

if __name__=="__main__":main()
