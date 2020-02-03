import sys
import ctypes
import struct
from enum import Enum, auto
from typing import Type, Any, Iterable, Dict, Optional, Mapping, Union

__all__ = [
    "pyembc_struct",
    "pyembc_union",
]

# save the system's endianness
_SYS_ENDIANNESS_IS_LITTLE = sys.byteorder == "little"
#  name for holding pyembc fields and endianness
_FIELDS = "__pyembc_fields__"
_ENDIAN = "__pyembc_endian__"
# name of the field in ctypes instances that hold the struct char
_CTYPES_TYPE_ATTR = "_type_"
# name of the field in ctypes Structure/Union instances that hold the fields
_CTYPES_FIELDS_ATTR = "_fields_"
# name of the field in ctypes Structure/Union instances that hold packing value
_CTYPES_PACK_ATTR = "_pack_"
# name of the field in ctypes Structure instances that are non-native-byteorder
_CTYPES_SWAPPED_ATTR = "_swappedbytes_"


class _PyembcTarget(Enum):
    """
    Target type for pyembc class creation
    """
    STRUCT = auto()
    UNION = auto()


def _check_value_for_type(field_type: Type, value: Any):
    """
    Checks whether a value can be assigned to a field.

    :param field_type: type class of the field.
    :param value: value to be written
    :raises: ValueError
    """
    if _is_ctypes_simple_type(field_type):
        # check for ctypes types, that have the _type_ attribute, containing a struct char.
        struct_char = getattr(field_type, _CTYPES_TYPE_ATTR)
        try:
            # noinspection PyProtectedMember
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
        raise TypeError('Got non-ctypes type!')


def _is_little_endian(obj: Union[ctypes.Structure, Type[ctypes.Structure]]) -> bool:
    """
    Checks whether a Structure instance/class is little endian

    :param obj: Structure instance/class
    :return: True if little endian
    """
    is_swapped = hasattr(obj, _CTYPES_SWAPPED_ATTR)
    if _SYS_ENDIANNESS_IS_LITTLE:
        return not is_swapped
    else:
        return is_swapped


def _is_ctypes_type(_type: Type) -> bool:
    """
    Checks whether a field type is a ctypes type

    :param _type: type class to check
    :return: True if ctypes type.
    """
    # noinspection PyProtectedMember
    return issubclass(_type, (ctypes._SimpleCData, ctypes.Structure, ctypes.Union, ctypes.Array))


def _is_ctypes_simple_type(_type: Type) -> bool:
    """
    Checks whether a field type is a basic ctypes type (byte, uint, etc)

    :param _type: type class to check
    :return: True if basic ctypes type.
    """
    # noinspection PyProtectedMember
    return issubclass(_type, ctypes._SimpleCData)


def _is_pyembc_struct(instance: Any) -> bool:
    """
    Checks if an object/field is a pyembc instance by checking if it has the __pyembc_fields__ attribute

    :param instance: instance to check
    :return: True if pyembc instance
    """
    return hasattr(instance, _FIELDS)


# noinspection PyProtectedMember
def _short_type_name(_type: ctypes._SimpleCData) -> str:
    """
    Returns a short type name for a basic type, like u8, s16, etc...

    :param _type: type class
    :return: short name for the type
    """
    # noinspection PyUnresolvedReferences
    byte_size = struct.calcsize(_type._type_)
    bit_size = byte_size * 8
    # noinspection PyUnresolvedReferences
    signedness = 'u' if _type._type_.isupper() else 's'
    if isinstance(_type, (ctypes.c_float, ctypes.c_double)):
        prefix = 'f'
    else:
        prefix = signedness
    return f"{prefix}{bit_size}"


