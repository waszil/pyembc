import sys
import ctypes
import struct
from typing import Optional, Type, Any

__all__ = [
    "pyembc_struct",
    "ctypes"
]

_FIELDS = "__pyembc_fields__"

_CTYPES_TYPE_ATTR = '_type_'
_CTYPES_FIELDS_ATTR = '_fields_'
_CTYPES_PACK_ATTR = '_pack_'


def _check_value_for(
        field_type: Type,
        value: Any
):
    """
    Checks whether a value can be assigned to a field.

    :param field_type: type class of the field.
    :param value: value to be written
    :raises: ValueError
    """
    if hasattr(field_type, _CTYPES_TYPE_ATTR):
        # check for ctypes types, that have the _type_ attribute, containing a struct char.
        struct_char = getattr(field_type, _CTYPES_TYPE_ATTR)
        try:
            if isinstance(value, ctypes._SimpleCData):
                _value = value.value
            else:
                _value = value
            struct.pack(struct_char, _value)
        except struct.error as e:
            raise ValueError(
                f'{value} cannot be set for {field_type.__name__} ({repr(e)})!'
            ) from None
    else:
        # check for standard types
        try:
            _value = field_type(value)
        except ValueError as e:
            raise ValueError(
                f'{value} cannot be set for {field_type.__name__}! ({repr(e)})'
            ) from None
        if not isinstance(value, field_type):
            raise ValueError(
                f"Implicit casting not allowed! Value {value} is not {field_type}!"
            ) from None


_SYS_ENDIANNESS_IS_LITTLE = sys.byteorder == "little"


def _is_little_endian(obj) -> bool:
    is_swapped = hasattr(obj, "_swappedbytes_")
    if _SYS_ENDIANNESS_IS_LITTLE:
        return not is_swapped
    else:
        return is_swapped


def _is_pyembc_struct(obj: Any) -> bool:
    """
    Checks if an object/field is a pyemb_struct by checking if it has the __pyembc_fields__ attribute

    :param obj: object to check
    :return: bool
    """
    return hasattr(obj, _FIELDS)


def _short_type_name(_type: ctypes._SimpleCData) -> str:
    byte_size = struct.calcsize(_type._type_)
    bit_size = byte_size * 8
    signed = 'u' if _type._type_.isupper() else 's'
    return f"{signed}{bit_size}"


def __len_for_union(self):
    """
    Monkypatch __len__() method for ctypes.Union
    """
    # print('union magic len')
    return ctypes.sizeof(self)


def __repr_for_union(self):
    """
    Monkypatch __len__() method for ctypes.Union
    """
    _fields = getattr(self, _FIELDS)
    field_count = len(_fields)
    s = f'{self.__class__.__name__}('
    for i, (field_name, field_type) in enumerate(_fields.items()):
        _field = getattr(self, field_name)
        if _is_pyembc_struct(_field):
            s += f'{field_name}={repr(_field)}'
        else:
            s += f'{field_name}:{_short_type_name(field_type)}=0x{_field:X}'
        if i < field_count - 1:
            s += ', '
    s += ')'
    return s


def __stream_for_union(self):
    print('strem for union....')


# monkypatch ctypes.Union: it only works like this, because Union is a metaclass,
# and the method with exec/setattr does not work for it, as described here:
#   https://stackoverflow.com/questions/53563561/monkey-patching-class-derived-from-ctypes-union-doesnt-work
ctypes.Union.__len__ = __len_for_union
ctypes.Union.__repr__ = __repr_for_union
ctypes.Union.stream = __stream_for_union


def _add_method(cls, name, args, body, _globals=None, _locals=None, only_for=None):
    if only_for is not None:
        if not issubclass(cls, only_for):
            # print(f'Skipping addmethod {name} for {cls}.')
            return
    body = body.strip('\n')
    args = ','.join(args)
    code = f"def {name}({args}):\n{body}"
    # print('---------------------------------------------------')
    # print(f'           code for {name}')
    # print('---------------------------------------------------')
    # print(code)
    __locals = {}
    # default globals:
    __globals = {
        'cls': cls,
        'ctypes': ctypes,
        '_is_pyembc_struct': _is_pyembc_struct,
        '_short_type_name': _short_type_name,
        '_is_little_endian': _is_little_endian,
        'struct': struct
    }
    if _globals is not None:
        __globals.update(_globals)
    if _locals is not None:
        __locals.update(_locals)
    exec(code, __globals, __locals)
    method = __locals[name]
    # if hasattr(cls, name):
    #     print(f"  Class {cls} already has method {name} ({getattr(cls, name)})!")
    setattr(cls, name, method)


