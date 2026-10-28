#!/usr/bin/env python3
import argparse
from contextlib import closing
import datetime
import json
import os
from pathlib import Path
import sqlite3


def snapshot(data, sid=None):
    report = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'threads': []}
    health = data/'discovery-health.json'
    report['discovery'] = json.loads(health.read_text()) if health.exists() else {'status': 'missing'}
    enabled = {p.stem for p in (data/'registrations').glob('*.thread')}
    disabled = {p.stem for p in (data/'registrations').glob('*.unshared')}
    report['registrations'] = {'enabled': len(enabled-disabled), 'disabled': len(disabled), 'conflicting': len(enabled & disabled)}
    with closing(sqlite3.connect((data/'t3/userdata/state.sqlite').as_uri()+'?mode=ro', uri=True)) as db:
        rows = db.execute('''SELECT t.thread_id,t.archived_at,t.deleted_at,
            t.pending_approval_count,t.pending_user_input_count,r.status,r.last_seen_at,r.resume_cursor_json
            FROM projection_threads t LEFT JOIN provider_session_runtime r USING(thread_id)''').fetchall()
        for tid, archived, deleted, approvals, questions, status, last_seen, cursor in rows:
            native = json.loads(cursor or '{}').get('threadId')
            if sid and sid not in (native, tid): continue
            activities = db.execute('''SELECT kind,created_at,payload_json,turn_id FROM projection_thread_activities
                WHERE thread_id=? AND (kind LIKE 'user-input.%' OR kind LIKE 'approval.%'
                OR kind LIKE 'provider.%respond.failed') ORDER BY created_at,activity_id''', (tid,)).fetchall()
            pending = {}
            events = []
            for kind, at, raw, turn_id in activities:
                payload = json.loads(raw)
                request_id = payload.get('requestId')
                detail = str(payload.get('detail', '')).lower()
                stale = 'stale pending' in detail or 'unknown pending' in detail
                event = dict(kind=kind, at=at, requestId=request_id, turnId=turn_id,
                             responseMode=payload.get('responseMode'), staleCallback=stale)
                events.append(event)
                if kind in ('user-input.requested', 'approval.requested'): pending[request_id] = event
                elif kind in ('user-input.resolved', 'approval.resolved') or stale: pending.pop(request_id, None)
            report['threads'].append(dict(threadId=tid, nativeThreadId=native, archived=archived is not None,
                deleted=deleted is not None, sharingRequested=native in enabled and native not in disabled,
                runtime=status, lastSeenAt=last_seen, pendingApprovals=approvals, pendingQuestions=questions,
                pendingRequests=list(pending.values()), recentRequestEvents=events[-50:]))
    if sid and not report['threads']:
        report['threads'].append(dict(nativeThreadId=sid, runtime='absent',
                                      sharingRequested=sid in enabled and sid not in disabled))
    report['toggleEvents'] = []
    report['malformedToggleEvents'] = 0
    directory = data/'diagnostics'
    for name in ['lifecycle.jsonl.3', 'lifecycle.jsonl.2', 'lifecycle.jsonl.1', 'lifecycle.jsonl']:
        path = directory/name
        if not path.exists(): continue
        for line in path.read_text().splitlines():
            try: entry = json.loads(line)
            except json.JSONDecodeError:
                report['malformedToggleEvents'] += 1
                continue
            if sid is None or entry.get('nativeThreadId') == sid: report['toggleEvents'].append(entry)
    report['toggleEvents'] = report['toggleEvents'][-100:]
    return report


def main():
    parser = argparse.ArgumentParser(description='Read-only T3 lifecycle diagnostics; excludes conversation content and credentials.')
    parser.add_argument('--session')
    args = parser.parse_args()
    data = Path(os.environ.get('T3_BRIDGE_HOME', str(Path.home()/'.local/share/codex-shared-t3/go-data-20d1565'))).resolve()
    print(json.dumps(snapshot(data, args.session), indent=2))


if __name__ == '__main__': main()