# noinspection PyProtectedMember
def _c_type_name(_type: ctypes._SimpleCData) -> str:
    """
    Returns an ANSI c type name for a basic type, like unsigned char, signed short, etc...

    :param _type: type class
    :return: c type name for the type
    """
    # noinspection PyUnresolvedReferences
    byte_size = struct.calcsize(_type._type_)
    if byte_size == 1:
        name = "char"
    elif byte_size == 2:
        name = "short"
    elif byte_size == 4:
        name = "int"
    elif byte_size == 8:
        name = "long"
    else:
        raise ValueError("invalid length")
    # noinspection PyUnresolvedReferences
    signed = "unsigned" if _type._type_.isupper() else "signed"
    return f"{signed} {name}"


def __len_for_union(self):
    """
    Monkypatch __len__() method for ctypes.Union
    """
    return ctypes.sizeof(self)


def _print_field_value(field, field_type):
    if issubclass(field_type, (ctypes.c_float, ctypes.c_double)):
        return f"{field:.6f}"
    else:
        return f"0x{field:X}"


def __repr_for_union(self):
    """
    Monkypatch __repr__() method for ctypes.Union
    """
    _fields = getattr(self, _FIELDS)
    field_count = len(_fields)
    s = f'{self.__class__.__name__}('
    for i, (field_name, field_type) in enumerate(_fields.items()):
        _field = getattr(self, field_name)
        if _is_pyembc_struct(_field):
            s += f"{field_name}={repr(_field)}"
        else:
            s += f"{field_name}:{_short_type_name(field_type)}={_print_field_value(_field, field_type)}"
        if i < field_count - 1:
            s += ", "
    s += ')'
    return s


# Monkypatch ctypes.Union: it only works like this, because Union is a metaclass,
# and the method with exec/setattr does not work for it, as described here:
#   https://stackoverflow.com/questions/53563561/monkey-patching-class-derived-from-ctypes-union-doesnt-work
# However, it only seems to be needed for __len__ and __repr__.
ctypes.Union.__len__ = __len_for_union
ctypes.Union.__repr__ = __repr_for_union


def _add_method(
        cls: Type,
        name: str,
        args: Iterable[str],
        body: str,
        return_type: Any,
        docstring="",
        _globals: Optional[Dict[str, Any]] = None,
        _locals: Optional[Mapping] = None
):
    """
    Magic for adding methods dynamically to a class. Yes, it uses exec(). I know. Sorry about that.

    :param cls: class to extend
    :param name: name of the method to add
    :param args: arguments of the method
    :param body: body code of the method
    :param return_type: return type of the method
    :param docstring: optional docstring for the method
    :param _globals: globals for the method
    :param _locals: locals for the method
    """
    # default locals
    __locals = dict()
    __locals["_return_type"] = return_type
    return_annotation = "->_return_type"
    # default globals:
    __globals = {
        "cls": cls,
        "ctypes": ctypes,
        "struct": struct,
        "_is_pyembc_struct": _is_pyembc_struct,
        "_short_type_name": _short_type_name,
        "_c_type_name": _c_type_name,
        "_is_little_endian": _is_little_endian,
        "_check_value_for_type": _check_value_for_type,
        "_print_field_value": _print_field_value
    }
    # update globals and locals
    if _globals is not None:
        __globals.update(_globals)
    if _locals is not None:
        __locals.update(_locals)
    # final code
    args = ','.join(args)
    code = f"def {name}({args}){return_annotation}:\n{body}"
    # execute it and save to the class
    exec(code, __globals, __locals)
    method = __locals[name]
    method.__doc__ = docstring
    setattr(cls, name, method)


