"""Read-only recovery case and quarantine APIs."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.quarantine_repository import QuarantineRepository
from app.repositories.recovery_case_repository import RecoveryCaseRepository
from app.schemas.recovery import QuarantineRecordResponse, RecoveryCaseResponse

router = APIRouter(tags=["Recovery"])


@router.get("/recovery-cases", response_model=list[RecoveryCaseResponse])
def list_recovery_cases(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return RecoveryCaseRepository(db).list(limit=limit)


@router.get(
    "/recovery-cases/{case_id}",
    response_model=RecoveryCaseResponse,
)
def get_recovery_case(case_id: str, db: Session = Depends(get_db)):
    recovery_case = RecoveryCaseRepository(db).get_by_case_id(case_id)
    if recovery_case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recovery case not found",
        )
    return recovery_case


@router.get("/quarantines", response_model=list[QuarantineRecordResponse])
def list_quarantines(
    active: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return QuarantineRepository(db).list(active=active, limit=limit)


@router.get(
    "/quarantines/{quarantine_id}",
    response_model=QuarantineRecordResponse,
)
def get_quarantine(quarantine_id: str, db: Session = Depends(get_db)):
    quarantine = QuarantineRepository(db).get_by_quarantine_id(quarantine_id)
    if quarantine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quarantine record not found",
        )
    return quarantine
