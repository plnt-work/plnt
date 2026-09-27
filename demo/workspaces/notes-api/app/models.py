from __future__ import annotations

from pydantic import BaseModel, Field


class NoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = ""
    tags: list[str] = Field(default_factory=list)


class Note(NoteIn):
    id: int
    owner: str


class Page(BaseModel):
    items: list[Note]
    page: int
    page_size: int
    total: int
