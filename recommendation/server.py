from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from recommendation.api import recommend_from_dataset_json, recommend_rooms_payload

_scripts_dir = str(Path(__file__).resolve().parent.parent / "data_processing" / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from nlp_2_json_spacy import RoomParser


class PayloadRequest(BaseModel):
    user_query: str = ""
    requirements: dict[str, Any] = Field(default_factory=dict)
    rooms: list[dict[str, Any]] = Field(default_factory=list)
    reservations: list[dict[str, Any]] = Field(default_factory=list)


class DatasetRequest(BaseModel):
    user_query: str
    requirements: dict[str, Any] = Field(default_factory=dict)
    dataset_path: str | None = None


app = FastAPI(title="NaviRoom API", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_dataset(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"dataset file not found: {path}")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/recommend/upload")
async def recommend_upload(
    user_query: str = Form(default=""),
    requirements: str = Form(default="{}"),
    room_text: str = Form(default=""),
    file: UploadFile = File(default=None),
) -> list[dict[str, Any]]:
    """
    公开接口：通过 CSV 文件或文字描述提供房间数据，返回推荐结果。
    - user_query  : 用户的需求描述，例如 "need a quiet room for 4 people with projector"
    - room_text   : 用文字描述的房间信息，由 NLP 解析为结构化数据（与 CSV 二选一）
    - file        : 房间数据 CSV 文件（与 room_text 二选一）
    - requirements: JSON 字符串，结构化需求（可选），例如 {"capacity": 4, "has_screen": true}
    优先级：CSV 文件 > room_text > 系统默认数据集
    """
    try:
        req_dict: dict[str, Any] = json.loads(requirements) if requirements.strip() else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="requirements 字段必须是合法的 JSON 字符串")

    rooms: list[dict[str, Any]] = []
    source: str = ""

    # 优先使用上传的 CSV 文件
    if file is not None and file.filename:
        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="仅支持 CSV 格式文件")

        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="文件过大（最大 10 MB）")

        parser = RoomParser()
        try:
            rooms = parser.parse(content.decode("utf-8-sig"))
            source = "csv"
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"CSV 解析失败：{exc}") from exc

    # 其次使用文字描述（NLP 解析）
    if not rooms and room_text.strip():
        parser = RoomParser()
        try:
            rooms = parser.parse(room_text.strip())
            source = "text"
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"文字描述解析失败：{exc}") from exc

    # 最后回退到系统默认数据集
    if not rooms:
        dataset_path = os.getenv(
            "RECO_DATASET_PATH", "data_processing/output/dku_dataset.json"
        )
        try:
            dataset = _load_dataset(dataset_path)
            rooms = dataset.get("rooms", [])
            source = "dataset"
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"无法加载系统数据集，请上传 CSV 文件或输入房间描述：{exc}",
            ) from exc

    if not rooms:
        raise HTTPException(
            status_code=404,
            detail="没有可用的房间数据，请上传 CSV 文件或在文本框中描述房间信息",
        )

    payload = {
        "user_query": user_query,
        "requirements": req_dict,
        "rooms": rooms,
        "reservations": [],
    }
    results = recommend_rooms_payload(payload)
    # 在每个结果里附带数据来源，方便前端展示
    for r in results:
        r["_source"] = source
    return results


@app.post("/recommend/payload")
def recommend_with_payload(req: PayloadRequest) -> list[dict[str, Any]]:
    payload = req.model_dump()
    return recommend_rooms_payload(payload)


@app.post("/recommend/dataset")
def recommend_with_dataset(req: DatasetRequest) -> list[dict[str, Any]]:
    dataset_path = req.dataset_path or os.getenv(
        "RECO_DATASET_PATH", "data_processing/output/dku_dataset.json"
    )
    try:
        dataset = _load_dataset(dataset_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return recommend_from_dataset_json(
        user_query=req.user_query,
        requirements=req.requirements,
        dataset=dataset,
    )