from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from biensoxe.api.deps import get_client_ip, get_current_scope
from biensoxe.db import get_db
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.services.bien import (
    add_plate_to_lo,
    delete_plate_in_lo,
    inspect_plate_inline,
    list_plates_in_lo,
    update_plate_in_lo,
)

router = APIRouter(prefix="/api/v1", tags=["bien"])


class KiemTraBienRequest(BaseModel):
    lo_id: int | None = None
    bien_so: str
    nen_bien: str | None = None
    mau_sac: str | None = None
    nen_bien_id: int | None = None
    exclude_bien_id: int | None = None


class CreateOrUpdateBienRequest(BaseModel):
    bien_so: str
    nen_bien: str | None = None
    mau_sac: str | None = None
    nen_bien_id: int | None = None
    ghi_chu: str | None = None
    dat_lai_xac_nhan: bool = False


@router.post("/bien/kiem-tra")
def post_kiem_tra_bien(
    payload: KiemTraBienRequest,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return inspect_plate_inline(
        db,
        scope,
        lo_id=payload.lo_id,
        bien_so=payload.bien_so,
        nen_bien=payload.nen_bien or payload.mau_sac,
        nen_bien_id=payload.nen_bien_id,
        exclude_bien_id=payload.exclude_bien_id,
    )


@router.get("/lo/{lo_id}/bien")
def get_bien_in_lo(
    lo_id: int,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return {"items": list_plates_in_lo(db, scope, lo_id=lo_id)}


@router.post("/lo/{lo_id}/bien", status_code=status.HTTP_201_CREATED)
def post_add_bien_to_lo(
    lo_id: int,
    payload: CreateOrUpdateBienRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return add_plate_to_lo(
        db,
        scope,
        lo_id=lo_id,
        bien_so=payload.bien_so,
        nen_bien=payload.nen_bien or payload.mau_sac,
        nen_bien_id=payload.nen_bien_id,
        ghi_chu=payload.ghi_chu,
        dat_lai_xac_nhan=payload.dat_lai_xac_nhan,
        ip=get_client_ip(request),
    )


@router.put("/bien/{bien_id}")
def put_update_bien(
    bien_id: int,
    payload: CreateOrUpdateBienRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return update_plate_in_lo(
        db,
        scope,
        bien_id=bien_id,
        bien_so=payload.bien_so,
        nen_bien=payload.nen_bien or payload.mau_sac,
        nen_bien_id=payload.nen_bien_id,
        ghi_chu=payload.ghi_chu,
        dat_lai_xac_nhan=payload.dat_lai_xac_nhan,
        ip=get_client_ip(request),
    )


@router.delete("/bien/{bien_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bien_endpoint(
    bien_id: int,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    delete_plate_in_lo(
        db,
        scope,
        bien_id=bien_id,
        ip=get_client_ip(request),
    )
