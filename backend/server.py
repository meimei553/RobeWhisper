# -*- coding: utf-8 -*-
"""
前后端分离后的网站入口。
页面文件在 web/，业务接口在 /api。旧 Streamlit 页仍保留在 frontend/app.py。
启动：python -m backend.server
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.runtime import RUNTIME
from frontend.reply_text import FRIENDLY_BLOCKED

WEB = ROOT / "web"
app = FastAPI(title="RobeWhisper")


class TextIn(BaseModel):
    text: str = ""


class RefIn(BaseModel):
    ref: str = "default"


class PhysicsIn(BaseModel):
    friction: float = 1.0
    joint_damping: float = 0.5
    joint_range_min: float = -2.8
    joint_range_max: float = 2.8


class StepIn(BaseModel):
    joint_targets: list[float] = []


class RsrIn(BaseModel):
    enabled: bool = False


class PackIn(BaseModel):
    experiment_id: str = ""
    latest: bool = True


def _guard(fn):
    try:
        return fn()
    except Exception:
        return JSONResponse({"ok": False, "message": FRIENDLY_BLOCKED})


@app.on_event("startup")
def _startup() -> None:
    RUNTIME.init()


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/overview")
def overview():
    return _guard(RUNTIME.overview)


@app.post("/api/instruction")
def instruction(body: TextIn):
    return _guard(lambda: RUNTIME.run_text(body.text))


@app.post("/api/chat/clear")
def clear_chat():
    return _guard(RUNTIME.clear_chat)


@app.post("/api/rsr")
def set_rsr(body: RsrIn):
    return _guard(lambda: RUNTIME.set_rsr(body.enabled))


@app.post("/api/models/load")
def load_model(body: RefIn):
    return _guard(lambda: RUNTIME.load_model(body.ref))


@app.post("/api/models/upload")
async def upload_model(file: UploadFile = File(...)):
    data = await file.read()
    return _guard(lambda: RUNTIME.upload_model(file.filename or "upload.xml", data))


@app.post("/api/physics")
def physics(body: PhysicsIn):
    return _guard(lambda: RUNTIME.apply_physics(body.model_dump()))


@app.post("/api/step")
def step(body: StepIn):
    return _guard(lambda: RUNTIME.step(body.joint_targets))


@app.post("/api/reset")
def reset_sim():
    return _guard(RUNTIME.reset_sim)


@app.post("/api/reload")
def reload_model():
    return _guard(RUNTIME.reload_model)


@app.get("/api/records")
def records():
    return _guard(RUNTIME.records)


@app.post("/api/demo-pack")
def demo_pack(body: PackIn):
    return _guard(lambda: RUNTIME.export_pack(body.experiment_id, body.latest))


@app.get("/api/demo-pack/download")
def download_pack(name: str):
    from config import settings
    safe = Path(name).name
    path = Path(settings.EXPERIMENTS_DIR) / "packs" / safe
    if safe != name or path.suffix.lower() != ".zip" or not path.is_file():
        return JSONResponse({"ok": False, "message": "找不到演示包"})
    return FileResponse(path, filename=safe, media_type="application/zip")


@app.post("/api/probe/http")
def probe_http():
    return _guard(RUNTIME.probe_http)


@app.post("/api/probe/llm")
def probe_llm():
    return _guard(RUNTIME.probe_llm)


@app.post("/api/demo/overlimit")
def overlimit():
    return _guard(RUNTIME.run_overlimit_demo)


app.mount("/static", StaticFiles(directory=str(WEB)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)