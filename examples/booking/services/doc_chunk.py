"""Per-tenant doc storage: chunking + keyword retrieval for enquiry-generic.

Originals live at <tenant_home>/docs/<name>; chunks as plain .txt at
<tenant_home>/docs/chunks/<name>/<i>.txt. Tokens are approximated as
words * 1.3 — no tokenizer dep, no embeddings (v1 is keyword overlap).
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

ALLOWED_EXTENSIONS = {".pdf", ".txt"}
MAX_DOC_BYTES = 5 * 1024 * 1024

_CHUNK_TOKENS = 500
_OVERLAP_TOKENS = 50
_TOKENS_PER_WORD = 1.3
# ~500-token chunks with ~50-token overlap, expressed in words.
_CHUNK_WORDS = int(_CHUNK_TOKENS / _TOKENS_PER_WORD)      # 384
_OVERLAP_WORDS = int(_OVERLAP_TOKENS / _TOKENS_PER_WORD)  # 38

_WORD_RE = re.compile(r"[a-z0-9]+")


class DocExtractionError(Exception):
    """Raised when a stored doc yields no extractable text."""


def docs_dir(tenant_id: str) -> Path:
    from tenancy.factory import for_tenant
    d = for_tenant(tenant_id).home / "docs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _chunks_root(tenant_id: str) -> Path:
    return docs_dir(tenant_id) / "chunks"


def extract_text(path: Path) -> str:
    """Plain text for a stored .txt or .pdf doc. Raises DocExtractionError
    when nothing extractable comes out."""
    suffix = path.suffix.lower()
    if suffix == ".txt":
        text = path.read_text(encoding="utf-8", errors="replace")
    elif suffix == ".pdf":
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            reader = PdfReader(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except PyPdfError as e:
            raise DocExtractionError(f"could not parse PDF {path.name!r}: {e}") from e
    else:
        raise DocExtractionError(f"unsupported doc type {suffix!r}")
    if not text.strip():
        raise DocExtractionError(f"no extractable text in {path.name!r}")
    return text


def chunk_text(text: str) -> list[str]:
    """Split into ~500-token word windows with ~50-token overlap."""
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    start = 0
    step = _CHUNK_WORDS - _OVERLAP_WORDS
    while start < len(words):
        chunks.append(" ".join(words[start:start + _CHUNK_WORDS]))
        if start + _CHUNK_WORDS >= len(words):
            break
        start += step
    return chunks


def rechunk_doc(tenant_id: str, name: str) -> int:
    """(Re)write the chunk files for one stored doc. Returns the chunk count."""
    src = docs_dir(tenant_id) / name
    text = extract_text(src)
    remove_chunks(tenant_id, name)
    dest = _chunks_root(tenant_id) / name
    dest.mkdir(parents=True, exist_ok=True)
    chunks = chunk_text(text)
    for i, chunk in enumerate(chunks):
        (dest / f"{i}.txt").write_text(chunk, encoding="utf-8")
    return len(chunks)


def remove_chunks(tenant_id: str, name: str) -> None:
    shutil.rmtree(_chunks_root(tenant_id) / name, ignore_errors=True)


def chunk_count(tenant_id: str, name: str) -> int:
    d = _chunks_root(tenant_id) / name
    if not d.is_dir():
        return 0
    return sum(1 for p in d.glob("*.txt"))


def list_docs(tenant_id: str) -> list[dict[str, Any]]:
    """Uploaded docs (originals only) with size, mtime, and chunk counts."""
    out: list[dict[str, Any]] = []
    for p in sorted(docs_dir(tenant_id).iterdir()):
        if not p.is_file():
            continue
        st = p.stat()
        out.append({
            "name": p.name,
            "size": st.st_size,
            "uploaded_at": st.st_mtime,
            "chunks": chunk_count(tenant_id, p.name),
        })
    return out


def top_chunks(tenant_id: str, question: str, k: int = 3) -> list[dict[str, Any]]:
    """Top-k chunks by lowercase word-set overlap with the question.

    Zero-overlap chunks are dropped; no docs → empty list.
    """
    q_words = set(_WORD_RE.findall(question.lower()))
    if not q_words:
        return []
    root = _chunks_root(tenant_id)
    if not root.is_dir():
        return []
    scored: list[tuple[int, str, int, str]] = []
    for doc_dir in sorted(root.iterdir()):
        if not doc_dir.is_dir():
            continue
        for chunk_file in sorted(doc_dir.glob("*.txt")):
            text = chunk_file.read_text(encoding="utf-8", errors="replace")
            score = len(q_words & set(_WORD_RE.findall(text.lower())))
            if score > 0:
                scored.append((score, doc_dir.name, int(chunk_file.stem), text))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [
        {"doc": doc, "chunk": idx, "text": text}
        for _, doc, idx, text in scored[:k]
    ]
