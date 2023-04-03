# Copyright 2022 Ultimaker BV
#
# This file is part of Telepathy.
#
# Telepathy is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# Telepathy is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for
# more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with Telepathy. If not, see <https://www.gnu.org/licenses/>.

"""
This module allows accessing global external C-variables on the embedded target.

It uses the binary ELF file of the source code of the target to extract the addresses and types of the variables.
For this to work, the sources must be compiled with DWARF debug information (gcc -g)
"""

import struct
import itertools
import typing
from enum import IntEnum
import io
from elftools.elf.elffile import ELFFile
from .variableinfo import VariableInfo
from .targetinterface import TargetInterface


# DWARF Base types
class DW_ATE(IntEnum):
    address = 0x01
    boolean = 0x02
    complex_float = 0x03
    float = 0x04
    signed = 0x05
    signed_char = 0x06
    unsigned = 0x07
    unsigned_char = 0x08
    imaginary_float = 0x09
    packed_decimal = 0x0a
    numeric_string = 0x0b
    edited = 0x0c
    signed_fixed = 0x0d
    unsigned_fixed = 0x0e
    decimal_float = 0x0f
    UTF = 0x10
    UCS = 0x11
    ASCII = 0x12
    lo_user = 0x80
    hi_user = 0xff

# This code only supports 32-bit targets. The host can be 32 or 64 bit, but ensure that "I" (which is used where
# the Mathworks C code uses 'uint32_t' or pointer, is indeed 32 bits.
assert struct.calcsize('I') == 4


# tuple of DW_ATE.xxx format, byte_size
STRUCT_FORMATS = {
    (DW_ATE.unsigned, 1): 'B', (DW_ATE.signed, 1): 'b',
    (DW_ATE.unsigned_char, 1): 'B', (DW_ATE.signed_char, 1): 'b',
    (DW_ATE.unsigned, 2): 'H', (DW_ATE.signed, 2): 'h',
    (DW_ATE.unsigned, 4): 'I', (DW_ATE.signed, 4): 'i',
    (DW_ATE.float, 4): 'f', (DW_ATE.float, 8): 'd'
}


def skip_typedefs(die):
    while die.tag == 'DW_TAG_typedef':
        die = die.get_DIE_from_attribute('DW_AT_type')
    return die


