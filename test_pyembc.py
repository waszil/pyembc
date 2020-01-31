import time
from dataclasses import dataclass

from .pyembc import *
import ctypes


import construct


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


@dataclass
class Kacsa:
    a: int


def test_compare_construct_benchmark():

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
