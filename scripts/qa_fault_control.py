"""Control fault injection on the owned isolated Vite/API QA pair, never production."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sqlite3
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'output/verification/luna-completion/supervisor/qa.sqlite3'
URL = 'http://127.0.0.1:5191/__qa/faults'

def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['arm', 'clear', 'receipt'])
    p.add_argument('--activity', choices=[f'HY-{i:02}' for i in range(1, 7)])
    p.add_argument('--attempt', help='Exact disposable QA attempt; avoids selecting a newer abandoned attempt')
    p.add_argument('--route', choices=['actions', 'stimulus', 'assistance', 'complete', 'trials'], default='actions')
    p.add_argument('--method', choices=['GET', 'POST'], default='POST')
    p.add_argument('--action', choices=['reject', 'drop_after_accept', 'delay'], default='reject')
    p.add_argument('--id', default='supervisor-qa')
    p.add_argument('--output')
    args = p.parse_args()
    if args.mode == 'receipt':
        with urlopen(URL, timeout=10) as response: result = json.load(response)
    else:
        faults = []
        if args.mode == 'arm':
            if args.route == 'trials': path = '/api/trials'
            else:
                if not args.activity: p.error('--activity is required for a hybrid route')
                with sqlite3.connect(DB.as_uri() + '?mode=ro', uri=True) as db:
                    if args.attempt:
                        row = db.execute('SELECT attempt_id FROM hybrid_attempts WHERE activity_id=? AND attempt_id=?', (args.activity, args.attempt)).fetchone()
                    else:
                        row = db.execute('SELECT attempt_id FROM hybrid_attempts WHERE activity_id=? ORDER BY started_at DESC LIMIT 1', (args.activity,)).fetchone()
                if not row: p.error('No QA attempt exists for this activity')
                path = f'/api/hybrid/attempts/{row[0]}/{args.route}'
            faults = [{'id': args.id, 'method': args.method, 'path': path, 'action': args.action}]
        request = Request(URL, data=json.dumps({'faults': faults, 'clearHits': True}).encode(), headers={'Content-Type': 'application/json'}, method='POST')
        with urlopen(request, timeout=10) as response: result = json.load(response)
    if args.output:
        output = (ROOT / args.output).resolve()
        if not output.is_relative_to(ROOT / 'output/verification'): p.error('Evidence output must stay in output/verification')
        output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))

if __name__ == '__main__': main()
