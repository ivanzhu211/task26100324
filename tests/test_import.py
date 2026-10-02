"""乱序导入与重复导入：最终结果必须与手算一致。"""
import pytest

from backlinks import BacklinkRecord, BacklinkStore

# 同一条外链的三种写法（规范化后相同）：
#  - 协议/主机大小写、默认端口、末尾点
#  - utm_ 参数、片段
#  - 锚文本首尾与中间空白
MAIN_SRC = "http://src.com/page1"
MAIN_DST = "http://target.com/landing"

# 批次一：检查时间最新的数据先到
BATCH_NEW = [
    BacklinkRecord(
        MAIN_SRC, MAIN_DST,
        anchor_text="Alpha", link_type="dofollow",
        status="live", weight=9.0,
        first_seen="2024-01-01", last_checked="2024-03-01",
    ),
    # 同目标域名、不同来源的另一条外链
    BacklinkRecord(
        "http://src.com/page2", "http://target.com/other",
        anchor_text="Gamma", link_type="dofollow",
        status="live", weight=2.0,
        first_seen="2024-01-10", last_checked="2024-01-10",
    ),
]

# 批次二：中间时间的数据，URL 写法不同但指向同一外链
BATCH_MID = [
    BacklinkRecord(
        "HTTP://SRC.COM:80/page1", "http://TARGET.com./landing?utm_source=gg#top",
        anchor_text="  Alpha   ", link_type="dofollow",
        status="ok", weight=5.0,
        first_seen="2023-12-15", last_checked="2024-02-01",
    ),
    # 不同目标域名的外链
    BacklinkRecord(
        "http://src.com/page3", "http://other.org/",
        anchor_text="Delta", link_type="nofollow",
        status="live", weight=1.0,
        first_seen="2024-01-11", last_checked="2024-01-11",
    ),
]

# 批次三：最旧的数据最后到，另带一条锚文本/类型不一致的冲突记录
BATCH_OLD = [
    BacklinkRecord(
        "http://src.com/page1?utm_campaign=x", "http://target.com:80/landing",
        anchor_text="Alpha", link_type="dofollow",
        status="ok", weight=1.0,
        first_seen="2024-01-01", last_checked="2024-01-01",
    ),
    BacklinkRecord(
        "http://src.com/page1", "http://target.com/landing",
        anchor_text="Beta", link_type="nofollow",
        status="ok", weight=7.0,
        first_seen="2024-02-10", last_checked="2024-02-15",
    ),
]


@pytest.fixture()
def store(tmp_path):
    s = BacklinkStore(str(tmp_path / "links.db"))
    yield s
    s.close()


def import_all(store):
    store.import_records(BATCH_NEW)
    store.import_records(BATCH_MID)
    store.import_records(BATCH_OLD)


def test_out_of_order_import(store):
    import_all(store)

    # 主外链合并结果：状态/权重/最后检查时间取最新批次，首次发现取最早
    row = store.get_backlink(MAIN_SRC, MAIN_DST)
    assert row is not None
    assert row["anchor_text"] == "Alpha"
    assert row["link_type"] == "dofollow"
    assert row["status"] == "live"
    assert row["weight"] == 9.0
    assert row["last_checked"] == "2024-03-01"
    assert row["first_seen"] == "2023-12-15"

    # 冲突：锚文本与链接类型不一致的那条被保留为冲突
    conflicts = store.list_conflicts()
    assert len(conflicts) == 1
    assert conflicts[0]["anchor_text"] == "Beta"
    assert conflicts[0]["link_type"] == "nofollow"
    assert conflicts[0]["status"] == "ok"
    assert conflicts[0]["weight"] == 7.0
    assert conflicts[0]["first_seen"] == "2024-02-10"
    assert conflicts[0]["last_checked"] == "2024-02-15"

    # 总数：3 条外链；按目标域名统计
    assert store.count_by_target_domain("target.com") == 2
    assert store.count_by_target_domain("TARGET.COM.") == 2
    assert store.count_by_target_domain("other.org") == 1
    assert store.count_by_target_domain("missing.com") == 0


def test_reimport_is_idempotent(store):
    import_all(store)
    before_row = store.get_backlink(MAIN_SRC, MAIN_DST)
    before_conflicts = store.list_conflicts()
    before_count = store.count_by_target_domain("target.com")

    # 同一个文件重复导入：外链条数、冲突条数、字段值都不变
    import_all(store)

    assert store.get_backlink(MAIN_SRC, MAIN_DST) == before_row
    assert store.list_conflicts() == before_conflicts
    assert store.count_by_target_domain("target.com") == before_count
    assert store.count_by_target_domain("other.org") == 1


def test_duplicates_within_one_batch(store):
    # 同一批里互相重复的记录也按合并/冲突规则处理
    result = store.import_records([
        BacklinkRecord(
            "http://a.com/x", "http://b.com/y",
            anchor_text="One", link_type="dofollow",
            status="ok", weight=1.0,
            first_seen="2024-01-01", last_checked="2024-01-01",
        ),
        BacklinkRecord(
            "http://a.com/x", "http://b.com/y",
            anchor_text="One", link_type="dofollow",
            status="live", weight=2.0,
            first_seen="2024-01-02", last_checked="2024-01-02",
        ),
        BacklinkRecord(
            "http://a.com/x", "http://b.com/y",
            anchor_text="Two", link_type="dofollow",
            status="ok", weight=3.0,
            first_seen="2024-01-03", last_checked="2024-01-03",
        ),
    ])
    assert result.inserted == 1
    assert result.merged == 1
    assert result.conflicts == 1
    row = store.get_backlink("http://a.com/x", "http://b.com/y")
    assert row["status"] == "live"
    assert row["weight"] == 2.0
    assert row["first_seen"] == "2024-01-01"
    assert row["last_checked"] == "2024-01-02"
    assert len(store.list_conflicts()) == 1


def test_reimport_after_reopen(tmp_path):
    # 关掉重开同一个 SQLite 文件后，重复导入结果仍不变
    db = str(tmp_path / "links.db")
    s1 = BacklinkStore(db)
    s1.import_records(BATCH_NEW)
    s1.import_records(BATCH_MID)
    s1.import_records(BATCH_OLD)
    s1.close()

    s2 = BacklinkStore(db)
    s2.import_records(BATCH_NEW)
    s2.import_records(BATCH_MID)
    s2.import_records(BATCH_OLD)
    row = s2.get_backlink(MAIN_SRC, MAIN_DST)
    assert row["status"] == "live"
    assert row["weight"] == 9.0
    assert row["first_seen"] == "2023-12-15"
    assert row["last_checked"] == "2024-03-01"
    assert len(s2.list_conflicts()) == 1
    assert s2.count_by_target_domain("target.com") == 2
    s2.close()
