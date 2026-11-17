"""Synthetic v2 database inputs shared by Phase 2g tests and its probe."""

import json
import sqlite3
from pathlib import Path

from docket.schema import MIGRATION_1, MIGRATION_2

NOW = "2026-11-17T14:00:00+00:00"
STAMP = "2026-11-17T14:00:00.000000+00:00"
BODY = {
    "source": "email",
    "title": "Synthetic reference task",
    "deadline": None,
    "provider": "gmail",
    "message_id": "synthetic/1",
    "link": "https://mail.example/1",
}
LINK = {
    "source": "email",
    "provider": "gmail",
    "message_id": "synthetic/2",
    "link": "https://mail.example/2",
}


def version_two(path: Path) -> None:
    db = sqlite3.connect(path, isolation_level=None)
    try:
        db.executescript(MIGRATION_1 + MIGRATION_2)
        db.execute(
            "INSERT INTO tasks(title,state,source,provider,message_id,link,created_at,updated_at) "
            "VALUES ('Synthetic reference task','open','email','gmail','synthetic/1',"
            "'https://mail.example/1',?,?)",
            (STAMP, STAMP),
        )
        db.execute(
            "INSERT INTO audit_log(task,at,action,actor,before,after) "
            "VALUES (1,?,'create','email','{}',?)",
            (STAMP, '{"title":"Synthetic reference task"}'),
        )
        for message_id in ("synthetic/2", "synthetic/pruned"):
            db.execute(
                "INSERT INTO links(task,provider,message_id,link,created_at) "
                "VALUES (1,'gmail',?,'https://mail.example/2',?)",
                (message_id, STAMP),
            )
        db.execute("DELETE FROM links WHERE number=2")
        for key, body, link in (("task-key", BODY, None), ("link-key", LINK, 1)):
            db.execute(
                "INSERT INTO request_keys(client,key,request,task,link,created_at) "
                "VALUES ('email',?,?,1,?,?)",
                (
                    key,
                    json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")),
                    link,
                    STAMP,
                ),
            )
        db.execute("PRAGMA user_version = 2")
    finally:
        db.close()


def snapshot(path: Path) -> dict[str, list[tuple]]:
    db = sqlite3.connect(path)
    try:
        return {
            table: db.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            for table in ("tasks", "audit_log", "links", "request_keys", "sqlite_sequence")
        }
    finally:
        db.close()
