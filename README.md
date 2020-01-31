# pyembc

Declarative library for for defining embedded C data types

## Examples

### Declaring structures

structures and unions can be declared in a similar way as with `dataclasses`:

```python
@pyembc
class Inner(ctypes.Structure):
    a: ctypes.c_uint8
    b: ctypes.c_uint8

@pyembc
class Outer(ctypes.Structure):
    first: Inner
    second: ctypes.c_uint8
```

### Setting fields

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

### Generating c code

```python
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
