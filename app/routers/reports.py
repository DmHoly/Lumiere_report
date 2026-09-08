from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import HTMLResponse, Response

from .. import config_store
from ..report_compiler import BlockBuildError, ConfigError, render_html

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
def list_reports():
    return config_store.list_configs()


@router.get("/{report_id}")
def get_report(report_id: str):
    try:
        return config_store.load_config(report_id)
    except KeyError as exc:
        raise HTTPException(404, "Rapport introuvable") from exc


@router.post("")
def save_report(payload: dict = Body(...)):
    name = (payload.get("name") or "").strip() or "Rapport sans titre"
    config = payload.get("config")
    report_id = payload.get("id") or None
    if not config:
        raise HTTPException(400, "config manquant")
    new_id = config_store.save_config(config, name=name, report_id=report_id)
    return {"id": new_id}


@router.delete("/{report_id}")
def delete_report(report_id: str):
    try:
        config_store.delete_config(report_id)
    except KeyError as exc:
        raise HTTPException(404, "Rapport introuvable") from exc
    return {"status": "deleted"}


@router.post("/preview")
def preview_report(config: dict = Body(...)):
    try:
        html = render_html(config)
    except ConfigError as exc:
        raise HTTPException(400, str(exc)) from exc
    except BlockBuildError as exc:
        raise HTTPException(422, str(exc)) from exc
    return HTMLResponse(html)


@router.post("/{report_id}/generate")
def generate_report(report_id: str):
    try:
        cfg = config_store.load_config(report_id)
    except KeyError as exc:
        raise HTTPException(404, "Rapport introuvable") from exc
    try:
        html = render_html(cfg)
    except (ConfigError, BlockBuildError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{report_id}.html"'},
    )
