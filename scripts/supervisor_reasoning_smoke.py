"""Independent supervisor fixture checks, separate from builder smoke checks."""
from __future__ import annotations
import os
import sqlite3
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
with tempfile.TemporaryDirectory(prefix='ai4brain-supervisor-') as temp:
    os.environ['AI4BRAIN_DB'] = str(Path(temp) / 'audit.sqlite3')
    from fastapi.testclient import TestClient
    from backend.app.main import app, store
    with TestClient(app) as client:
        sid = client.post('/api/sessions', json={'consent_accepted': True}).json()['id']
        public = client.get('/api/exercises/EX-02?phase=baseline').json()
        assert len(public['items']) == 6
        assert all('answer' not in item and 'rule_type' not in item for item in public['items'])
        ids=[]
        # Independently reviewed fixed bank: A is correct on items 2 and 5 only.
        for item in public['items']:
            body={'session_id':sid,'event_id':str(uuid.uuid4()),'phase':'baseline','item_id':item['item_id'],'choice':'A','response_time_ms':1500}
            result=client.post('/api/trials',json=body)
            assert result.status_code==200,result.text
            ids.append(body['event_id'])
        profile=client.get('/api/profile/demo-user').json()['dimensions']['reasoning']
        assert profile['correct']==2 and profile['index_0_100']==33.33,profile
        assert set(profile['evidence_ids'])==set(ids)
        assert client.post('/api/trials',json={**body,'event_id':str(uuid.uuid4()),'choice':'B'}).status_code==409
        # SQLite itself prevents an ordinary writer from altering raw evidence.
        with store.connect() as db:
            try:
                db.execute("UPDATE events SET type='forged' WHERE event_id=?",(ids[0],))
            except sqlite3.IntegrityError:
                pass
            else:
                raise AssertionError('SQLite allowed event mutation')
        # A different assessment session cannot inherit five prior item slots.
        next_sid=client.post('/api/sessions',json={'consent_accepted':True}).json()['id']
        result=client.post('/api/trials',json={**body,'event_id':str(uuid.uuid4()),'session_id':next_sid})
        assert result.status_code==200,result.text
        newer=client.get('/api/profile/demo-user').json()['dimensions']['reasoning']
        assert newer['evidence_count']==1 and newer['index_0_100'] is None,newer
    # Explicitly close the connection context above on Windows.
    db.close()
print('PASS supervisor: manual 2/6 = 33.33 fixture, evidence IDs, immutable raw events, duplicate replacement rejection, coherent session isolation')