def _generate_class(cls, pack):
    cls_annotations = cls.__dict__.get('__annotations__', {})

    # set our special attribute to save fields
    setattr(cls, _FIELDS, {})
    _fields = getattr(cls, _FIELDS)

    # go through the annotations and create fields
    _ctypes_fields = []
    _first_endian = None
    for name, _type in cls_annotations.items():
        if not issubclass(_type, (ctypes._SimpleCData, ctypes.Structure, ctypes.Union, ctypes.Array)):
            raise TypeError(
                f'Invalid type for field "{name}". Only ctypes types can be used!'
            )
        if issubclass(_type, ctypes.Structure):
            if _first_endian is None:
                _first_endian = _is_little_endian(_type)
            else:
                _endian = _is_little_endian(_type)
                if _endian != _first_endian:
                    raise TypeError('Only the same endianness is supported in a Union!')
        _fields[name] = _type
        _ctypes_fields.append((name, _type))

    # set the ctypes special attributes, note, _pack_ must be set before _fields_!
    if pack is not None:
        assert isinstance(pack, int)
        setattr(cls, _CTYPES_PACK_ATTR, pack)
    setattr(cls, _CTYPES_FIELDS_ATTR, _ctypes_fields)

    # ---------------------------------------------------
    #           __init__
    # ---------------------------------------------------

    body = f"""
        fields = getattr(self, '{_FIELDS}')
        if args:
            if kwargs:
                raise TypeError('Either positional arguments, or keyword arguments must be given!')
            if len(args) == len(fields):
                for arg_val, field_name in zip(args, fields):
                    setattr(self, field_name, arg_val)
            else:
                raise TypeError('Invalid number of arguments!')
        if kwargs:
            if args:
                raise TypeError('Either positional arguments, or keyword arguments must be given!')
            if len(kwargs) == len(fields):
                for field_name in fields:
                    try:
                        arg_val = kwargs[field_name]
                    except KeyError:
                        raise TypeError(f'Keyword argument {{field_name}} not specified!')
                    setattr(self, field_name, arg_val)
            else:
                raise TypeError('Invalid number of keyword arguments!')
    """
    _add_method(
        cls=cls,
        name="__init__",
        args=('self', '*args', '**kwargs',),
        body=body,
        _globals={'_check_value_for': _check_value_for}
    )

    # # ---------------------------------------------------
    # #           __getattribute__
    # # ---------------------------------------------------
    #
    # body = f"""
    #         print(f'__getattribute__ {{name}}')
    #         #print(f'   ::: {{hasattr(self, name)}}')
    #         return object.__getattribute__(self, name)
    #     """
    # _add_method(
    #     cls=cls,
    #     name="__getattribute__",
    #     args=('self', 'name'),
    #     body=body
    # )

    # ---------------------------------------------------
    #           __len__
    # ---------------------------------------------------

    body = f"""
        # print('__len__')
        return ctypes.sizeof(self)
    """
    _add_method(
        cls=cls,
        name="__len__",
        args=('self',),
        body=body,
        only_for=ctypes.Structure
    )

    # ---------------------------------------------------
    #           stream()
    # ---------------------------------------------------

    body = f"""
        return bytes(self)
    """
    _add_method(
        cls=cls,
        name="stream",
        args=('self',),
        body=body
    )

    # ---------------------------------------------------
    #           parse()
    # ---------------------------------------------------

    body = f"""
        if not isinstance(stream, bytes):
            raise TypeError("bytes required")
        bytepos = 0
        for field_name, field_type in self.{_FIELDS}.items():
            _field = getattr(self, field_name)
            if _is_pyembc_struct(_field):
                _field.parse(stream[bytepos:])
                bytepos += len(_field)
            else:
                fmt = field_type._type_
                field_size_bytes = struct.calcsize(fmt)
                if _is_little_endian(self):
                    endianchar = '<'
                else:
                    endianchar = '>'
                field_value = struct.unpack_from(f"{{endianchar}}{{fmt}}", stream[bytepos:])[0]
                super(cls, self).__setattr__(field_name, field_value)
                bytepos += field_size_bytes
            if issubclass(self.__class__, ctypes.Union):
                # for Unions, only the 0. field has to be parsed.
                break
    """
    _add_method(
        cls=cls,
        name="parse",
        args=("self", "stream"),
        body=body
    )

    # ---------------------------------------------------
    #           __repr__
    # ---------------------------------------------------

    body = f"""
        # print('__repr__')
        field_count = len(self.{_FIELDS})
        s = f'{{cls.__name__}}('
        for i, (field_name, field_type) in enumerate(self.{_FIELDS}.items()):
            _field = getattr(self, field_name)
            if _is_pyembc_struct(_field):
                s += f'{{field_name}}={{repr(_field)}}'
            else:                
                s += f'{{field_name}}:{{_short_type_name(field_type)}}=0x{{_field:X}}'
            if i < field_count - 1:
                s += ', ' 
        s += ')'
        return s
    """
    _add_method(
        cls=cls,
        name="__repr__",
        args=('self',),
        body=body,
        only_for=ctypes.Structure
    )

    # ---------------------------------------------------
    #           __setattr__
    # ---------------------------------------------------

    body = f"""
        print(f'setting attr {{name}} to {{value}}')
        field = self.__getattribute__(name)
        field_type = self.{_FIELDS}[name]
        if _is_pyembc_struct(field):
            if not isinstance(value, field_type):
                raise TypeError(
                    f'invalid value for field "{{name}}"! Must be of type {{field_type}}!'
                )
            super(cls, self).__setattr__(name, value)
        else:
            _check_value_for(field_type, value)
            if isinstance(value, ctypes._SimpleCData):
                value = value.value
            super(cls, self).__setattr__(name, value)
    """
    _add_method(
        cls=cls,
        name="__setattr__",
        args=('self', 'name', 'value',),
        body=body,
        _globals={'_check_value_for': _check_value_for}
    )

    return cls


