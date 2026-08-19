from __future__ import annotations

import asyncio

import structlog

from horus import jsondb

logger = structlog.get_logger(service="json_sync.local_client")


class JsonLocalClient:
    """In-process adapter over ``horus.jsondb`` that matches the async interface
    ``JsonSyncService`` expects (previously satisfied by an HTTP ``JsonServerClient``).

    ``horus.jsondb`` operations are synchronous and guarded by a cross-process file
    lock (``filelock``). Every call is offloaded to a worker thread via
    ``asyncio.to_thread`` so the sync event loop is never blocked on the lock / file
    I/O. Concurrent in-process callers still serialize correctly through the OS-level
    file lock — identical to the multi-process arrangement the store already supports.

    ``db_path=None`` lets ``jsondb`` fall back to its own ``JSON_DB_PATH`` default
    (``<repo>/db.json``). The explicit param exists so tests can point a client at an
    isolated temp store without patching module globals.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path

    async def get_all_matches(self, source: str = "1x") -> list[dict]:
        """Return the full collection for ``source`` (or [] on any failure)."""
        try:
            return await asyncio.to_thread(jsondb.get_collection, source, self.db_path)
        except Exception:
            logger.exception("local_client_get_all_error", source=source)
            return []

    async def post_match(self, source: str, data: dict) -> bool:
        """Upsert semantics: insert; if the id already exists (jsondb raises
        ``ValueError``), fall back to a full-replace update. Returns True on success.

        Mirrors ``JsonServerClient.post_match(source, data)`` — no separate id arg,
        the id is carried in ``data['id']`` (set by ``converter.match_data_to_json``).
        """
        match_id = data.get("id")
        try:
            await asyncio.to_thread(jsondb.insert_record, source, data, self.db_path)
            return True
        except ValueError:
            # id already exists -> update in place (same full-replace semantics as PUT)
            if match_id is None:
                logger.warning("local_client_post_conflict_no_id", source=source)
                return False
            try:
                result = await asyncio.to_thread(
                    jsondb.update_record, source, match_id, data, self.db_path
                )
                return result is not None
            except Exception:
                logger.exception(
                    "local_client_post_fallback_update_error", match_id=match_id
                )
                return False
        except Exception:
            logger.exception("local_client_post_error", match_id=match_id)
            return False

    async def put_match(self, source: str, match_id: str, data: dict) -> bool:
        """Update the record; if it doesn't exist yet (jsondb returns None), insert it.
        Returns True on success. ``data['id']`` equals ``match_id`` by construction at
        every call site, but we force it on the insert path defensively.
        """
        try:
            result = await asyncio.to_thread(
                jsondb.update_record, source, match_id, data, self.db_path
            )
            if result is not None:
                return True
            # Not found -> insert. Force the intended id so a caller bug can't cause a
            # silent insert under an auto-generated id.
            insert_payload = dict(data)
            insert_payload["id"] = match_id
            await asyncio.to_thread(
                jsondb.insert_record, source, insert_payload, self.db_path
            )
            return True
        except ValueError:
            # Lost a race: another writer inserted match_id between our update-miss and
            # our insert attempt. Retry as an update — it must exist now.
            try:
                result = await asyncio.to_thread(
                    jsondb.update_record, source, match_id, data, self.db_path
                )
                return result is not None
            except Exception:
                logger.exception("local_client_put_race_retry_error", match_id=match_id)
                return False
        except Exception:
            logger.exception("local_client_put_error", match_id=match_id)
            return False

    async def delete_match(self, source: str, match_id: str) -> bool:
        """Idempotent delete: return True if the record was removed OR is already
        absent. The service retries on False, so "already gone" MUST be True.
        """
        try:
            removed = await asyncio.to_thread(
                jsondb.delete_record, source, match_id, self.db_path
            )
            if removed:
                return True
            # jsondb returns False only for "not found" (I/O errors raise). Confirm
            # absence via get_record so we swallow exactly the not-found case.
            existing = await asyncio.to_thread(
                jsondb.get_record, source, match_id, self.db_path
            )
            return existing is None
        except Exception:
            logger.exception("local_client_delete_error", match_id=match_id)
            return False
