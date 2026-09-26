"""Slice-8 tests — doc upload/chunking, keyword retrieval, enquiry-generic
install, and the question-intent routing e2e (stub activities, no Gemini)."""
from __future__ import annotations

import asyncio
import io
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ADMIN_TOKEN = "test-admin-token"
AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
TID = "t1"
TASK_QUEUE = "plnt-cloud-test"

MENU_TEXT = (
    "Joe's Pizza menu. Margherita, pepperoni, and quattro formaggi. "
    "Gluten free crust available on request for any pizza. "
    "Vegan cheese on selected pies."
)


def _clear_caches() -> None:
    from memory import memori_adapter as ma
    from microagents import loader
    from services import orders_store as os_
    from tenancy import factory as tf
    from workflows import bookings_store as bs

    for mod in (ma, tf, bs, os_, loader):
        mod.clear_cache()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Isolated PLNT_CLOUD_HOME + admin v2 and docs routers."""
    monkeypatch.setenv("PLNT_CLOUD_HOME", str(tmp_path))
    monkeypatch.setenv("PLNT_CLOUD_MEMORY_BACKEND", "stub")
    monkeypatch.setenv("PLNT_CLOUD_ADMIN_TOKEN", ADMIN_TOKEN)
    _clear_caches()

    from surface.admin_v2 import router as admin_v2_router
    from surface.docs_upload import router as docs_router
    app = FastAPI()
    app.include_router(admin_v2_router)
    app.include_router(docs_router)
    yield TestClient(app), tmp_path

    _clear_caches()


def _minimal_pdf(text: str) -> bytes:
    """Smallest well-formed single-page PDF with a text content stream."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
         b"/Resources << /Font << /F1 5 0 R >> >> >>"),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF".encode()
    )
    return out.getvalue()


# ─────────────────────────────────────────────────────────── upload + chunks


