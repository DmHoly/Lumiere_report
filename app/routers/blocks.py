from __future__ import annotations

from fastapi import APIRouter

from ..block_registry import registry_as_dict

router = APIRouter(prefix="/api/blocks", tags=["blocks"])


@router.get("")
def list_blocks():
    return registry_as_dict()
