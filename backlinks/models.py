"""数据类型定义：外链记录与冲突记录。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class BacklinkRecord:
    """一次导入中的一条外链记录。"""

    source_url: str
    target_url: str
    anchor_text: str = ""
    link_type: str = ""  # 例如 "dofollow" / "nofollow"
    status: str = ""
    weight: float = 0.0
    first_seen: Optional[datetime] = None
    last_checked: Optional[datetime] = None


@dataclass
class StoredBacklink:
    """库中已合并的外链。"""

    id: int
    source_url: str
    target_url: str
    source_key: str
    target_key: str
    anchor_text: str
    link_type: str
    status: str
    weight: float
    first_seen: Optional[datetime]
    last_checked: Optional[datetime]


@dataclass
class ConflictRecord:
    """同一外链前后说法不一致时保留的冲突记录。"""

    id: int
    backlink_id: int
    source_url: str
    target_url: str
    anchor_text: str
    link_type: str
    status: str
    weight: float
    first_seen: Optional[datetime]
    last_checked: Optional[datetime]
