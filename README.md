# backlinks：外链入库与去重模块

供上层 SEO 分析服务调用的 Python 库，数据存本地 SQLite 文件，无接口层。

## 用法

```python
from datetime import datetime
from backlinks import BacklinkRecord, BacklinkStore

store = BacklinkStore("links.db")          # 本地 SQLite 文件；":memory:" 亦可
store.import_records([
    BacklinkRecord(
        source_url="http://a.com/x",
        target_url="https://b.com/page",
        anchor_text="Hello",
        link_type="dofollow",
        status="live",
        weight=5.0,
        first_seen=datetime(2024, 1, 1),
        last_checked=datetime(2024, 6, 1),
    ),
])

store.list_backlinks()                     # 合并后的外链
store.list_conflicts()                     # 说法不一致被保留的冲突记录
store.count_by_target_domain("b.com")      # 按目标域名统计外链总数
store.close()
```

## 规则摘要

- 一条外链 = 规范化后的来源 URL + 目标 URL；规范化规则见 `backlinks/urlnorm.py`
  （大小写、默认端口、末尾点、IDN、IPv6、百分号编码、点段、空路径、片段、
  utm_ 参数、参数顺序等均按业务规则归一）。
- 同一外链再次出现：锚文本（去首尾空白、连续空白合一）与链接类型都一致则合并
  （状态/权重/最后检查时间取较新，首次发现取较早）；否则保留已有记录，
  本次记为冲突，不丢弃。
- 同一文件重复导入结果不变（外链与冲突均不增加）。

## 测试

```
python3 -m unittest discover -s tests -v
```

- `tests/test_urlnorm.py`：URL 对照表，逐对验证每条“相同 / 不同”规则。
- `tests/test_ingest.py`：乱序导入（新数据先到、旧数据后到）再重复导入，
  校验外链条数、冲突条数与每个字段的值。
