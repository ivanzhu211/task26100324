"""URL 规范化：按业务规则判断两个 URL 是否指向同一资源。"""
from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

_UNRESERVED = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)
_HEX = "0123456789ABCDEF"
_DEFAULT_PORTS = {"http": 80, "https": 443}


def _normalize_percent(s: str) -> str:
    """百分号编码规范化：
    - 十六进制统一大写；
    - 非保留字符（字母数字 -._~）解码为字面字符；
    - 保留字符的编码保持编码形态（%2F 不等于 /）；
    - 未编码的非 ASCII 字符与空格转为 UTF-8 百分号编码；
    - "+" 不做特殊处理（路径里 + 与空格不同）。
    """
    out = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "%":
            hexpart = s[i + 1 : i + 3]
            if len(hexpart) == 2 and all(c in _HEX or c in _HEX.lower() for c in hexpart):
                byte = int(hexpart, 16)
                c = chr(byte)
                if c in _UNRESERVED:
                    out.append(c)
                else:
                    out.append("%" + _HEX[byte >> 4] + _HEX[byte & 0xF])
                i += 3
                continue
            # 非法的 % 按字面量编码为 %25
            out.append("%25")
            i += 1
            continue
        if ch in _UNRESERVED or ch in ":/?@!$&'()*+,;=-._~":
            # ASCII 可见字符原样保留（保留字符的字面形态保持字面）
            if ord(ch) < 128 and ch not in "%":
                out.append(ch)
                i += 1
                continue
        # 非 ASCII 字符、空格及其他字符：UTF-8 百分号编码
        for byte in ch.encode("utf-8"):
            out.append("%" + _HEX[byte >> 4] + _HEX[byte & 0xF])
        i += 1
    return "".join(out)


def _remove_dot_segments(path: str) -> str:
    """RFC 3986 点段解析。"""
    out = []
    for seg in path.split("/"):
        if seg == ".":
            continue
        if seg == "..":
            if out:
                out.pop()
            continue
        out.append(seg)
    joined = "/".join(out)
    if path.endswith(("/.", "/..")) and not joined.endswith("/"):
        joined += "/"
    return joined


def _normalize_host(host: str) -> str:
    host = host.lower().rstrip(".")
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass
    try:
        return host.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return host


def _normalize_query(query: str) -> str:
    if not query:
        return ""
    pairs = []
    for part in query.split("&"):
        if not part:
            continue
        if "=" in part:
            name, value = part.split("=", 1)
        else:
            name, value = part, ""
        name = _normalize_percent(name)
        value = _normalize_percent(value)
        if name.lower().startswith("utm_"):
            continue
        pairs.append((name, value))
    if not pairs:
        return ""
    # 参数顺序无关：按名字稳定排序，同名参数的值保持出现顺序
    pairs.sort(key=lambda p: p[0])
    return "&".join(f"{k}={v}" for k, v in pairs)


def normalize_url(url: str) -> str:
    """返回 URL 的规范化形式，规范化后字符串相等即视为同一 URL。"""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    # 片段（#...）忽略
    host = _normalize_host(parts.hostname or "")
    try:
        port = parts.port
    except ValueError:
        port = None
    if port is not None and _DEFAULT_PORTS.get(scheme) == port:
        port = None
    userinfo = ""
    if parts.username:
        userinfo = parts.username
        if parts.password:
            userinfo += ":" + parts.password
        userinfo += "@"
    netloc = userinfo + host
    if ":" in host:  # IPv6 字面量需要方括号
        netloc = userinfo + "[" + host + "]"
    if port is not None:
        netloc += f":{port}"
    path = _normalize_percent(parts.path)
    path = _remove_dot_segments(path)
    if not path:
        path = "/"
    query = _normalize_query(parts.query)
    out = f"{scheme}://{netloc}{path}" if scheme else f"//{netloc}{path}"
    if query:
        out += "?" + query
    return out


def urls_equal(a: str, b: str) -> bool:
    """判断两个 URL 是否相同。"""
    return normalize_url(a) == normalize_url(b)
