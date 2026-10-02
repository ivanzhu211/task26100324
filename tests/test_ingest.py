"""乱序导入：新数据先到、旧数据后到，再重复导入一次，结果必须不变。"""
import unittest
from datetime import datetime

from backlinks import BacklinkRecord, BacklinkStore


def rec(source, target, anchor, link_type, status, weight, first, checked):
    return BacklinkRecord(
        source_url=source,
        target_url=target,
        anchor_text=anchor,
        link_type=link_type,
        status=status,
        weight=weight,
        first_seen=datetime(*first),
        last_checked=datetime(*checked),
    )


# 外链 L1: a.com/x -> b.com/page（两批写法不同但规范化为同一条）
L1_NEW = rec("HTTP://A.com/x", "https://B.com:443/page?utm_source=g",
             "  Hello   World ", "dofollow", "live", 5.0,
             (2024, 3, 1), (2024, 6, 1))
L1_OLD = rec("http://a.com/x", "https://b.com/page",
             "Hello World", "dofollow", "dead", 2.0,
             (2024, 1, 1), (2024, 4, 1))
L1_OLD_DUP = rec("http://a.com./x#frag", "https://b.com:443/page?utm_campaign=x",
             "Hello World", "dofollow", "dead", 2.0,
             (2024, 1, 1), (2024, 4, 1))

# 外链 L2: c.com/y -> b.com/other（两批锚文本不同，产生冲突）
L2_NEW = rec("http://c.com/y", "https://b.com/other",
             "Anchor A", "dofollow", "live", 7.0,
             (2024, 5, 1), (2024, 6, 1))
L2_OLD = rec("http://c.com/y", "https://b.com/other",
             "Anchor B", "dofollow", "dead", 3.0,
             (2024, 2, 1), (2024, 4, 1))

BATCH_NEWER_FIRST = [L1_NEW, L2_NEW]
BATCH_OLDER_SECOND = [L1_OLD, L1_OLD_DUP, L2_OLD]


class TestOutOfOrderImport(unittest.TestCase):
    def setUp(self):
        self.store = BacklinkStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_out_of_order_then_reimport(self):
        self.store.import_records(BATCH_NEWER_FIRST)
        self.store.import_records(BATCH_OLDER_SECOND)
        # 同一个文件重复导入，结果不能变
        self.store.import_records(BATCH_NEWER_FIRST)
        self.store.import_records(BATCH_OLDER_SECOND)

        backlinks = self.store.list_backlinks()
        conflicts = self.store.list_conflicts()

        self.assertEqual(len(backlinks), 2)
        self.assertEqual(len(conflicts), 1)

        l1 = next(b for b in backlinks if b.target_key.endswith("/page"))
        l2 = next(b for b in backlinks if b.target_key.endswith("/other"))

        # L1：合并 —— 状态/权重/最后检查时间取较新那次，首次发现取较早那次
        self.assertEqual(l1.anchor_text, "Hello World")
        self.assertEqual(l1.link_type, "dofollow")
        self.assertEqual(l1.status, "live")
        self.assertEqual(l1.weight, 5.0)
        self.assertEqual(l1.first_seen, datetime(2024, 1, 1))
        self.assertEqual(l1.last_checked, datetime(2024, 6, 1))

        # L2：说法不一致，保留已有记录
        self.assertEqual(l2.anchor_text, "Anchor A")
        self.assertEqual(l2.status, "live")
        self.assertEqual(l2.weight, 7.0)
        self.assertEqual(l2.first_seen, datetime(2024, 5, 1))
        self.assertEqual(l2.last_checked, datetime(2024, 6, 1))

        # 冲突记录完整保留旧数据的说法
        conflict = conflicts[0]
        self.assertEqual(conflict.backlink_id, l2.id)
        self.assertEqual(conflict.anchor_text, "Anchor B")
        self.assertEqual(conflict.link_type, "dofollow")
        self.assertEqual(conflict.status, "dead")
        self.assertEqual(conflict.weight, 3.0)
        self.assertEqual(conflict.first_seen, datetime(2024, 2, 1))
        self.assertEqual(conflict.last_checked, datetime(2024, 4, 1))

        # 按目标域名统计
        self.assertEqual(self.store.count_by_target_domain("b.com"), 2)
        self.assertEqual(self.store.count_by_target_domain("B.COM."), 2)
        self.assertEqual(self.store.count_by_target_domain("a.com"), 0)


if __name__ == "__main__":
    unittest.main()
