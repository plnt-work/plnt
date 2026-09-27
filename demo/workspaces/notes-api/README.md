# notes-api

A small HTTP API for personal notes: create, list (paged), read, delete.
Built with FastAPI and an in-memory store. Users authenticate with a bearer
token; every note belongs to the user that created it.

    pip install -e .
    uvicorn app.main:app --reload

There are no tests yet.
