"""SQLite 存储与导入去重逻辑。"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Union
from urllib.parse import urlsplit

from .models import BacklinkRecord, ConflictRecord, StoredBacklink
from .urlnorm import normalize_domain, normalize_url

_WS_RE = re.compile(r"\s+")


def _normalize_anchor(text: str) -> str:
    """锚文本归一：去首尾空白，中间连续空白算一个。"""
    return _WS_RE.sub(" ", text.strip())


def _to_str(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt is not None else None


def _to_dt(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value is not None else None


class BacklinkStore:
    """外链库：导入去重、冲突记录、按目标域名统计。"""

    def __init__(self, db_path: Union[str, Path]) -> None:
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS backlinks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_key TEXT NOT NULL,
                target_key TEXT NOT NULL,
                target_domain TEXT NOT NULL,
                source_url TEXT NOT NULL,
                target_url TEXT NOT NULL,
                anchor_text TEXT NOT NULL,
                link_type TEXT NOT NULL,
                status TEXT NOT NULL,
                weight REAL NOT NULL,
                first_seen TEXT,
                last_checked TEXT,
                UNIQUE (source_key, target_key)
            );
            CREATE TABLE IF NOT EXISTS conflicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backlink_id INTEGER NOT NULL REFERENCES backlinks(id),
                source_url TEXT NOT NULL,
                target_url TEXT NOT NULL,
                anchor_text TEXT NOT NULL,
                link_type TEXT NOT NULL,
                status TEXT NOT NULL,
                weight REAL NOT NULL,
                first_seen TEXT,
                last_checked TEXT,
                UNIQUE (backlink_id, source_url, target_url, anchor_text,
                        link_type, status, weight, first_seen, last_checked)
            );
            """
        )
        self._conn.commit()

    def import_records(self, records: Iterable[BacklinkRecord]) -> None:
        """导入一批记录，按业务规则合并或记冲突。"""
        with self._conn:
            for record in records:
                self._import_one(record)

    def _import_one(self, record: BacklinkRecord) -> None:
        source_key = normalize_url(record.source_url)
        target_key = normalize_url(record.target_url)
        anchor = _normalize_anchor(record.anchor_text)
        link_type = record.link_type
        first_seen = _to_str(record.first_seen)
        last_checked = _to_str(record.last_checked)

        row = self._conn.execute(
            "SELECT * FROM backlinks WHERE source_key = ? AND target_key = ?",
            (source_key, target_key),
        ).fetchone()

        if row is None:
            self._conn.execute(
                """
                INSERT INTO backlinks (
                    source_key, target_key, target_domain,
                    source_url, target_url, anchor_text, link_type,
                    status, weight, first_seen, last_checked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_key,
                    target_key,
                    urlsplit(target_key).hostname or "",
                    record.source_url,
                    record.target_url,
                    anchor,
                    link_type,
                    record.status,
                    record.weight,
                    first_seen,
                    last_checked,
                ),
            )
            return

        if anchor == row["anchor_text"] and link_type == row["link_type"]:
            self._merge(row, record, first_seen, last_checked)
        else:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO conflicts (
                    backlink_id, source_url, target_url, anchor_text,
                    link_type, status, weight, first_seen, last_checked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    record.source_url,
                    record.target_url,
                    anchor,
                    link_type,
                    record.status,
                    record.weight,
                    first_seen,
                    last_checked,
                ),
            )

    def _merge(
        self,
        row: sqlite3.Row,
        record: BacklinkRecord,
        first_seen: Optional[str],
        last_checked: Optional[str],
    ) -> None:
        existing_checked = row["last_checked"]
        incoming_later = last_checked is not None and (
            existing_checked is None or last_checked > existing_checked
        )
        if incoming_later:
            status, weight, checked = record.status, record.weight, last_checked
        else:
            status, weight, checked = row["status"], row["weight"], existing_checked

        seen_candidates = [v for v in (row["first_seen"], first_seen) if v is not None]
        first = min(seen_candidates) if seen_candidates else None

        self._conn.execute(
            """
            UPDATE backlinks
            SET status = ?, weight = ?, first_seen = ?, last_checked = ?
            WHERE id = ?
            """,
            (status, weight, first, checked, row["id"]),
        )

    def list_backlinks(self) -> List[StoredBacklink]:
        rows = self._conn.execute(
            "SELECT * FROM backlinks ORDER BY id"
        ).fetchall()
        return [
            StoredBacklink(
                id=r["id"],
                source_url=r["source_url"],
                target_url=r["target_url"],
                source_key=r["source_key"],
                target_key=r["target_key"],
                anchor_text=r["anchor_text"],
                link_type=r["link_type"],
                status=r["status"],
                weight=r["weight"],
                first_seen=_to_dt(r["first_seen"]),
                last_checked=_to_dt(r["last_checked"]),
            )
            for r in rows
        ]

    def list_conflicts(self) -> List[ConflictRecord]:
        rows = self._conn.execute(
            "SELECT * FROM conflicts ORDER BY id"
        ).fetchall()
        return [
            ConflictRecord(
                id=r["id"],
                backlink_id=r["backlink_id"],
                source_url=r["source_url"],
                target_url=r["target_url"],
                anchor_text=r["anchor_text"],
                link_type=r["link_type"],
                status=r["status"],
                weight=r["weight"],
                first_seen=_to_dt(r["first_seen"]),
                last_checked=_to_dt(r["last_checked"]),
            )
            for r in rows
        ]

    def count_by_target_domain(self, domain: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM backlinks WHERE target_domain = ?",
            (normalize_domain(domain),),
        ).fetchone()
        return row["n"]

    def close(self) -> None:
        self._conn.close()
