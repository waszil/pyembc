import time
from ctypes import c_ubyte, c_uint16, c_uint8, c_uint32, c_float, c_int8

import construct
import pytest

from pyembc.pyembc import pyembc_struct, pyembc_union


def test_compare_construct_benchmark():
    NA = construct.Struct(
        "send_mode" / construct.Struct(
            "a" / construct.Int8ub,
            "b" / construct.Int8ub
        ),
        "enable" / construct.Int8ub
    )

    @pyembc_struct
    class SendMode:
        a: c_ubyte
        b: c_ubyte

    @pyembc_struct
    class NA2:
        send_mode: SendMode
        enable: c_ubyte

    data = b'\x01\x02\x03\x04'
    N = 10000

    print(' ')
    t0 = time.perf_counter()
    for i in range(N):
        na = NA.parse(data)
        newdata = NA.build(na)
        # del na
    t1 = time.perf_counter()
    print('construct:', t1 - t0)
    a = t1-t0

    t0 = time.perf_counter()
    na2 = NA2()
    for i in range(N):
        na2.parse(data)
        newdata = na2.stream()
        # del na2
    t1 = time.perf_counter()
    print('pyembc:   ', t1 - t0)
    b = t1 - t0

    print('Diff factor:', max(a, b) / min(a, b))


@pyembc_struct(endian="little")
class SL:
    a: c_uint16
    b: c_uint8
    c: c_uint8


@pyembc_struct(endian="big")
class SB:
    a: c_uint16
    b: c_uint8
    c: c_uint8


@pyembc_union
class U:
    sl: SL
    raw: c_uint32


def test_struct_le():
    sl = SL(a=0xFFAA, b=1, c=2)
    assert sl.a == 0xFFAA
    assert sl.b == 1
    assert sl.c == 2
    assert sl.stream() == b'\xAA\xFF\x01\x02'
    sl.a = 0x1234
    assert sl.a == 0x1234
    assert len(sl) == 4


def test_struct_be():
    sb = SB(a=0xFFAA, b=1, c=2)
    assert sb.a == 0xFFAA
    assert sb.b == 1
    assert sb.c == 2
    assert sb.stream() == b'\xFF\xAA\x01\x02'
    sb.a = 0x1234
    assert sb.a == 0x1234
    assert len(sb) == 4


def test_union():
    sl = SL(a=0xFFAA, b=1, c=2)
    u = U(sl=sl)
    assert u.raw == 0x0201FFAA
    assert u.sl.a == 0xFFAA
    assert u.sl.b == 1
    assert u.sl.c == 2
    assert u.stream() == sl.stream()
    assert len(u) == 4


def test_parse_le():
    data = b'\xCC\xBB\x11\x22'
    sl = SL(a=0xFFAA, b=1, c=2)
    sl.parse(data)
    assert sl.a == 0xBBCC
    assert sl.b == 0x11
    assert sl.c == 0x22


def test_parse_be():
    data = b'\xCC\xBB\x11\x22'
    sb = SB(a=0xFFAA, b=1, c=2)
    sb.parse(data)
    assert sb.a == 0xCCBB
    assert sb.b == 0x11
    assert sb.c == 0x22


def test_parse_union():
    sl = SL(a=0xFFAA, b=1, c=2)
    u = U(sl=sl)
    u.parse(b'\x87\x65\x43\x21')
    assert u.sl.a == 0x6587
    assert u.sl.b == 0x43
    assert u.sl.c == 0x21


def parse_embedded():
    @pyembc_struct
    class Inner:
        a: c_uint8
        b: c_uint8

    @pyembc_struct
    class Outer:
        first: Inner
        second: c_uint8

    outer = Outer(first=Inner(a=1, b=2), second=3)
    assert outer.stream() == b'\x01\x02\x03'
    outer.parse(b'\x11\x22\x33')
    assert outer.first.a == 0x11
    assert outer.first.b == 0x22
    assert outer.second == 0x33

    assert len(outer) == 3

    with pytest.raises(ValueError):
        outer.second = 0x1234


def test_ccode():
    @pyembc_struct
    class S:
        a: c_uint16
        b: c_float

    s = S()
    assert S.ccode() == s.ccode()

    _ = SL.ccode()
    _ = SB.ccode()
    _ = U.ccode()


def test_bitfields():
    @pyembc_struct
    class S:
        a: (c_uint8, 2)
        b: (c_uint8, 6)

    s = S(a=3, b=63)
    assert s.stream() == b'\xFF'
    s = S(a=1, b=4)
    assert s.stream() == b'\x11'
    s.parse(b'\xff')
    assert s.a == 3
    assert s.b == 63
    s.parse(b'\x81')
    assert s.a == 1
    assert s.b == 32

    with pytest.raises(SyntaxError):
        @pyembc_struct
        class S:
            a: (c_uint8, 1)

    with pytest.raises(SyntaxError):
        @pyembc_struct
        class S:
            a: (c_uint8, 1)
            b: (c_uint8, 8)

    with pytest.raises(SyntaxError):
        @pyembc_struct
        class S:
            a: (c_uint8, 1)
            b: (c_int8, 7)
