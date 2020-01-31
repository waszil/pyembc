# import time
# from dataclasses import dataclass
#
# from .pyembc import *
# import ctypes
#
#
# import construct
#
#
# NA = construct.Struct(
#     "send_mode" / construct.Struct(
#         "a" / construct.Int8ub,
#         "b" / construct.Int8ub
#     ),
#     "enable" / construct.Int8ub
# )
#
#
# @dataclass
# class Kacsa:
#     a: int
#
#
# def test_subs():
#     class Kaki(BEStruct):
#         _fields_ = [
#             ("a", ctypes.c_uint8),
#             ("b", ctypes.c_uint8)
#         ]
#
#     class PSC_BE(BEStruct):
#         _fields_ = [
#             ("send_mode", Kaki),
#             ("enable", ctypes.c_uint8)
#         ]
#
#     data = b'\x01\x02\x03\x04'
#     psc = PSC_BE()
#     psc.parse(data)
#     assert psc.send_mode.a == 1
#     assert psc.send_mode.b == 2
#     assert psc.enable == 3
#
#     assert psc.struct_bytesize == 3
#     assert psc.send_mode.struct_bytesize == 2
#
#     assert psc.stream() == data[:psc.struct_bytesize]
#
#     N = 10000
#     print(' ')
#     t0 = time.perf_counter()
#     psc = PSC_BE()
#     for i in range(N):
#         psc.parse(data)
#         newdata = psc.stream()
#         # del psc
#     t1 = time.perf_counter()
#     print('pyembc:   ', t1-t0)
#     a = t1-t0
#
#     t0 = time.perf_counter()
#     for i in range(N):
#         na = NA.parse(data)
#         newdata = NA.build(na)
#         # del na
#     t1 = time.perf_counter()
#     print('construct:', t1 - t0)
#     b = t1-t0
#
#     print('Diff factor:', max(a, b) / min(a, b))
