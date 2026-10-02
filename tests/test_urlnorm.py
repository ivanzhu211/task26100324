"""URL 对照表：逐对验证每条“相同”与“不同”规则。"""
import pytest

from backlinks import urls_equal

SAME_PAIRS = [
    # 协议不区分大小写
    ("HTTP://example.com/", "http://example.com/"),
    # 主机名不区分大小写
    ("http://ExAmPlE.COM/", "http://example.com/"),
    # http 默认端口 80
    ("http://example.com:80/", "http://example.com/"),
    # https 默认端口 443
    ("https://example.com:443/", "https://example.com/"),
    # 主机名末尾的点忽略
    ("http://example.com./", "http://example.com/"),
    # 国际化域名 Unicode 与 punycode
    ("http://bücher.de/", "http://xn--bcher-kva.de/"),
    # IPv6 不同写法
    (
        "http://[2001:0db8:0000:0000:0000:ff00:0042:8329]/",
        "http://[2001:db8::ff00:42:8329]/",
    ),
    # 百分号编码十六进制不分大小写
    ("http://example.com/a%2fb", "http://example.com/a%2Fb"),
    # 非保留字符编码与不编码一样
    ("http://example.com/%7Euser/%41", "http://example.com/~user/A"),
    # 路径里未编码的非 ASCII 与 UTF-8 百分号编码
    ("http://example.com/页面", "http://example.com/%E9%A1%B5%E9%9D%A2"),
    # 查询里未编码的非 ASCII
    ("http://example.com/?q=页面", "http://example.com/?q=%E9%A1%B5%E9%9D%A2"),
    # 路径里的空格与 %20
    ("http://example.com/a b", "http://example.com/a%20b"),
    # 点段解析
    ("http://example.com/a/./b/../c", "http://example.com/a/c"),
    # 空路径等于 /
    ("http://example.com", "http://example.com/"),
    # 片段忽略
    ("http://example.com/page#sec1", "http://example.com/page#sec2"),
    ("http://example.com/page#sec1", "http://example.com/page"),
    # utm_ 参数忽略（不分大小写）
    ("http://example.com/?a=1&utm_source=x", "http://example.com/?a=1"),
    ("http://example.com/?a=1&UTM_Medium=y", "http://example.com/?a=1"),
    # 查询参数顺序无关
    ("http://example.com/?a=1&b=2", "http://example.com/?b=2&a=1"),
    # 同名参数多个值按出现顺序比较（顺序一致则相同）
    ("http://example.com/?a=1&a=2&b=3", "http://example.com/?b=3&a=1&a=2"),
    # 去掉 utm_ 后剩下的空查询等于没有查询
    ("http://example.com/?utm_source=x", "http://example.com/"),
    ("http://example.com/?", "http://example.com/"),
    # utm_ 参数的值不同也忽略
    ("http://example.com/?a=1&utm_x=1", "http://example.com/?a=1&utm_x=2"),
]

DIFFERENT_PAIRS = [
    # http 与 https 不同
    ("http://example.com/", "https://example.com/"),
    # 有 www. 和没有 www. 不同
    ("http://www.example.com/", "http://example.com/"),
    # 路径大小写不同
    ("http://example.com/About", "http://example.com/about"),
    # 非根路径末尾的 / 有无不同
    ("http://example.com/a", "http://example.com/a/"),
    # 保留字符编码与不编码不同：%2F 与 /
    ("http://example.com/a%2Fb", "http://example.com/a/b"),
    # %3F 与 ?
    ("http://example.com/a%3Fb", "http://example.com/a?b"),
    # %26 与 &
    ("http://example.com/?a=x%26y", "http://example.com/?a=x&y"),
    # 路径里的 + 和空格不同
    ("http://example.com/a+b", "http://example.com/a%20b"),
    ("http://example.com/a+b", "http://example.com/a b"),
    # 同名参数多个值顺序不同则不同
    ("http://example.com/?a=1&a=2", "http://example.com/?a=2&a=1"),
    # 非 utm_ 参数的差异不能忽略
    ("http://example.com/?a=1", "http://example.com/?a=2"),
    ("http://example.com/?a=1&b=1", "http://example.com/?a=1&b=2"),
    # 非默认端口不同
    ("http://example.com:8080/", "http://example.com/"),
    # 不同主机
    ("http://example.com/", "http://example.net/"),
]


@pytest.mark.parametrize("a,b", SAME_PAIRS)
def test_same_urls(a, b):
    assert urls_equal(a, b), f"应判定相同: {a} vs {b}"


@pytest.mark.parametrize("a,b", DIFFERENT_PAIRS)
def test_different_urls(a, b):
    assert not urls_equal(a, b), f"应判定不同: {a} vs {b}"
