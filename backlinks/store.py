"""SQLite 存储层：外链入库、去重合并、冲突记录与查询。"""
from __future__ import annotations

import sqlite3
from typing import Iterable, List, Optional

from .models import BacklinkRecord, ImportResult
from .urlnorm import _normalize_host, normalize_url

_SCHEMA = """
CREATE TABLE IF NOT EXISTS backlinks (
    id INTEGER PRIMARY KEY,
    source_key TEXT NOT NULL,
    target_key TEXT NOT NULL,
    source_url TEXT NOT NULL,
    target_url TEXT NOT NULL,
    anchor_text TEXT NOT NULL DEFAULT '',
    link_type TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    weight REAL NOT NULL DEFAULT 0,
    first_seen TEXT NOT NULL DEFAULT '',
    last_checked TEXT NOT NULL DEFAULT '',
    target_domain TEXT NOT NULL,
    UNIQUE (source_key, target_key)
);
CREATE TABLE IF NOT EXISTS conflicts (
    id INTEGER PRIMARY KEY,
    backlink_id INTEGER NOT NULL REFERENCES backlinks (id),
    source_url TEXT NOT NULL,
    target_url TEXT NOT NULL,
    anchor_text TEXT NOT NULL DEFAULT '',
    link_type TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    weight REAL NOT NULL DEFAULT 0,
    first_seen TEXT NOT NULL DEFAULT '',
    last_checked TEXT NOT NULL DEFAULT '',
    UNIQUE (
        backlink_id, anchor_text, link_type,
        status, weight, first_seen, last_checked
    )
);
"""


def _normalize_anchor(text: str) -> str:
    """锚文本规范化：去首尾空白，中间连续空白算一个。"""
    return " ".join((text or "").split())


class BacklinkStore:
    """外链库。数据保存在本地 SQLite 文件中。"""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def import_records(self, records: Iterable[BacklinkRecord]) -> ImportResult:
        """导入一批外链记录，按业务规则去重、合并或记冲突。"""
        result = ImportResult()
        with self._conn:
            for rec in records:
                self._import_one(rec, result)
        return result

    def _import_one(self, rec: BacklinkRecord, result: ImportResult) -> None:
        source_key = normalize_url(rec.source_url)
        target_key = normalize_url(rec.target_url)
        anchor = _normalize_anchor(rec.anchor_text)
        link_type = rec.link_type or ""
        row = self._conn.execute(
            "SELECT * FROM backlinks WHERE source_key = ? AND target_key = ?",
            (source_key, target_key),
        ).fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO backlinks (source_key, target_key, source_url,"
                " target_url, anchor_text, link_type, status, weight,"
                " first_seen, last_checked, target_domain)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    source_key,
                    target_key,
                    rec.source_url,
                    rec.target_url,
                    anchor,
                    link_type,
                    rec.status or "",
                    rec.weight,
                    rec.first_seen or "",
                    rec.last_checked or "",
                    self._target_domain(target_key),
                ),
            )
            result.inserted += 1
            return
        if row["anchor_text"] == anchor and row["link_type"] == link_type:
            # 合并：状态/权重/最后检查时间取检查时间更晚者，首次发现取更早者
            last_checked = row["last_checked"]
            status = row["status"]
            weight = row["weight"]
            if (rec.last_checked or "") > last_checked:
                last_checked = rec.last_checked or ""
                status = rec.status or ""
                weight = rec.weight
            first_seen = row["first_seen"]
            if rec.first_seen and (not first_seen or rec.first_seen < first_seen):
                first_seen = rec.first_seen
            self._conn.execute(
                "UPDATE backlinks SET status = ?, weight = ?,"
                " first_seen = ?, last_checked = ? WHERE id = ?",
                (status, weight, first_seen, last_checked, row["id"]),
            )
            result.merged += 1
            return
        # 锚文本或链接类型不一致：保留已有记录，本次记为冲突（可幂等）
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO conflicts (backlink_id, source_url,"
            " target_url, anchor_text, link_type, status, weight,"
            " first_seen, last_checked) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row["id"],
                rec.source_url,
                rec.target_url,
                anchor,
                link_type,
                rec.status or "",
                rec.weight,
                rec.first_seen or "",
                rec.last_checked or "",
            ),
        )
        if cur.rowcount:
            result.conflicts += 1

    @staticmethod
    def _target_domain(target_key: str) -> str:
        netloc = target_key.split("://", 1)[-1].split("/", 1)[0]
        netloc = netloc.split("@")[-1]
        if netloc.startswith("["):
            return netloc[1 : netloc.index("]")]
        return netloc.split(":")[0]

    def count_by_target_domain(self, domain: str) -> int:
        """按目标域名统计外链总数。"""
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM backlinks WHERE target_domain = ?",
            (_normalize_host(domain),),
        ).fetchone()
        return row["c"]

    def get_backlink(self, source_url: str, target_url: str) -> Optional[dict]:
        """按来源+目标 URL 查询合并后的外链记录。"""
        row = self._conn.execute(
            "SELECT * FROM backlinks WHERE source_key = ? AND target_key = ?",
            (normalize_url(source_url), normalize_url(target_url)),
        ).fetchone()
        return dict(row) if row else None

    def list_conflicts(self) -> List[dict]:
        """列出全部冲突记录。"""
        rows = self._conn.execute(
            "SELECT * FROM conflicts ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        """关闭数据库连接。"""
        self._conn.close()
