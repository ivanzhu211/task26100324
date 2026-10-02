# task26100324 — 外链入库与去重库

供上层 SEO 分析服务直接调用的 Python 库，数据保存在本地 SQLite 文件中，无接口层。

## 结构

- `backlinks/urlnorm.py` — URL 规范化与相同性判断（`normalize_url` / `urls_equal`）
- `backlinks/store.py` — SQLite 存储：导入去重、合并、冲突记录、按目标域名统计（`BacklinkStore`）
- `backlinks/models.py` — `BacklinkRecord`（导入记录）与 `ImportResult`（导入统计）
- `tests/` — 自动化测试（URL 对照表、乱序导入、重复导入幂等）

## 用法

```python
from backlinks import BacklinkRecord, BacklinkStore

store = BacklinkStore("links.db")
result = store.import_records([
    BacklinkRecord(
        source_url="http://src.com/page",
        target_url="http://target.com/landing",
        anchor_text="Example", link_type="dofollow",
        status="live", weight=9.0,
        first_seen="2024-01-01", last_checked="2024-03-01",
    ),
])
print(result)  # ImportResult(inserted=1, merged=0, conflicts=0)

store.count_by_target_domain("target.com")   # 按目标域名统计外链总数
store.get_backlink(src, dst)                 # 查询合并后的外链
store.list_conflicts()                       # 列出冲突记录
store.close()
```

## 规则要点

- 一条外链 = 规范化后的（来源 URL, 目标 URL）。
- 相同：协议/主机大小写、默认端口、主机末尾点、IDN Unicode/punycode、IP 地址等价写法、
  百分号十六进制大小写、非保留字符编解码、路径与查询里未编码的非 ASCII/空格、
  点段解析、空路径、片段、`utm_` 参数、参数顺序。
- 不同：http/https、www. 有无、路径大小写、非根路径末尾 `/`、保留字符编解码（%2F 等）、
  路径里的 `+` 与空格、同名参数值的出现顺序。
- 重复出现：锚文本（空白折叠）与链接类型一致则合并（状态/权重/最后检查时间取更晚，
  首次发现取更早）；不一致则保留已有记录并记为冲突。
- 同一文件重复导入幂等：外链与冲突都不会变多。

## 测试

```bash
python3 -m pytest tests/ -q
```
