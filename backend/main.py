"""
Intelligent Document Processing — FastAPI Backend
Local:  uvicorn main:app --reload --port 8001
Azure:  uvicorn main:app --host 0.0.0.0 --port 8000
"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiofiles

from config import settings
from storage import get_store
from extractor import detect_document_type, extract_document, chat_about_document

app = FastAPI(
    title="IDP Banking",
    version="1.0.0",
    description="Intelligent Document Processing — Azure OpenAI + Document Intelligence",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

store = get_store()


# ── Models ────────────────────────────────────────────────────────────────────

class CorrectionPayload(BaseModel):
    doc_id:              str
    field_name:          str
    corrected_value:     str
    original_value:      str
    original_confidence: float

class ReviewDecision(BaseModel):
    doc_id:   str
    decision: str                         # approved | rejected | escalated
    reviewer: Optional[str] = "reviewer@bank.com"
    notes:    Optional[str] = ""

class ChatPayload(BaseModel):
    doc_id:  str
    message: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status":    "ok",
        "llm":       settings.llm_label,
        "doc_intel": settings.use_doc_intel,
        "cosmos":    settings.use_cosmos,
        "blob":      settings.use_blob,
        "ts":        datetime.utcnow().isoformat(),
    }


@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    doc_id  = str(uuid.uuid4())
    suffix  = Path(file.filename).suffix.lower() or ".txt"
    content = await file.read()

    # Save file locally (or to Blob Storage if configured)
    save_path = UPLOAD_DIR / f"{doc_id}{suffix}"
    async with aiofiles.open(save_path, "wb") as f:
        await f.write(content)

    # Upload to Azure Blob if configured
    file_url = f"/uploads/{doc_id}{suffix}"
    if settings.use_blob:
        try:
            from azure.storage.blob import BlobServiceClient
            blob_client = BlobServiceClient.from_connection_string(
                settings.azure_storage_connection_string
            )
            container = blob_client.get_container_client(
                settings.azure_storage_container
            )
            blob_name = f"{doc_id}{suffix}"
            container.upload_blob(name=blob_name, data=content, overwrite=True)
            file_url = (
                f"[{blob_client.account_name}.blob.core.windows.net](https://{blob_client.account_name}.blob.core.windows.net/)"
                f"{settings.azure_storage_container}/{blob_name}"
            )
        except Exception as e:
            print(f"Blob upload warning: {e}")

    # Detect type and extract
    preview  = content.decode("utf-8", errors="replace")[:500]
    doc_type = detect_document_type(preview, file.filename)
    result = await extract_document(content, suffix, doc_type)

    # Compute overall confidence
    fields = result.get("fields", {})
    scores = [
        v["confidence"] for v in fields.values()
        if isinstance(v, dict) and "confidence" in v
    ]
    overall = round(sum(scores) / len(scores), 3) if scores else 0.0

    document = {
        "id":                 doc_id,
        "filename":           file.filename,
        "doc_type":           doc_type,
        "upload_time":        datetime.utcnow().isoformat(),
        "status":             "auto_accepted" if overall >= 0.85 else "pending_review",
        "overall_confidence": overall,
        "fields":             fields,
        "summary":            result.get("summary", ""),
        "raw_text_snippet":   result.get("raw_text", ""),
        "llm_used":           result.get("llm_used", ""),
        "file_url":           file_url,
        "file_size_bytes":    len(content),
        "corrections":        [],
        "review_decision":    None,
    }
    store.save(document)
    return document


@app.get("/documents")
async def list_documents(
    status:   Optional[str] = None,
    doc_type: Optional[str] = None,
):
    docs = store.list_all()
    if status:
        docs = [d for d in docs if d.get("status") == status]
    if doc_type:
        docs = [d for d in docs if d.get("doc_type") == doc_type]
    return {"documents": docs, "total": len(docs)}


@app.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    doc = store.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@app.post("/documents/correct")
async def submit_correction(payload: CorrectionPayload):
    doc = store.get(payload.doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    doc.setdefault("corrections", []).append({
        "field_name":          payload.field_name,
        "original_value":      payload.original_value,
        "corrected_value":     payload.corrected_value,
        "original_confidence": payload.original_confidence,
        "corrected_at":        datetime.utcnow().isoformat(),
    })
    if payload.field_name in doc["fields"]:
        doc["fields"][payload.field_name].update({
            "value":           payload.corrected_value,
            "confidence":      1.0,
            "status":          "human_verified",
            "human_corrected": True,
        })
    store.save(doc)
    return {"ok": True}


@app.post("/documents/review")
async def submit_review(payload: ReviewDecision):
    doc = store.get(payload.doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    doc["review_decision"] = {
        "decision":    payload.decision,
        "reviewer":    payload.reviewer,
        "notes":       payload.notes,
        "reviewed_at": datetime.utcnow().isoformat(),
    }
    doc["status"] = payload.decision
    store.save(doc)
    return {"ok": True, "new_status": payload.decision}


@app.post("/documents/chat")
async def document_chat(payload: ChatPayload):
    doc = store.get(payload.doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    answer = await chat_about_document(
        doc.get("raw_text_snippet", ""),
        doc.get("fields", {}),
        doc.get("doc_type", ""),
        payload.message,
    )
    return {"answer": answer}


@app.get("/dashboard/stats")
async def dashboard_stats():
    docs  = store.list_all()
    total = len(docs)
    if total == 0:
        return {
            "total_documents": 0, "by_status": {}, "by_type": {},
            "confidence_buckets": {"high": 0, "medium": 0, "low": 0},
            "average_confidence": 0, "auto_acceptance_rate": 0,
            "total_corrections": 0, "recent": [],
        }

    by_status     = {}
    by_type       = {}
    conf_buckets  = {"high": 0, "medium": 0, "low": 0}
    corrections   = 0
    conf_sum      = 0.0

    for d in docs:
        s = d.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        t = d.get("doc_type", "unknown")
        by_type[t]   = by_type.get(t, 0) + 1
        c = d.get("overall_confidence", 0.0)
        conf_sum += c
        if c >= 0.85:
            conf_buckets["high"]   += 1
        elif c >= 0.60:
            conf_buckets["medium"] += 1
        else:
            conf_buckets["low"]    += 1
        corrections += len(d.get("corrections", []))

    recent = sorted(docs, key=lambda x: x.get("upload_time", ""), reverse=True)[:5]

    return {
        "total_documents":      total,
        "by_status":            by_status,
        "by_type":              by_type,
        "confidence_buckets":   conf_buckets,
        "average_confidence":   round(conf_sum / total, 3),
        "auto_acceptance_rate": round(
            by_status.get("auto_accepted", 0) / total * 100, 1
        ),
        "total_corrections":    corrections,
        "recent":               recent,
    }
