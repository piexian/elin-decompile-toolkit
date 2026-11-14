"""BinaryCursor：Unity 序列化流读取，字符串 len32+UTF-8+align4，所有错误带偏移。"""

import struct

from .errors import ElinToolError, ExitCode


class ParseError(ElinToolError):
    """二进制表解析失败，offset 是出错位置。"""

    exit_code = ExitCode.GAME_INCOMPLETE

    def __init__(self, message: str, offset: int):
        super().__init__(f"{message} @ {offset}")
        self.offset = offset


def align4(pos: int) -> int:
    """向上对齐到 4 字节边界。"""
    return (pos + 3) & ~3


class BinaryCursor:
    """在 bytes 上按声明序读取 Unity 序列化字段。"""

    __slots__ = ("data", "p")

    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.p = pos

    def _need(self, n: int) -> None:
        if self.p + n > len(self.data):
            raise ParseError("数据提前结束", self.p)

    def align(self) -> None:
        self.p = align4(self.p)

    def int(self) -> int:
        """读取 little-endian int32。"""
        self._need(4)
        v = struct.unpack_from("<i", self.data, self.p)[0]
        self.p += 4
        return v

    def float(self) -> float:
        """读取 little-endian float32。"""
        self._need(4)
        v = struct.unpack_from("<f", self.data, self.p)[0]
        self.p += 4
        return v

    def boolean(self) -> bool:
        """读取 1 字节 bool 并对齐 4。"""
        self._need(1)
        v = self.data[self.p]
        self.p += 1
        self.align()
        return bool(v)

    def string(self, maxlen: int = 8192) -> str:
        """读取 int32 长度 + UTF-8 + 对齐 4 的字符串。"""
        p = self.p
        self._need(4)
        ln = struct.unpack_from("<i", self.data, p)[0]
        if ln < 0 or ln > maxlen or p + 4 + ln > len(self.data):
            raise ParseError(f"非法字符串长度 {ln}", p)
        try:
            s = self.data[p + 4 : p + 4 + ln].decode("utf-8")
        except UnicodeDecodeError as e:
            raise ParseError("非 UTF-8 字符串", p) from e
        self.p = align4(p + 4 + ln)
        return s

    def int_array(self, limit: int = 100000) -> list[int]:
        """读取 int32 元素数 + 元素的 int 数组。"""
        at = self.p
        n = self.int()
        if n < 0 or n > limit:
            raise ParseError(f"非法 int[] 元素数 {n}", at)
        self._need(4 * n)
        vals = list(struct.unpack_from(f"<{n}i", self.data, self.p)) if n else []
        self.p += 4 * n
        return vals

    def str_array(self, limit: int = 64) -> list[str]:
        """读取 int32 元素数 + 元素的字符串数组。"""
        at = self.p
        n = self.int()
        if n < 0 or n > limit:
            raise ParseError(f"非法 str[] 元素数 {n}", at)
        return [self.string() for _ in range(n)]
