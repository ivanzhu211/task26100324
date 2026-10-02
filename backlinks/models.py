"""数据类型定义：外链记录与导入结果。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BacklinkRecord:
    """一条待导入的外链记录（爬虫导出的一行）。"""

    source_url: str
    target_url: str
    anchor_text: str = ""
    link_type: str = ""
    status: str = ""
    weight: float = 0.0
    first_seen: Optional[str] = None
    last_checked: Optional[str] = None


@dataclass
class ImportResult:
    """一次导入的统计结果。"""

    inserted: int = 0
    merged: int = 0
    conflicts: int = 0