def test_upload_txt_chunks_then_delete_removes(client):
    c, tmp_path = client
    r = c.post(
        f"/v1/admin/tenants/{TID}/docs", headers=AUTH,
        files={"file": ("menu.txt", MENU_TEXT.encode(), "text/plain")},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "menu.txt"
    assert body["chunks"] == 1
    assert body["size"] == len(MENU_TEXT.encode())

    docs_root = tmp_path / "tenants" / TID / "docs"
    assert (docs_root / "menu.txt").is_file()
    assert (docs_root / "chunks" / "menu.txt" / "0.txt").is_file()

    r = c.get(f"/v1/admin/tenants/{TID}/docs", headers=AUTH)
    docs = r.json()["docs"]
    assert len(docs) == 1
    assert docs[0]["name"] == "menu.txt" and docs[0]["chunks"] == 1

    r = c.delete(f"/v1/admin/tenants/{TID}/docs/menu.txt", headers=AUTH)
    assert r.status_code == 204
    assert not (docs_root / "menu.txt").exists()
    assert not (docs_root / "chunks" / "menu.txt").exists()

    r = c.delete(f"/v1/admin/tenants/{TID}/docs/menu.txt", headers=AUTH)
    assert r.status_code == 404


def test_upload_pdf_extracts_and_chunks(client):
    c, tmp_path = client
    pdf = _minimal_pdf("Gluten free pizza crust available on request")
    r = c.post(
        f"/v1/admin/tenants/{TID}/docs", headers=AUTH,
        files={"file": ("menu.pdf", pdf, "application/pdf")},
    )
    assert r.status_code == 201
    assert r.json()["chunks"] == 1
    chunk = (tmp_path / "tenants" / TID / "docs" / "chunks" / "menu.pdf" / "0.txt").read_text()
    assert "Gluten" in chunk


def test_upload_rejects_wrong_extension(client):
    c, _ = client
    r = c.post(
        f"/v1/admin/tenants/{TID}/docs", headers=AUTH,
        files={"file": ("menu.docx", b"whatever", "application/octet-stream")},
    )
    assert r.status_code == 415


def test_upload_rejects_oversize(client):
    c, tmp_path = client
    big = b"x" * (5 * 1024 * 1024 + 1)
    r = c.post(
        f"/v1/admin/tenants/{TID}/docs", headers=AUTH,
        files={"file": ("big.txt", big, "text/plain")},
    )
    assert r.status_code == 413
    assert not (tmp_path / "tenants" / TID / "docs" / "big.txt").exists()


def test_upload_unparseable_pdf_422(client):
    c, tmp_path = client
    r = c.post(
        f"/v1/admin/tenants/{TID}/docs", headers=AUTH,
        files={"file": ("broken.pdf", b"not a pdf at all", "application/pdf")},
    )
    assert r.status_code == 422
    # Failed uploads leave nothing behind.
    assert not (tmp_path / "tenants" / TID / "docs" / "broken.pdf").exists()


# ─────────────────────────────────────────────────────────── chunker + scoring


def test_chunk_text_windows_and_overlap():
    from services.doc_chunk import chunk_text

    words = [f"w{i}" for i in range(1000)]
    chunks = chunk_text(" ".join(words))
    # 384-word windows, 346-word step → starts at 0, 346, 692.
    assert len(chunks) == 3
    c0, c1 = chunks[0].split(), chunks[1].split()
    assert c0[-38:] == c1[:38]  # ~50-token overlap carried forward
    assert chunk_text("") == []
    assert chunk_text("short doc") == ["short doc"]


def test_top_chunks_returns_keyword_matching_chunk(client):
    _, _ = client
    from services import doc_chunk as dc

    (dc.docs_dir(TID) / "menu.txt").write_text(MENU_TEXT, encoding="utf-8")
    (dc.docs_dir(TID) / "parking.txt").write_text(
        "Street parking behind the building after 6pm.", encoding="utf-8",
    )
    dc.rechunk_doc(TID, "menu.txt")
    dc.rechunk_doc(TID, "parking.txt")

    top = dc.top_chunks(TID, "do you have gluten free pizza?")
    assert top
    assert top[0]["doc"] == "menu.txt"
    assert "Gluten free crust" in top[0]["text"]

    top = dc.top_chunks(TID, "where can I park my car? parking")
    assert top and top[0]["doc"] == "parking.txt"

    assert dc.top_chunks(TID, "") == []
    assert dc.top_chunks("tenant-with-no-docs", "gluten free?") == []


# ─────────────────────────────────────────────────────────── marketplace install


def test_install_enquiry_generic_succeeds(client):
    c, tmp_path = client
    r = c.post(f"/v1/admin/tenants/{TID}/agents/enquiry-generic", headers=AUTH)
    assert r.status_code == 201, r.text
    row = r.json()
    assert row["slug"] == "enquiry-generic"
    assert row["version"] == "0.1.0"
    assert row["enabled"] is True

    bundle = tmp_path / "tenants" / TID / "agents" / "enquiry-generic@0.1.0"
    assert (bundle / "skill.toml").exists()
    assert (bundle / "prompt.md").exists()


# ─────────────────────────────────────────────────────────── e2e (stub mode)


async def test_question_intent_routes_to_enquiry(tmp_path, monkeypatch):
    """Question-kind message → enquiry-generic answers grounded in the
    tenant's uploaded doc; the say reply carries the doc content."""
    from temporalio.client import Client
    from temporalio.testing import WorkflowEnvironment
    from temporalio.worker import Worker

    from workflows.session import ConversationWorkflow, SessionInput
    from workflows.stub_activities import stub_run_microagent

    monkeypatch.setenv("PLNT_CLOUD_HOME", str(tmp_path))
    monkeypatch.setenv("PLNT_CLOUD_MEMORY_BACKEND", "stub")
    _clear_caches()

    tid = "enq-demo"
    from services.doc_chunk import docs_dir, rechunk_doc
    (docs_dir(tid) / "menu.txt").write_text(MENU_TEXT, encoding="utf-8")
    assert rechunk_doc(tid, "menu.txt") == 1

    async with await WorkflowEnvironment.start_local() as env:
        client: Client = env.client
        async with Worker(
            client,
            task_queue=TASK_QUEUE,
            workflows=[ConversationWorkflow],
            activities=[stub_run_microagent],
        ):
            handle = await client.start_workflow(
                ConversationWorkflow.run,
                SessionInput(tenant_id=tid, user_id="alice",
                             session_id=f"sess-{uuid.uuid4().hex[:6]}",
                             force_backend="offline"),
                id=f"test-{uuid.uuid4().hex[:8]}",
                task_queue=TASK_QUEUE,
            )
            await handle.signal("user_message", "do you have gluten free pizza?")

            replies: list[dict[str, Any]] = []
            for _ in range(100):
                replies = await handle.query("replies_since", 0)
                if any(r["role"] == "say" for r in replies):
                    break
                await asyncio.sleep(0.1)
            await handle.signal("close")

    cls = next(r for r in replies if r["role"] == "classify_intent")
    assert cls["content"]["kind"] == "question"

    enq = next(r for r in replies if r["role"] == "enquiry-generic")
    assert enq["content"]["grounded"] is True
    assert enq["content"]["source"] == "docs"

    say = next(r for r in replies if r["role"] == "say")
    assert "gluten free" in say["content"]["say"].lower()
    # No booking chain for a question turn.
    roles = [r["role"] for r in replies]
    assert "resolve_business" not in roles and "check_availability" not in roles

    _clear_caches()