class Variable:
    def __init__(self, interface: TargetInterface, name: str, die, address: int, arrayIndex: typing.Union[int, None] = None):
        self.__interface = interface
        self.__const = False
        self.__members = None  # None denotes not a struct; [] is a struct with no members
        self.__dimensions = []
        self.__structformat = None
        self.__name = name
        self.__pointertype = None

        die = skip_typedefs(die)

        # Strip const and volatile type attributes
        while die.tag in ('DW_TAG_const_type', 'DW_TAG_volatile_type'):
            if die.tag == 'DW_TAG_const_type':
                self.__const = True

            die = skip_typedefs(die.get_DIE_from_attribute('DW_AT_type'))

        self.__die = die
        self.__description = die.tag
        size = die.attributes.get('DW_AT_byte_size')
        if size:
            size = size.value
        self.__size = size

        if arrayIndex is not None:
            assert self.__size, 'byte_size of array member type not defined'
            address += arrayIndex * self.__size

        self.__address = address

        if die.tag in ('DW_TAG_structure_type', 'DW_TAG_union_type'):
            self.__members = self.__get_members_for_struct_or_union_die(die)

        elif die.tag == 'DW_TAG_base_type':
            encoding = die.attributes['DW_AT_encoding'].value
            bytesize = die.attributes['DW_AT_byte_size'].value
            self.__structformat = STRUCT_FORMATS[(encoding, bytesize)]
            self.__description = die.attributes['DW_AT_name'].value.decode('latin-1')
        elif die.tag == 'DW_TAG_array_type':
            for child in die.iter_children():
                assert child.tag == 'DW_TAG_subrange_type'
                self.__dimensions.append(child.attributes['DW_AT_upper_bound'].value + 1)

        elif die.tag == 'DW_TAG_pointer_type':
            # TODO: pointer size could be target-dependent
            self.__structformat = 'L'
            self.__pointertype = skip_typedefs(die.get_DIE_from_attribute('DW_AT_type')) 
        else:
            raise NotImplementedError(f'{die.tag} {name}')

        if self.__structformat is not None:
            assert struct.calcsize(self.__structformat) == self.__size


    @classmethod
    def __get_members_for_struct_or_union_die(cls, die):
        """
        For a DW_TAG_structure_type or DW_TAG_union_type, create a dictionary
        of name -> datatype, offset
        
        This is called recursively in case of anonymous structs/unions to combine
        the members of those anonymous structs/unions with the members of their
        parent
        """
        members = {}
        for child in die.iter_children():
            assert child.tag == 'DW_TAG_member'
            name = child.attributes.get('DW_AT_name')
            if name is not None:
                name = name.value.decode('latin-1')
            
            if die.tag == 'DW_TAG_structure_type':
                offset = child.attributes['DW_AT_data_member_location'].value
            else:
                offset = 0 # Union: all members overlap
                       
            child_type = skip_typedefs(child.get_DIE_from_attribute('DW_AT_type'))
            
            if name is None:
                # Child is anonymous struct/union: add its members to ours
                for membername, (membertype, memberoffset) in cls.__get_members_for_struct_or_union_die(child_type).items():
                    members[membername] = membertype, offset + memberoffset
            else:
                # Normal (named) struct/union: store the child as a member
                members[name] = child_type, offset      
        
        return members

    def __eq__(self, other):
        """
        Two variables are deemed equal if their address and size are equal
        """
        if not isinstance(other, Variable):
            return False
        vi_self = ~self
        vi_other = ~other

        return vi_self.address == vi_other.address and vi_self.size == vi_other.size

    def __invert__(self):
        """
        The ~ operator overload is 'abused' to get auxiliary data from this
        variable. This is done to prevent naming clashes with struct members.

        It returns a VariableInfo object

        """
        return VariableInfo(name=self.__name, address=self.__address, size=self.__size, dtype=self.__structformat)

    def __dir__(self):

        return super().__dir__() + ([] if self.__members is None else list(self.__members))

    def __iter__(self):
        """
        Iterating over a variable yields tuples of (name, variable) for struct and
        array variables. For arrays, name is in the form of "[i,...]"
        """
        if self.__members is not None:
            for name, (die, offset) in self.__members.items():
                try:
                    yield name, Variable(self.__interface, self.__name + '.' + name, die, self.__address + offset)
                except (KeyError, NotImplementedError):
                    pass

        elif self.__dimensions:
            dims = [range(i) for i in self.__dimensions]
            for idx in itertools.product(*dims):
                idxStr = '[' + ",".join(str(i) for i in idx) + ']'

                yield idxStr, self[idx]

        else:
            raise TypeError('Variable is not iterable')

    def __getitem__(self, index):
        """Get item from array variable"""
        if not self.__dimensions:
            raise TypeError('Variable is not an array')
        subtype = self.__die.get_DIE_from_attribute('DW_AT_type')

        if not isinstance(index, tuple):
            index = index,

        if len(index) != len(self.__dimensions):
            raise IndexError(
                f'Incorrect number of dimensions. Should be '
                f'{len(self.__dimensions)} but {len(index)} given')

        linearIndex = 0
        for idx, dimension in zip(index, self.__dimensions):
            if idx<0 or idx >= dimension:
                raise IndexError('Index out of range')

            linearIndex = (linearIndex * dimension) + idx

        idxStr = '[' + ",".join(str(i) for i in index) + ']'

        return Variable(self.__interface, self.__name + idxStr, subtype, self.__address, linearIndex)

    def __getattr__(self, attr):
        """Get a member from a struct variable"""
        if self.__members is None:
            raise TypeError('Variable has no members')
        try:
            die, offset = self.__members[attr]
        except KeyError:
            raise AttributeError(f'Variable has no member {attr}')

        return Variable(self.__interface, self.__name + '.' + attr, die, self.__address + offset)

    def __repr__(self):
        return f'<Variable {self.__name} of type {self.__description} at 0x{self.__address:x}>'

    def __call__(self, *args):
        if self.__structformat is None:
            raise RuntimeError("Don't know how to read or write this variable")

        size = struct.calcsize(self.__structformat)

        if len(args) == 0:
            # Read
            data = self.__interface.readMemory(self.__address, size)
            value = struct.unpack(self.__structformat, data)[0]
            if self.__pointertype:
                return Variable(self.__interface, '*' + self.__name, self.__pointertype, value)
            else:
                return value

        elif len(args) == 1:
            # Write
            # TODO: writing a pointer should check the datatype
            value = args[0]
            if self.__pointertype and isinstance(value, Variable):
                value = (~value).address

            data = struct.pack(self.__structformat, value)
            self.__interface.writeMemory(self.__address, data)

        else:
            raise ValueError('call accepts either 0 arguments (read) or 1 argument (write)')


