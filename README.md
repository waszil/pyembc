# pyembc

Declarative library for for defining embedded C data types

## Examples

### Declaring structures / unions

structures and unions can be declared in a similar way as with `dataclasses`:

```python
from pyembc import pyembc_struct, pyembc_union
from ctypes import c_uint8

@pyembc_struct
class Inner:
    a: c_uint8
    b: c_uint8

@pyembc_struct
class Outer:
    first: Inner
    second: c_uint8
    third: c_uint8
    
@pyembc_union
class MyUnion:
    as_struct: Outer
    as_int: c_uint32
```

### Instantiating

The instances of the above declared classes can be created as shown below.

```python
# empty constructor
inner = Inner()
print(inner)
>>> Inner(a:u8=0x0, b:u8=0x0)

# constructor with default values
inner = Inner(a=1, b=2)
print(inner)
>>> Inner(a:u8=0x1, b:u8=0x2)

# value checking
inner = Inner(a=256, b=300)
>>> ValueError: 256 cannot be set for c_ubyte (error('ubyte format requires 0 <= number <= 255'))!

# embedded structures
outer = Outer()
>>> Outer(first=Inner(a:u8=0x0, b:u8=0x0), second:u8=0x0, third:u8=0x0)

outer = Outer(Inner(42, 43), 1, 2)
>>> Outer(first=Inner(a:u8=0x2A, b:u8=0x2B), second:u8=0x1, third:u8=0x2)

# creating a union instance
my_union = MyUnion()
>>> MyUnion(as_struct=Outer(first=Inner(a:u8=0x0, b:u8=0x0), second:u8=0x0, third:u8=0x0), as_int:u32=0x0)

# with defaults
my_union = MyUnion(as_struct=Outer(Inner(1,2), 3,4))
>>> MyUnion(as_struct=Outer(first=Inner(a:u8=0x1, b:u8=0x2), second:u8=0x3, third:u8=0x4), as_int:u32=0x4030201)
```

### Setting field/member values

Value setting is protected for fields:

```python
outer.second = 0x1234
>>> ValueError: 4660 cannot be set for c_ubyte (error('ubyte format requires 0 <= number <= 255'))!
```

### Parsing from binary data

```python
outer = Outer(first=Inner(a=1, b=2), second=3)
print(outer)
>>> Outer(first=Inner(a:u8=0x1, b:u8=0x2), second:u8=0x3)

outer.parse(b'\x11\x22\x33')
print(outer)
>>> Outer(first=Inner(a:u8=0x11, b:u8=0x22), second:u8=0x33)
```

### Packing of structures

The structures are by default packed to 4 bytes. This means, that empty fill bytes are added
between struct members to align them to the 4 byte boundaries.
This packing can be modified by the user.

```python
@pyembc_struct
class Inner:
    a: c_uint8
    
@pyembc_struct
class Outer:
    first: Inner
    second: c_uint32
    
outer = Outer(first=Inner(1), second = 0xFFEEDDCC)
outer.stream()
>>> b'\x01\x00\x00\x00\xcc\xdd\xee\xff'
```

If we define the outer structure as below, the fill bytes will disappear

```python
@pyembc_struct(pack=1)
class Outer:
    first: Inner
    second: c_uint32
    
outer = Outer(first=Inner(1), second = 0xFFEEDDCC)
outer.stream()
>>> b'\x01\xcc\xdd\xee\xff'
```

Note: this is true for the parse() method as well! 

### Endianness

The default endianness / byteorder is the one of the system's. (`sys.byteorder`).
However, it can be adjusted in the decorators.

```python
@pyembc_struct(endian="little")
class Little:
    a: c_uint16

little = Little(a=0xFF00)
little.stream()
>>> b'\x00\xff'

@pyembc_struct(endian="big")
class Big:
    a: c_uint16

big = Big(a=0xFF00)
big.stream()
>>> b'\xff\x00'
```

However, for now, unions only support native byteorder, as the ctypes module does not
implement the appropriate BigEndianUnion and LittleEndianUnion types.
See details:

https://stackoverflow.com/questions/49524952/bigendianunion-is-not-part-of-pythons-ctypes
https://bugs.python.org/issue33178

### Generating c code

The ANSI c representation of a structure/union can be created from the class itself
or from its instance. The `ccode()` static method returns a list of lines.

```python
print('\n'.join(Outer.ccode()))
# or
print('\n'.join(outer.ccode()))
```

```c
typedef struct _tag_Inner {
    unsigned char a;
    unsigned char b;
} Inner;
typedef struct _tag_Outer {
    Inner first;
    unsigned char second;
} Outer;
```
