"""Admin doc upload — merchant menus / service lists for enquiry-generic.

POST stores the original under <tenant_home>/docs/ and re-chunks it
immediately (services/doc_chunk.py); DELETE removes both. Gated by
`require_tenant_access` — admin bearer or the owning merchant's cookie.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from services.doc_chunk import (
    ALLOWED_EXTENSIONS,
    MAX_DOC_BYTES,
    DocExtractionError,
    docs_dir,
    list_docs,
    rechunk_doc,
    remove_chunks,
)
from surface.auth_deps import require_tenant_access

router = APIRouter(
    prefix="/v1/admin", dependencies=[Depends(require_tenant_access)], tags=["docs"],
)


def _safe_name(raw: str) -> str:
    """Strip any path components; reject empty/hidden names."""
    name = Path(raw or "").name
    if not name or name.startswith("."):
        raise HTTPException(422, "upload needs a plain filename like menu.pdf")
    return name


@router.post("/tenants/{tid}/docs", status_code=status.HTTP_201_CREATED)
async def upload_doc(tid: str, file: UploadFile) -> dict[str, Any]:
    name = _safe_name(file.filename or "")
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"unsupported extension {ext!r} — upload .pdf or .txt",
        )
    data = await file.read(MAX_DOC_BYTES + 1)
    if len(data) > MAX_DOC_BYTES:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"doc exceeds the {MAX_DOC_BYTES // (1024 * 1024)}MB limit",
        )

    dest = docs_dir(tid) / name
    dest.write_bytes(data)
    try:
        chunks = rechunk_doc(tid, name)
    except DocExtractionError as e:
        dest.unlink(missing_ok=True)
        remove_chunks(tid, name)
        raise HTTPException(422, str(e)) from e

    st = dest.stat()
    return {"name": name, "size": st.st_size, "uploaded_at": st.st_mtime, "chunks": chunks}


@router.get("/tenants/{tid}/docs")
def get_docs(tid: str) -> dict[str, list[dict[str, Any]]]:
    return {"docs": list_docs(tid)}


@router.delete("/tenants/{tid}/docs/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_doc(tid: str, name: str) -> None:
    safe = _safe_name(name)
    target = docs_dir(tid) / safe
    if not target.is_file():
        raise HTTPException(404, f"doc {safe!r} not found")
    target.unlink()
    remove_chunks(tid, safe)
