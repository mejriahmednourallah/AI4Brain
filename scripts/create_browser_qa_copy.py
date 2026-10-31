"""Create an isolated QA database from ONLY the known supervisor browser session."""
from pathlib import Path
import sqlite3,sys,json
sys.path.insert(0,str(Path.cwd()))
from backend.app.storage import Store
session_id='a7fdaeab-a57b-4dcf-93b0-d5aa4bca885f'
target=Path('data/qa/approved-ui.sqlite3')
if target.exists():raise SystemExit('QA database already exists; refusing to overwrite')
store=Store(target)
source=sqlite3.connect('data/ai4brain.sqlite3');source.row_factory=sqlite3.Row
rows={}
rows['sessions']=source.execute('SELECT * FROM sessions WHERE id=?',(session_id,)).fetchall()
if len(rows['sessions'])!=1:raise RuntimeError('Known QA session not found')
rows['events']=source.execute('SELECT * FROM events WHERE session_id=? ORDER BY created_at,event_id',(session_id,)).fetchall()
event_ids={row['event_id'] for row in rows['events']}
rows['profile_snapshots']=[r for r in source.execute('SELECT * FROM profile_snapshots') if set(json.loads(r['evidence_ids_json'])).issubset(event_ids)]
snapshot_ids={r['id'] for r in rows['profile_snapshots']}
rows['recommendations']=[r for r in source.execute('SELECT * FROM recommendations') if r['snapshot_id'] in snapshot_ids]
rows['training_blocks']=source.execute('SELECT * FROM training_blocks WHERE session_id=?',(session_id,)).fetchall()
block_ids={r['block_id'] for r in rows['training_blocks']}
rows['difficulty_decisions']=[r for r in source.execute('SELECT * FROM difficulty_decisions') if r['block_id'] in block_ids]
rows['training_plans']=[r for r in source.execute('SELECT * FROM training_plans') if set(json.loads(r['evidence_ids_json'])).issubset(event_ids)]
rows['event_submissions']=[r for r in source.execute('SELECT * FROM event_submissions') if r['event_id'] in event_ids]
with store.connect() as out:
    out.execute('BEGIN IMMEDIATE')
    for table in ['sessions','events','event_submissions','profile_snapshots','training_blocks','difficulty_decisions','recommendations','training_plans']:
        for row in rows[table]:
            names=list(row.keys());quoted=','.join('"'+k+'"' for k in names)
            out.execute(f'INSERT INTO {table} ({quoted}) VALUES ({",".join("?" for _ in names)})',list(row))
    out.commit()
print(json.dumps({'source':'known automated browser QA session only','session_id':session_id,'target':str(target),'rows':{table:len(items) for table,items in rows.items()}},indent=2))
