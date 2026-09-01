import os
import json
import tempfile
import threading
from filelock import FileLock
from livescore.config import logger, JSON_DB_PATH

COLLECTIONS = ('1x', '8x')
LOCK_TIMEOUT = 10

# Process-local mutex around every read-modify-write. The FileLock below handles
# CROSS-process safety, but when the sync loops run in a background thread inside
# the Streamlit process (see livescore.json_sync.embedded), several writer threads (the
# updater offloads jsondb calls via asyncio.to_thread) plus the Streamlit reader
# share one process — and same-process fcntl locks don't reliably exclude each
# other. This RLock guarantees intra-process serialization regardless. Always
# acquired OUTSIDE the FileLock (consistent order => no deadlock).
_PROCESS_LOCK = threading.RLock()


def _lock(db_path):
    return FileLock(db_path + '.lock', timeout=LOCK_TIMEOUT)


def _seed(collections=COLLECTIONS):
    return {c: [] for c in collections}


def _save_atomic(data, db_path):
    # Write to a temp file on the same filesystem, then atomically replace.
    dir_ = os.path.dirname(db_path) or '.'
    fd, tmp_path = tempfile.mkstemp(prefix='.db_', suffix='.tmp', dir=dir_)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, db_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _load_unlocked(db_path):
    # Read the whole document. Auto-create or self-heal a missing/corrupt file.
    if not os.path.exists(db_path):
        data = _seed()
        _save_atomic(data, db_path)
        return data
    try:
        with open(db_path, 'r') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError('db root is not an object')
        return data
    except (ValueError, json.JSONDecodeError) as e:
        logger.error(f'db.json is corrupt, re-seeding: {e}')
        data = _seed()
        _save_atomic(data, db_path)
        return data


def ensure_db(db_path=None):
    db_path = db_path or JSON_DB_PATH
    with _PROCESS_LOCK, _lock(db_path):
        if not os.path.exists(db_path):
            _save_atomic(_seed(), db_path)


def _write_txn(mutate, db_path=None):
    # Serialize the read-modify-write cycle across processes.
    db_path = db_path or JSON_DB_PATH
    with _PROCESS_LOCK, _lock(db_path):
        db = _load_unlocked(db_path)
        result = mutate(db)
        _save_atomic(db, db_path)
        return result


def next_id(records):
    int_ids = []
    for r in records:
        try:
            int_ids.append(int(r.get('id')))
        except (TypeError, ValueError):
            continue
    return str(max(int_ids) + 1) if int_ids else '1'


def get_collection(source, db_path=None):
    db_path = db_path or JSON_DB_PATH
    with _PROCESS_LOCK, _lock(db_path):
        db = _load_unlocked(db_path)
    return db.get(source, [])


def query_collection(source, predicate=None, db_path=None):
    records = get_collection(source, db_path)
    if predicate is None:
        return records
    return [r for r in records if predicate(r)]


def get_record(source, record_id, db_path=None):
    for r in get_collection(source, db_path):
        if str(r.get('id')) == str(record_id):
            return r
    return None


def insert_record(source, record, db_path=None):
    def mutate(db):
        records = db.setdefault(source, [])
        new_record = dict(record)
        rid = new_record.get('id')
        if rid not in (None, ''):
            new_record['id'] = str(rid)
            if any(str(r.get('id')) == new_record['id'] for r in records):
                raise ValueError(f"id already exists: {new_record['id']}")
        else:
            new_record['id'] = next_id(records)
        records.append(new_record)
        return new_record
    return _write_txn(mutate, db_path)


def update_record(source, record_id, record, db_path=None):
    def mutate(db):
        records = db.setdefault(source, [])
        for i, r in enumerate(records):
            if str(r.get('id')) == str(record_id):
                new_record = dict(record)
                new_record['id'] = str(record_id)  # PUT is a full replace but keeps the id
                records[i] = new_record
                return new_record
        return None
    return _write_txn(mutate, db_path)


def delete_record(source, record_id, db_path=None):
    def mutate(db):
        records = db.setdefault(source, [])
        for i, r in enumerate(records):
            if str(r.get('id')) == str(record_id):
                del records[i]
                return True
        return False
    return _write_txn(mutate, db_path)


# Create the store at import time (idempotent), mirroring config.py's os.makedirs(TEMP_FOLDER).
ensure_db()
