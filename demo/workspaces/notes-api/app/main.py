"""HTTP routes for notes-api."""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Query

from app import store
from app.auth import current_user
from app.models import Note, NoteIn, Page

app = FastAPI(title="notes-api", version="0.3.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/notes", response_model=Note, status_code=201)
def create_note(data: NoteIn, user: str = Depends(current_user)) -> Note:
    return store.create(user, data)


@app.get("/notes", response_model=Page)
def list_notes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: str = Depends(current_user),
) -> Page:
    items, total = store.list_for(user, page, page_size)
    return Page(items=items, page=page, page_size=page_size, total=total)


@app.get("/notes/search", response_model=list[Note])
def search_notes(q: str, user: str = Depends(current_user)) -> list[Note]:
    return store.search(user, q)


@app.get("/notes/{note_id}", response_model=Note)
def read_note(note_id: int, user: str = Depends(current_user)) -> Note:
    note = store.get(note_id)
    if note is None or note.owner != user:
        raise HTTPException(status_code=404, detail="no such note")
    return note


@app.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int, user: str = Depends(current_user)) -> None:
    if not store.delete(note_id):
        raise HTTPException(status_code=404, detail="no such note")
