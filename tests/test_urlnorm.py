"""URL 对照表：逐对验证每条“相同 / 不同”规则。"""
import unittest

from backlinks.urlnorm import normalize_url


# (url_a, url_b) —— 按规则必须判定为相同
SAME_PAIRS = [
    # 协议和主机名不区分大小写
    ("HTTP://Example.COM/path", "http://example.com/path"),
    # http 写 80 端口跟不写一样
    ("http://example.com:80/a", "http://example.com/a"),
    # https 写 443 端口跟不写一样
    ("https://example.com:443/a", "https://example.com/a"),
    # 主机名末尾的点忽略
    ("http://example.com./a", "http://example.com/a"),
    # 国际化域名 Unicode 与 punycode 一样
    ("https://例え.テスト/a", "https://xn--r8jz45g.xn--zckzah/a"),
    # IPv6 不同写法算同一个
    (
        "http://[2001:0db8:0000:0000:0000:ff00:0042:8329]/a",
        "http://[2001:db8::ff00:42:8329]/a",
    ),
    # 百分号编码的十六进制不分大小写
    ("http://example.com/%2f%3a", "http://example.com/%2F%3A"),
    # unreserved 字符编码与不编码一样
    ("http://example.com/%7Euser/%2Dpage", "http://example.com/~user/-page"),
    ("http://example.com/%41%42%43", "http://example.com/ABC"),
    # 未编码的非 ASCII 字符与其 UTF-8 百分号编码一样
    ("http://example.com/路径", "http://example.com/%E8%B7%AF%E5%BE%84"),
    # 未编码的空格与其百分号编码一样
    ("http://example.com/a b", "http://example.com/a%20b"),
    ("http://example.com/?q=a b", "http://example.com/?q=a%20b"),
    # 路径里的 . 和 .. 段先解析掉再比较
    ("http://example.com/a/./b/../c", "http://example.com/a/c"),
    ("http://example.com/a/b/../../c", "http://example.com/c"),
    # 空路径等于 /
    ("http://example.com", "http://example.com/"),
    # 片段忽略
    ("http://example.com/a#section", "http://example.com/a"),
    ("http://example.com/a#x", "http://example.com/a#y"),
    # utm_ 开头的查询参数忽略，不分大小写
    ("http://example.com/a?utm_source=g&x=1", "http://example.com/a?x=1"),
    ("http://example.com/a?UTM_MEDIUM=c&x=1", "http://example.com/a?x=1"),
    # 查询参数顺序不影响结果
    ("http://example.com/a?x=1&y=2", "http://example.com/a?y=2&x=1"),
    # 同名参数多个值按出现顺序比较（顺序一致则相同）
    ("http://example.com/a?x=1&y=2&x=3", "http://example.com/a?x=1&y=2&x=3"),
    # 去掉 utm 参数后剩下的空查询等于没有查询
    ("http://example.com/a?utm_source=g", "http://example.com/a"),
    ("http://example.com/a?utm_source=g&", "http://example.com/a"),
]

# (url_a, url_b) —— 按规则必须判定为不同
DIFFERENT_PAIRS = [
    # http 和 https 不同
    ("http://example.com/a", "https://example.com/a"),
    # 有 www. 和没有 www. 不同
    ("http://www.example.com/a", "http://example.com/a"),
    # 路径大小写不同
    ("http://example.com/Path", "http://example.com/path"),
    # 非根路径末尾有没有 / 不同
    ("http://example.com/a", "http://example.com/a/"),
    # 保留字符编码和不编码不同
    ("http://example.com/a%2Fb", "http://example.com/a/b"),
    ("http://example.com/a%3Fb", "http://example.com/a?b"),
    ("http://example.com/?x=a%26b", "http://example.com/?x=a&b"),
    # 路径里的 + 和空格不同
    ("http://example.com/a+b", "http://example.com/a b"),
    ("http://example.com/a+b", "http://example.com/a%20b"),
    # 同名参数的多个值顺序不同则不同
    ("http://example.com/a?x=1&x=2", "http://example.com/a?x=2&x=1"),
]


class TestNormalizeUrl(unittest.TestCase):
    def test_same_pairs(self):
        for a, b in SAME_PAIRS:
            with self.subTest(a=a, b=b):
                self.assertEqual(normalize_url(a), normalize_url(b))

    def test_different_pairs(self):
        for a, b in DIFFERENT_PAIRS:
            with self.subTest(a=a, b=b):
                self.assertNotEqual(normalize_url(a), normalize_url(b))


if __name__ == "__main__":
    unittest.main()
