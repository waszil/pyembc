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
            struct.pack(struct_char, value)
        except struct.error:
            raise ValueError(
                f'{value} cannot be set for {field_type.__name__}!'
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


def _is_pyembc_struct(obj: Any) -> bool:
    """
    Checks if an object/field is a pyemb_struct by checking if it has the __pyembc_fields__ attribute

    :param obj: object to check
    :return: bool
    """
    return hasattr(obj, _FIELDS)


def _add_method(cls, name, args, body, _globals=None, _locals=None):
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
        '_is_pyembc_struct': _is_pyembc_struct
    }
    if _globals is not None:
        __globals.update(_globals)
    if _locals is not None:
        __locals.update(_locals)
    exec(code, __globals, __locals)
    method = __locals[name]
    setattr(cls, name, method)


def _generate_class(cls, pack):
    cls_annotations = cls.__dict__.get('__annotations__', {})

    # set our special attribute to save fields
    setattr(cls, _FIELDS, {})
    _fields = getattr(cls, _FIELDS)

    # go through the annotations and create fields
    _ctypes_fields = []
    for name, _type in cls_annotations.items():
        if not issubclass(_type, (ctypes._SimpleCData, ctypes.Structure, ctypes.Union, ctypes.Array)):
            raise TypeError(
                f'Invalid type for field "{name}". Only ctypes types can be used!'
            )
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
        print('__init__')
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
        for arg in args:
            print(f'arg: {{arg}}')
    """
    _add_method(
        cls=cls,
        name="__init__",
        args=('self', '*args', '**kwargs',),
        body=body,
        _globals={'_check_value_for': _check_value_for}
    )

    # ---------------------------------------------------
    #           __len__
    # ---------------------------------------------------

    body = f"""
        return ctypes.sizeof(self)
    """
    _add_method(
        cls=cls,
        name="__len__",
        args=('self',),
        body=body
    )

    # ---------------------------------------------------
    #           __repr__
    # ---------------------------------------------------

    body = f"""
        field_count = len(self.{_FIELDS})
        s = f'{{cls.__name__}}('
        for i, (field_name, field_type) in enumerate(self.{_FIELDS}.items()):
            _field = getattr(self, field_name)
            if _is_pyembc_struct(_field):
                s += f'{{field_name}}={{repr(_field)}}'
            else:                
                s += f'{{field_name}}={{_field}}'
            if i < field_count - 1:
                s += ', ' 
        s += ')'
        return s
    """
    _add_method(
        cls=cls,
        name="__repr__",
        args=('self',),
        body=body
    )

    # ---------------------------------------------------
    #           __setattr__
    # ---------------------------------------------------

    body = f"""
            print('setting attr magic', name, 'to', value)
            field = self.__getattribute__(name)
            field_type = field.__class__
            if _is_pyembc_struct(field):
                if not isinstance(value, field_type):
                    raise TypeError(
                        f'invalid value for field "{{name}}"! Must be of type {{field_type}}!'
                    )
                super(cls, self).__setattr__(name, value)
            else:
                _check_value_for(field_type, value)
                new_value = field_type(value)
                super(cls, self).__setattr__(name, new_value)
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