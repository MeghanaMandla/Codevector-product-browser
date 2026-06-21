"""
Cursor encoding/decoding for keyset (seek) pagination.

The cursor is an opaque, base64-encoded JSON object carrying the last row's
sort key: {"updated_at": "...", "id": ...}. Base64-encoding it means the
client never needs to know — or be able to tamper meaningfully with — the
internal shape; it just passes back whatever string it was given.

Why (updated_at, id) and not just updated_at?
updated_at alone is not unique (two products can be updated in the same
millisecond), so paginating on it alone could skip or repeat rows whose
timestamps tie. Appending id as a tiebreaker makes the sort key unique,
which is required for keyset pagination to be exact.
"""
import base64
import json
from datetime import datetime
from typing import Tuple


def encode_cursor(updated_at: datetime, id_: int) -> str:
    payload = {"updated_at": updated_at.isoformat(), "id": id_}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def decode_cursor(cursor: str) -> Tuple[datetime, int]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8"))
        payload = json.loads(raw)
        updated_at = datetime.fromisoformat(payload["updated_at"])
        id_ = int(payload["id"])
        return updated_at, id_
    except (ValueError, KeyError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Invalid pagination cursor") from exc