def _generate_class(_cls, target: _PyembcTarget, endian=sys.byteorder, pack=4):
    """
    Generates a new class based on the decorated one that we gen in the _cls parameter.
    Adds methods, sets bases, etc.

    :param _cls: class to work on
    :param target: union/struct
    :param endian: endianness for structures. Default is the system's byteorder.
    :param pack: packing for structures
    :return: generated class
    """
    # get the original class' annotations, we will parse these and generate the fields from these.
    cls_annotations = _cls.__dict__.get('__annotations__', {})

    # ctypes currently does not implement the BigEndianUnion and LittleEndianUnion despite its documentation
    # sais so. Therefore, we use simple Union for now. Details:
    # https://stackoverflow.com/questions/49524952/bigendianunion-is-not-part-of-pythons-ctypes
    # https://bugs.python.org/issue33178
    if endian == "little":
        _bases = {
            _PyembcTarget.STRUCT: ctypes.LittleEndianStructure,
            _PyembcTarget.UNION: ctypes.Union
        }
    elif endian == "big":
        _bases = {
            _PyembcTarget.STRUCT: ctypes.BigEndianStructure,
            _PyembcTarget.UNION: ctypes.Union
        }
    else:
        raise ValueError("Invalid endianness")

    # create the new class
    cls = type(_cls.__name__, (_bases[target], ), {})

    # set our special attribute to save fields
    setattr(cls, _FIELDS, {})
    _fields = getattr(cls, _FIELDS)

    # go through the annotations and create fields
    _ctypes_fields = []
    _first_endian = None
    for field_name, field_type in cls_annotations.items():
        # noinspection PyProtectedMember
        if not issubclass(field_type, (ctypes._SimpleCData, ctypes.Structure, ctypes.Union, ctypes.Array)):
            raise TypeError(
                f'Invalid type for field "{field_name}". Only ctypes types can be used!'
            )
        if target is _PyembcTarget.UNION:
            # for unions, check if all sub-struct has the same endianness.
            if issubclass(field_type, ctypes.Structure):
                if _first_endian is None:
                    _first_endian = _is_little_endian(field_type)
                else:
                    _endian = _is_little_endian(field_type)
                    if _endian != _first_endian:
                        raise TypeError('Only the same endianness is supported in a Union!')
        # save the field to our special attribute, and also for the ctypes _fields_ attribute
        _fields[field_name] = field_type
        _ctypes_fields.append((field_name, field_type))

    # set the ctypes special attributes, note, _pack_ must be set before _fields_!
    setattr(cls, _CTYPES_PACK_ATTR, pack)
    setattr(cls, _CTYPES_FIELDS_ATTR, _ctypes_fields)
    # save the endianness to us, because union streaming/building will need this
    setattr(cls, _ENDIAN, endian)

    # Add the generated methods

    # ---------------------------------------------------
    #           __init__
    # ---------------------------------------------------
    docstring = "init method for the class"
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
        docstring=docstring,
        return_type=None
    )

    # ---------------------------------------------------
    #           __len__
    # ---------------------------------------------------
    docstring = "Gets the byte length of the structure/union"
    body = f"""
        # print('__len__')
        return ctypes.sizeof(self)
    """
    _add_method(
        cls=cls,
        name="__len__",
        args=('self',),
        body=body,
        docstring=docstring,
        return_type=int
    )

    # ---------------------------------------------------
    #           stream()
    # ---------------------------------------------------
    docstring = "gets the bytestream of the instance"
    if issubclass(cls, ctypes.Union):
        body = f"""
            if cls.__pyembc_endian__ == sys.byteorder:
                return bytes(self)
            else:
                _bytearray = bytearray(self)
                _bytearray.reverse()
                return bytes(_bytearray)
        """
    else:
        body = f"""
            return bytes(self)
        """
    _add_method(
        cls=cls,
        name="stream",
        args=('self',),
        body=body,
        docstring=docstring,
        return_type=bytes,
        _globals={"sys": sys}
    )

    # ---------------------------------------------------
    #           parse()
    # ---------------------------------------------------
    docstring = "parses the instance values from a bytestream"
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
        body=body,
        docstring=docstring,
        return_type=None
    )

    # ---------------------------------------------------
    #           ccode()
    # ---------------------------------------------------
    docstring = "Generates the c representation of the instance. Returns a list of the c code lines."
    body = f"""
        code = []
        _typename = 'struct' if issubclass(self.__class__, ctypes.Structure) else 'union'
        code.append(f"typedef {{_typename}} _tag_{{self.__class__.__name__}} {{{{")
        for field_name, field_type in self.{_FIELDS}.items():
            _field = getattr(self, field_name)
            if _is_pyembc_struct(_field):
                subcode = _field.ccode()
                code = subcode + code
                code.append(f"    {{field_type.__name__}} {{field_name}};")
            else:
                code.append(f"    {{_c_type_name(field_type)}} {{field_name}};")
        code.append(f"}}}} {{self.__class__.__name__}};")
        # for _c_type in _c_types:
        #     typedef_code.append(f"typedef {{_c_type_name(_c_type)}} {{_short_type_name(_c_type)}};")
        # typedef_code.extend(code)
        return code
    """
    _add_method(
        cls=cls,
        name="ccode",
        args=('self',),
        body=body,
        docstring=docstring,
        return_type=Iterable[str]
    )

    # ---------------------------------------------------
    #           __repr__
    # ---------------------------------------------------
    docstring = "repr method for the instance"
    body = f"""
        # print('__repr__')
        field_count = len(self.{_FIELDS})
        s = f'{{cls.__name__}}('
        for i, (field_name, field_type) in enumerate(self.{_FIELDS}.items()):
            _field = getattr(self, field_name)
            if _is_pyembc_struct(_field):
                s += f'{{field_name}}={{repr(_field)}}'
            else:                
                s += f'{{field_name}}:{{_short_type_name(field_type)}}={{_print_field_value(_field, field_type)}}'
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
        docstring=docstring,
        return_type=str
    )

    # ---------------------------------------------------
    #           __setattr__
    # ---------------------------------------------------
    docstring = "Attribute setter. Checks values."
    body = f"""
        # print(f'setting attr {{field_name}} to {{value}}')
        field = self.__getattribute__(field_name)
        field_type = self.{_FIELDS}[field_name]
        if _is_pyembc_struct(field):
            if not isinstance(value, field_type):
                raise TypeError(
                    f'invalid value for field "{{field_name}}"! Must be of type {{field_type}}!'
                )
            super(cls, self).__setattr__(field_name, value)
        else:
            _check_value_for_type(field_type, value)
            if isinstance(value, ctypes._SimpleCData):
                value = value.value
            super(cls, self).__setattr__(field_name, value)
    """
    _add_method(
        cls=cls,
        name="__setattr__",
        args=('self', 'field_name', 'value',),
        body=body,
        docstring=docstring,
        return_type=None
    )

    return cls


def pyembc_struct(_cls=None, *, endian=sys.byteorder, pack: int = 4):
    """
    Magic decorator to create a user-friendly struct class

    :param _cls: used for distinguishing between call modes (with or without parens)
    :param endian: endianness. "little" or "big"
    :param pack: packing of the fields.
    :return:
    """
    def wrap(cls):
        return _generate_class(cls, _PyembcTarget.STRUCT, endian, pack)
    if _cls is None:
        # call with parens: @pyembc_struct(...)
        return wrap
    else:
        # call without parens: @pyembc_struct
        return wrap(_cls)


def pyembc_union(_cls=None, *, endian=sys.byteorder):
    """
    Magic decorator to create a user-friendly union class

    :param _cls: used for distinguishing between call modes (with or without parens)
    :param endian: endianness. "little" or "big"
    :return: decorated class
    """
    if endian != sys.byteorder:
        raise NotImplementedError(
            f"{endian} endian byteorder is currently not supported for Unions."
            f"This is because ctypes does not implement the BigEndianUnion and LittleEndianUnion despite its "
            f"documentation says so. Details:"
            f"https://stackoverflow.com/questions/49524952/bigendianunion-is-not-part-of-pythons-ctypes, "
            f"https://bugs.python.org/issue33178"
        )

    def wrap(cls):
        return _generate_class(cls, _PyembcTarget.UNION, endian)

    if _cls is None:
        # call with parens: @pyembc_struct(...)
        return wrap
    else:
        # call without parens: @pyembc_struct
        return wrap(_cls)
