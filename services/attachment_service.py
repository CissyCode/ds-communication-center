"""File-save convention for attachments — ready for a future upload UI, not
called by any view this phase. Metadata goes to SQLite via
attachment_repository; the actual bytes always go to disk under
storage/files/, never into SQLite and never held in session_state."""
from __future__ import annotations

import uuid
from pathlib import Path

from repository import attachment_repository as repo

STORAGE_ROOT = Path(__file__).resolve().parent.parent / "storage" / "files"


def save_attachment(
    *, entity_type: str, entity_id: str, attachment_type: str,
    file_name: str, file_bytes: bytes, mime_type: str | None = None,
) -> str:
    folder = STORAGE_ROOT / entity_type / entity_id
    folder.mkdir(parents=True, exist_ok=True)

    ext = Path(file_name).suffix
    stored_name = f"{uuid.uuid4().hex}{ext}"
    (folder / stored_name).write_bytes(file_bytes)

    attachment_id = f"AT-{uuid.uuid4().hex[:8]}"
    repo.create({
        "attachment_id": attachment_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "attachment_type": attachment_type,
        "file_name": file_name,
        "stored_name": stored_name,
        "file_path": str((folder / stored_name).relative_to(STORAGE_ROOT.parent)),
        "mime_type": mime_type,
        "file_size": len(file_bytes),
    })
    return attachment_id


def list_attachments(entity_type: str, entity_id: str) -> list[dict]:
    return repo.get_all_for_entity(entity_type, entity_id)
