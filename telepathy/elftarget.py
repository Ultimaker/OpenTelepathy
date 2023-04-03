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

import struct
from elftools.elf.elffile import ELFFile
from . import remotevariables, targetinterface


class ELFTarget(targetinterface.TargetInterface):
    """
    Simulation of a target, using the memory contents defined in an ELF file

    This ELFTarget could be used for testing purposes without hardware, or for generation of static typing info
    """
    def __init__(self, filename: str):
        file = open(filename, 'rb')
        self.elf = ELFFile(file)

        self.sections = []
        for section in self.elf.iter_sections():
            if section.header.sh_flags & 3:  # ALLOC or WRITE bits set
                mem = bytearray(section.header.sh_size)
                data = section.data()
                mem[:len(data)] = data
                self.sections.append((section.header.sh_addr, mem))

        if self.elf.has_dwarf_info():
            topLevelDies = [cu.get_top_DIE() for cu in self.elf.get_dwarf_info().iter_CUs()]
            self.topLevelDies = {die.attributes['DW_AT_name'].value.decode('latin-1'): die for die in topLevelDies }
        else:
            self.topLevelDies = {}

    def _getDataView(self, address: int, size: int) -> memoryview:
        """
        Given an address and size, find the section that contains these
        Returns a memoryview of the underlying data

        The entire data must lie in one section
        """
        for start, data in self.sections:
            offset = address - start
            if 0 <= offset < len(data):
                view = memoryview(data)[offset:offset+size]
                if len(view) != size:
                    raise ValueError('part of the data falls outside the section')

                return view

        raise ValueError(f'no data at address {address:x}')

    def readMemory(self, address, size):
        return bytes(self._getDataView(address, size))

    def writeMemory(self, address, data):
        self._getDataView(address, len(data))[:] = data

    def getPrivateVariable(self, filename, name):
        try:
            file_die = self.topLevelDies[filename]
        except KeyError:
            raise ValueError(f'filename not found; these files are present: {", ".join(self.topLevelDies)}')

        for child in file_die.iter_children():
            childName = child.attributes.get('DW_AT_name')
            if childName:
                childName = childName.value.decode('latin-1')

            if childName == name:
                location = child.attributes['DW_AT_location'].value
                assert location[0] == 3  # DWARF expr_loc address
                address, = struct.unpack('L', bytes(location)[1:])
                return remotevariables.Variable(self, name, child.get_DIE_from_attribute('DW_AT_type'), address)

    def initializeDataMapInfo(self, rtModelStructPointer, capi_filename):
        # This is the Python version of xxx_InitializeDataMapInfo()
        rtModelStruct = rtModelStructPointer()
        mmi = rtModelStruct.DataMapInfo.mmi
        mmi.versionNum(1)
        mmi.staticMap(self.getPrivateVariable(capi_filename, 'mmiStatic'))
        mmi.InstanceMap.dataAddrMap(self.getPrivateVariable(capi_filename, 'rtDataAddrMap'))
        mmi.InstanceMap.vardimsAddrMap(self.getPrivateVariable(capi_filename, 'rtVarDimsAddrMap'))


