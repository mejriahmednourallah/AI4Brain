"""Local lifecycle HTTP surface; deleting data is an explicit user action."""
from __future__ import annotations
from contextlib import closing
from typing import Any, Literal
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from .graph_service import GraphMirror
from .lifecycle_service import export_learner_data, delete_learner_data, RETENTION_NOTICE, UNCERTAINTY_NOTICE, REMOTE_NOTICE
from .storage import utc_now

class DeleteRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    confirmation: Literal['DELETE LOCAL DATA']


def create_lifecycle_router(store: Any) -> APIRouter:
    router=APIRouter()
    with closing(store.connect()) as db:
        db.execute('CREATE TABLE IF NOT EXISTS privacy_reconciliation (learner_id TEXT PRIMARY KEY, status TEXT NOT NULL, updated_at TEXT NOT NULL)')

    def mark(status):
        with closing(store.connect()) as db:
            db.execute('INSERT INTO privacy_reconciliation VALUES (?,?,?) ON CONFLICT(learner_id) DO UPDATE SET status=excluded.status,updated_at=excluded.updated_at',('demo-user',status,utc_now()))

    @router.get('/api/data/demo-user/notice')
    def notice():
        with closing(store.connect()) as db:
            row=db.execute('SELECT status,updated_at FROM privacy_reconciliation WHERE learner_id=?',('demo-user',)).fetchone()
        return {'retention':RETENTION_NOTICE,'uncertainty':UNCERTAINTY_NOTICE,'remote_processing':REMOTE_NOTICE,
                'mirror_reconciliation':dict(row) if row else None,'storage':'Local SQLite canonical records and optional derived Neo4j mirror. Exported downloads must be managed separately.'}

    @router.get('/api/data/demo-user/export')
    def export():
        return JSONResponse(export_learner_data(store),headers={'Content-Disposition':'attachment; filename="ai4brain-local-export.json"','Cache-Control':'no-store'})

    @router.post('/api/data/demo-user/delete')
    def delete(body:DeleteRequest):
        result=delete_learner_data(store)
        mark('pending')
        mirror=GraphMirror().erase_learner('demo-user')
        if mirror.get('erasure_verified'):mark('verified')
        return {**result,'mirror':mirror,'complete':bool(mirror.get('erasure_verified')),
                'message':'Canonical local records deleted. Exported copies are outside this operation.' if mirror.get('erasure_verified') else 'Canonical local records deleted. Neo4j erasure is pending; enable the mirror and retry reconciliation.'}

    @router.post('/api/data/demo-user/reconcile')
    def reconcile():
        with closing(store.connect()) as db:
            row=db.execute('SELECT status FROM privacy_reconciliation WHERE learner_id=?',('demo-user',)).fetchone()
        if not row or row['status']!='pending':return {'status':'no_pending_erasure'}
        result=GraphMirror().erase_learner('demo-user')
        if result.get('erasure_verified'):mark('verified')
        return result
    return router
