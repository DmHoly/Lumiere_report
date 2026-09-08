from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..dataset_store import store

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.get("")
def list_datasets():
    return store.list()


@router.post("")
async def upload_dataset(file: UploadFile = File(...), key: str | None = Form(None)):
    raw = await file.read()
    try:
        k = store.add_upload(file.filename or "dataset", raw, key=key)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"key": k}


@router.get("/{key}/sample")
def sample_dataset(key: str, n: int = 20):
    try:
        return store.sample(key, n=n)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.delete("/{key}")
def delete_dataset(key: str):
    try:
        store.delete(key)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"status": "deleted"}
