import ctypes
import struct

__all__ = [
    "MagicStruct",
    "LEStruct",
    "BEStruct"
]


def _add_method(cls, name, body):
    _body = body.strip('\n')
    code = f"def {name}(self, name, value):\n{_body}"
    _locals = {}
    _globals = {'cls': cls, 'struct': struct}
    exec(code, _globals, _locals)
    method = _locals[name]
    setattr(cls, name, method)


def nagyonmagic(cls):
    def wrap(cls):
        cls_annotations = cls.__dict__.get('__annotations__', {})

        for name, _type in cls_annotations.items():
            print(' - adding field', name, 'with type', _type)
            setattr(cls, name, _type(0))

        body = f"""
            print('setting attr magic', name, 'to', value)
            field = self.__getattribute__(name)
            field_type = field.__class__
            try:
              struct_char = field_type._type_
              struct.pack(struct_char, value)
            except struct.error as e:
              raise ValueError(f'{{value}} does not fit to {{field_type.__name__}}!')
            super(cls, self).__setattr__(name, field_type(value))
        """
        _add_method(cls, "__setattr__", body)

        return cls
    return wrap(cls)


class MagicStruct(ctypes.LittleEndianStructure):
    _fields_ = []

    def __setattr__(self, key, value):
        pass

    @property
    def _bochar(self) -> str:
        raise NotImplementedError

    def __repr__(self):
        s = f"{self.__class__.__name__}("
        for i, (field_name, field_type) in enumerate(self._fields_):
            if issubclass(field_type, MagicStruct):
                subfield = self.__getattribute__(field_name)
                _repr = repr(subfield)
            else:
                field_value = self.__getattribute__(field_name)
                _repr = f"{field_name}=0x{field_value:X}"
            s += _repr
            if i < len(self._fields_) - 1:
                s += ", "
        s += ")"
        return s

    def stream(self):
        stream = b''
        for field_name, field_type in self._fields_:
            if issubclass(field_type, MagicStruct):
                subfield: MagicStruct = self.__getattribute__(field_name)
                stream += subfield.stream()
            else:
                fmt = field_type._type_
                field_value = self.__getattribute__(field_name)
                stream += struct.pack(f"{self._bochar}{fmt}", field_value)
        return stream

    @property
    def struct_bytesize(self) -> int:
        size = 0
        for field_name, field_type in self._fields_:
            if issubclass(field_type, MagicStruct):
                subfield: MagicStruct = self.__getattribute__(field_name)
                size += subfield.struct_bytesize
            else:
                size += struct.calcsize(field_type._type_)
        return size

    def parse(self, stream: bytes):
        bytepos = 0
        for field_name, field_type in self._fields_:
            if issubclass(field_type, MagicStruct):
                subfield: MagicStruct = self.__getattribute__(field_name)
                subfield.parse(stream[bytepos:])
                bytepos += subfield.struct_bytesize
            else:
                fmt = field_type._type_
                field_size_bytes = struct.calcsize(fmt)
                field_value = struct.unpack_from(f"{self._bochar}{fmt}", stream[bytepos:])[0]
                self.__setattr__(field_name, field_value)
                bytepos += field_size_bytes


class LEStruct(MagicStruct):

    @property
    def _bochar(self) -> str:
        return '>'


class BEStruct(MagicStruct):

    @property
    def _bochar(self) -> str:
        return '<'

