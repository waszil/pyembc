import time
from dataclasses import dataclass
import ctypes
import construct

from .pyembc import *


def test_compare_construct_benchmark():
    NA = construct.Struct(
        "send_mode" / construct.Struct(
            "a" / construct.Int8ub,
            "b" / construct.Int8ub
        ),
        "enable" / construct.Int8ub
    )

    @pyembc
    class SendMode(ctypes.BigEndianStructure):
        a: ctypes.c_ubyte
        b: ctypes.c_ubyte

    @pyembc
    class NA2(ctypes.BigEndianStructure):
        send_mode: SendMode
        enable: ctypes.c_ubyte

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


def test_basics():
    @pyembc
    class SL(ctypes.LittleEndianStructure):
        a: ctypes.c_uint16
        b: ctypes.c_uint8
        c: ctypes.c_uint8

    @pyembc
    class SB(ctypes.BigEndianStructure):
        a: ctypes.c_uint16
        b: ctypes.c_uint8
        c: ctypes.c_uint8

    @pyembc
    class U(ctypes.Union):
        sl: SL
        raw: ctypes.c_uint32

    sl = SL(a=0xFFAA, b=1, c=2)
    assert sl.a == 0xFFAA
    assert sl.b == 1
    assert sl.c == 2
    assert sl.stream() == b'\xAA\xFF\x01\x02'
    sl.a = 0x1234
    assert sl.a == 0x1234
    sl.a = 0xFFAA

    sb = SB(a=0xFFAA, b=1, c=2)
    assert sb.a == 0xFFAA
    assert sb.b == 1
    assert sb.c == 2
    assert sb.stream() == b'\xFF\xAA\x01\x02'
    sb.a = 0x1234
    assert sb.a == 0x1234
    sb.a = 0xFFAA

    u = U(sl=sl)
    assert u.raw == 0x0201FFAA
    assert u.sl.a == 0xFFAA
    assert u.sl.b == 1
    assert u.sl.c == 2
    assert u.stream() == sl.stream()

    assert len(sl) == 4
    assert len(sb) == 4
    assert len(u) == 4

    data = b'\xCC\xBB\x11\x22'
    sl.parse(data)
    assert sl.a == 0xBBCC
    assert sl.b == 0x11
    assert sl.c == 0x22
    sb.parse(data)
    assert sb.a == 0xCCBB
    assert sb.b == 0x11
    assert sb.c == 0x22

    u.parse(b'\x87\x65\x43\x21')
    assert u.sl.a == 0x6587
    assert u.sl.b == 0x43
    assert u.sl.c == 0x21

    @pyembc
    class Inner(ctypes.Structure):
        a: ctypes.c_uint8
        b: ctypes.c_uint8


    @pyembc
    class Outer(ctypes.Structure):
        first: Inner
        second: ctypes.c_uint8

    outer = Outer(first=Inner(a=1, b=2), second=3)
    assert outer.stream() == b'\x01\x02\x03'
    outer.parse(b'\x11\x22\x33')
    assert outer.first.a == 0x11
    assert outer.first.b == 0x22
    assert outer.second == 0x33

    assert len(outer) == 3

    try:
        outer.second = 0x1234
    except ValueError:
        pass

    print(' ----- ------ -----')
    print('\n'.join(outer.ccode()))
    # print(u.ccode())