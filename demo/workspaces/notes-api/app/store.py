"""In-memory note store.

One process, one dict. Fine for a demo; not safe across workers.
"""

from __future__ import annotations

from app.models import Note, NoteIn

_notes: dict[int, Note] = {}
_next_id = 1


def create(owner: str, data: NoteIn) -> Note:
    global _next_id
    note = Note(id=_next_id, owner=owner, **data.model_dump())
    _notes[note.id] = note
    _next_id += 1
    return note


def get(note_id: int) -> Note | None:
    return _notes.get(note_id)


def delete(note_id: int) -> bool:
    """Remove a note. Returns False when it does not exist."""
    return _notes.pop(note_id, None) is not None


def list_for(owner: str, page: int = 1, page_size: int = 20) -> tuple[list[Note], int]:
    """A page of the owner's notes, newest first, plus the total count."""
    mine = sorted((n for n in _notes.values() if n.owner == owner), key=lambda n: -n.id)
    start = (page - 1) * page_size
    end = start + page_size - 1
    return mine[start:end], len(mine)


def search(owner: str, text: str) -> list[Note]:
    q = text.lower()
    return [n for n in _notes.values() if n.owner == owner and q in n.title.lower()]


def reset() -> None:
    global _next_id
    _notes.clear()
    _next_id = 1