def pyembc_struct(
        _cls=None,
        *,
        pack: Optional[int] = None
):
    """
    Magic decorator to create a user-friendly struct class

    :param _cls: used for distinguishing between call modes (with or without parens)
    :param pack:
    :return:
    """
    def wrap(cls):
        return _generate_class(cls, pack)
    if _cls is None:
        # call with parens: @pyembc_struct(...)
        return wrap
    else:
        # call without parens: @pyembc_struct
        return wrap(_cls)


# class MagicStruct(ctypes.LittleEndianStructure):
#     _fields_ = []
#
#     def __setattr__(self, key, value):
#         pass
#
#     @property
#     def _bochar(self) -> str:
#         raise NotImplementedError
#
#     def __repr__(self):
#         s = f"{self.__class__.__name__}("
#         for i, (field_name, field_type) in enumerate(self._fields_):
#             if issubclass(field_type, MagicStruct):
#                 subfield = self.__getattribute__(field_name)
#                 _repr = repr(subfield)
#             else:
#                 field_value = self.__getattribute__(field_name)
#                 _repr = f"{field_name}=0x{field_value:X}"
#             s += _repr
#             if i < len(self._fields_) - 1:
#                 s += ", "
#         s += ")"
#         return s
#
#     def stream(self):
#         stream = b''
#         for field_name, field_type in self._fields_:
#             if issubclass(field_type, MagicStruct):
#                 subfield: MagicStruct = self.__getattribute__(field_name)
#                 stream += subfield.stream()
#             else:
#                 fmt = field_type._type_
#                 field_value = self.__getattribute__(field_name)
#                 stream += struct.pack(f"{self._bochar}{fmt}", field_value)
#         return stream
#
#     @property
#     def struct_bytesize(self) -> int:
#         size = 0
#         for field_name, field_type in self._fields_:
#             if issubclass(field_type, MagicStruct):
#                 subfield: MagicStruct = self.__getattribute__(field_name)
#                 size += subfield.struct_bytesize
#             else:
#                 size += struct.calcsize(field_type._type_)
#         return size
#
#     def parse(self, stream: bytes):
#         bytepos = 0
#         for field_name, field_type in self._fields_:
#             if issubclass(field_type, MagicStruct):
#                 subfield: MagicStruct = self.__getattribute__(field_name)
#                 subfield.parse(stream[bytepos:])
#                 bytepos += subfield.struct_bytesize
#             else:
#                 fmt = field_type._type_
#                 field_size_bytes = struct.calcsize(fmt)
#                 field_value = struct.unpack_from(f"{self._bochar}{fmt}", stream[bytepos:])[0]
#                 self.__setattr__(field_name, field_value)
#                 bytepos += field_size_bytes
#
#
# class LEStruct(MagicStruct):
#
#     @property
#     def _bochar(self) -> str:
#         return '>'
#
#
# class BEStruct(MagicStruct):
#
#     @property
#     def _bochar(self) -> str:
#         return '<'


if __name__ == '__main__':
    @pyembc_struct
    class SL(ctypes.LittleEndianStructure):
        a: ctypes.c_uint16
        b: ctypes.c_uint8
        c: ctypes.c_uint8


    @pyembc_struct
    class SB(ctypes.BigEndianStructure):
        a: ctypes.c_uint16
        b: ctypes.c_uint8
        c: ctypes.c_uint8


    @pyembc_struct
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
    print(u)

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

    @pyembc_struct
    class Inner(ctypes.Structure):
        a: ctypes.c_uint8
        b: ctypes.c_uint8


    @pyembc_struct
    class Outer(ctypes.Structure):
        first: Inner
        second: ctypes.c_uint8

    outer = Outer(first=Inner(a=1, b=2), second=3)
    print(outer)
    print(outer.stream())
    outer.parse(b'\x11\x22\x33')
    print(outer)