class RemoteVariables:
    def __init__(self, interface, elf: typing.Union[str, io.IOBase, ELFFile], check_version=True):
        """
        elf: either a filename, an open file (io.IOBase) or elftools.ELFFile object
        """
        self.__interface = interface

        # Elf can be either an ELFFile, an open file, or a filename
        if not isinstance(elf, ELFFile):
            if not isinstance(elf, io.IOBase):
                elf = open(elf, 'rb')

            elf = ELFFile(elf)

        if check_version:
            version_section = elf.get_section_by_name('.version_info')
            version_address = version_section.header.sh_addr
            version_size = version_section.header.sh_size
            version_remote = self.__interface.readMemory(version_address, version_size)
            if version_remote != version_section.data():
                raise RuntimeError(f'AXF file version does not match the target: AXF: '
                                   f'{version_section.data()!r}, target: {version_remote!r}')

        self.__loadVariablesFromElf(elf)

    def __loadVariablesFromElf(self, elf: typing.Union[str, io.IOBase, ELFFile]):

        assert elf.has_dwarf_info()
        dwarf = elf.get_dwarf_info()

        # For all compile units (i.e. source/object files), search the children of
        # the top-level Debug Information Entries (DIEs) for variable definitions,
        # and store their data type in a dict by name. If a name exists in multiple
        # compile units, the last one encountered is used.
        self.__dtypes = dtypes = {}

        for compileUnit in dwarf.iter_CUs():
            for child in compileUnit.get_top_DIE().iter_children():
                if child.tag == 'DW_TAG_variable':
                    name = child.attributes.get('DW_AT_name')
                    if name:
                        dtype = child.get_DIE_from_attribute('DW_AT_type')
                        dtypes[name.value.decode('latin-1')] = dtype

        # Get the symboltable and find all global variables
        symbolTable = elf.get_section_by_name('.symtab')

        variables = {}
        for sym in symbolTable.iter_symbols():
            info = sym.entry['st_info']
            if info['type'] == 'STT_OBJECT' and info['bind'] =='STB_GLOBAL':
                variables[sym.name] = int(sym.entry['st_value'])

        # Sort by name
        self.__variables = dict(sorted(variables.items(), key=lambda item: item[0]))

    def __getitem__(self, name):
        var = self.__variables[name]

        if isinstance(var, int):
            # Still unresolved variable, create Variable instance for it
            dtype = self.__dtypes[name]
            var = Variable(self.__interface, name, dtype, var)
            # Save the Variable instance for next references
            self.__variables[name] = var

        return var

    def __iter__(self):
        for name in self.__variables:
            try:
                yield name, self[name]
            except (KeyError, NotImplementedError):
                pass

    def __dir__(self):
        return super().__dir__() + list(self.__variables)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f'No global variable named {name}')

    def __invert__(self):
        return self.__dtypes


