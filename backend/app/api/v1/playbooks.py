"""
Playbook endpoints.

POST   /api/v1/playbooks/                          -> create a playbook (admin)
GET    /api/v1/playbooks/                           -> list playbooks (viewer+)
GET    /api/v1/playbooks/{playbook_id}               -> fetch one playbook (viewer+)
PATCH  /api/v1/playbooks/{playbook_id}               -> update a playbook (admin)
POST   /api/v1/playbooks/{playbook_id}/run/{alert_id} -> manually run a playbook on an alert (admin/soc_analyst)
GET    /api/v1/playbooks/executions/                 -> list execution history (viewer+)
GET    /api/v1/playbooks/executions/{execution_id}   -> fetch one execution record (viewer+)

Automatic evaluation isn't triggered from here — see the hooks in
app/api/v1/alerts.py (_ingest_one and update_alert_status), which call
run_playbooks_for_alert after every alert create/update.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user, require_role
from app.db.session import get_db
from app.models.alert import Alert
from app.models.playbook import Playbook
from app.models.playbook_execution import PlaybookExecution
from app.models.user import User
from app.schemas.playbook import (
    PlaybookCreate,
    PlaybookExecutionListResponse,
    PlaybookExecutionResponse,
    PlaybookListResponse,
    PlaybookResponse,
    PlaybookUpdate,
)
from app.services.playbook_engine import run_single_playbook
from app.services.playbook_engine.actions import known_action_names
from app.services.playbook_engine.rules import ALLOWED_FIELDS

router = APIRouter(prefix="/api/v1/playbooks", tags=["playbooks"])


def _validate_steps(steps: list[dict]) -> None:
    known = set(known_action_names())
    for step in steps:
        if step.get("action") not in known:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown action '{step.get('action')}'. Valid actions: {sorted(known)}",
            )


def _validate_conditions(conditions: Optional[list[dict]]) -> None:
    if not conditions:
        return
    allowed = set(ALLOWED_FIELDS.keys())
    for condition in conditions:
        if condition.get("field") not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown condition field '{condition.get('field')}'. Valid fields: {sorted(allowed)}",
            )


@router.post("/", response_model=PlaybookResponse, status_code=status.HTTP_201_CREATED)
def create_playbook(
    payload: PlaybookCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    _validate_steps(payload.steps)
    _validate_conditions(payload.trigger_conditions)

    playbook = Playbook(**payload.model_dump())
    db.add(playbook)
    db.commit()
    db.refresh(playbook)
    return playbook


@router.get("/", response_model=PlaybookListResponse)
def list_playbooks(
    is_active: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Playbook)
    if is_active is not None:
        query = query.filter(Playbook.is_active == is_active)

    total = query.count()
    items = query.order_by(Playbook.name).offset(skip).limit(limit).all()
    return PlaybookListResponse(total=total, items=items)


@router.get("/executions/", response_model=PlaybookExecutionListResponse)
def list_executions(
    alert_id: Optional[str] = Query(default=None),
    playbook_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(PlaybookExecution)
    if alert_id is not None:
        query = query.filter(PlaybookExecution.alert_id == alert_id)
    if playbook_id is not None:
        query = query.filter(PlaybookExecution.playbook_id == playbook_id)

    total = query.count()
    items = query.order_by(PlaybookExecution.created_at.desc()).offset(skip).limit(limit).all()
    return PlaybookExecutionListResponse(total=total, items=items)


@router.get("/executions/{execution_id}", response_model=PlaybookExecutionResponse)
def get_execution(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    execution = db.get(PlaybookExecution, execution_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook execution not found")
    return execution


@router.get("/{playbook_id}", response_model=PlaybookResponse)
def get_playbook(
    playbook_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playbook = db.get(Playbook, playbook_id)
    if playbook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook not found")
    return playbook


@router.patch("/{playbook_id}", response_model=PlaybookResponse)
def update_playbook(
    playbook_id: str,
    payload: PlaybookUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    playbook = db.get(Playbook, playbook_id)
    if playbook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook not found")

    updates = payload.model_dump(exclude_unset=True)
    if "steps" in updates and updates["steps"] is not None:
        _validate_steps(updates["steps"])
    if "trigger_conditions" in updates:
        _validate_conditions(updates["trigger_conditions"])

    for field, value in updates.items():
        setattr(playbook, field, value)

    db.add(playbook)
    db.commit()
    db.refresh(playbook)
    return playbook


@router.post(
    "/{playbook_id}/run/{alert_id}",
    response_model=PlaybookExecutionResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_playbook_manually(
    playbook_id: str,
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "soc_analyst")),
):
    """Run a playbook against a specific alert regardless of its
    trigger_type or whether trigger_conditions would currently match — an
    explicit manual invocation always executes. Conditions are still
    snapshotted onto the execution record for the audit trail."""
    playbook = db.get(Playbook, playbook_id)
    if playbook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook not found")

    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    execution = run_single_playbook(
        db, playbook, alert, trigger_source="manual", executed_by=current_user.id
    )
    db.commit()
    db.refresh(execution)
    return execution
