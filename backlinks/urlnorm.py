"""URL 规范化：按业务规则把写法不同的同一 URL 归一成同一 key。"""
from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

_UNRESERVED = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)
_PCT_RE = re.compile(r"%([0-9A-Fa-f]{2})")
_DEFAULT_PORTS = {"http": 80, "https": 443}


def _normalize_percent(text: str) -> str:
    """百分号编码归一：unreserved 解码、其余十六进制大写、
    未编码的非 ASCII 字符与空格做 UTF-8 百分号编码。"""

    def _sub(match: re.Match) -> str:
        ch = chr(int(match.group(1), 16))
        if ch in _UNRESERVED:
            return ch
        return "%" + match.group(1).upper()

    text = _PCT_RE.sub(_sub, text)
    out = []
    for ch in text:
        if ch == " " or ord(ch) > 0x7F:
            out.append("".join("%%%02X" % b for b in ch.encode("utf-8")))
        else:
            out.append(ch)
    return "".join(out)


def _remove_dot_segments(path: str) -> str:
    """RFC 3986 5.2.4 点段解析。"""
    out = []
    for seg in path.split("/"):
        if seg == ".":
            continue
        if seg == "..":
            if out:
                out.pop()
            continue
        out.append(seg)
    result = "/".join(out)
    if path.endswith(("/.", "/..")) and not result.endswith("/"):
        result += "/"
    return result


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
    params = []
    for part in query.split("&"):
        if "=" in part:
            name, _, value = part.partition("=")
            params.append((_normalize_percent(name), _normalize_percent(value), True))
        else:
            params.append((_normalize_percent(part), "", False))
    params = [p for p in params if not p[0].lower().startswith("utm_")]
    params.sort(key=lambda p: p[0])  # 稳定排序：同名参数保持原有顺序
    return "&".join(
        f"{name}={value}" if has_eq else name for name, value, has_eq in params
    )


def normalize_url(url: str) -> str:
    """返回 URL 的规范化 key。相同语义的 URL 得到相同 key。"""
    url = url.strip()
    split = urlsplit(url)  # 片段 (#...) 由解析器直接丢弃

    scheme = split.scheme.lower()

    try:
        port = split.port
    except ValueError:
        port = None
    host = _normalize_host(split.hostname or "")
    if ":" in host:  # IPv6
        host = f"[{host}]"
    if port is not None and _DEFAULT_PORTS.get(scheme) == port:
        port = None
    netloc = host if port is None else f"{host}:{port}"

    path = _normalize_percent(split.path)
    path = _remove_dot_segments(path)
    if not path:
        path = "/"

    query = _normalize_query(split.query)

    key = f"{scheme}://{netloc}{path}"
    if query:
        key += f"?{query}"
    return key


def normalize_domain(domain: str) -> str:
    """域名规范化：小写、去末尾点、IDN 转 punycode、IP 归一。"""
    return _normalize_host(domain.strip())
