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
Code generated from Simulink using the GRT code generator contains
structs that describe the internal data structure of the model, including its
signals, parameters, inputs and outputs as well as the data types etc of those.

This Python module mirrors those structs, allowing one to introspect into a
running model as well as modify parameters.

The top-level object is the 'Model'. Upon construction it is passed an
interface which must provide a readMemory() and a writeMemory() method to read and
write data from/to memory in the running code. From the starting point, a pointer
to the ModelMappingInfo struct, the entire structure is built up

This module is written with scalability in mind. This means that as much as
possible, read access from the target is deferred until the data is actually
required. E.g. for Signals, Parameters etc only the basic data is loaded upon
model initialization; properties like name and datatype are loaded lazily once
the attributes are accessed. Furthermore, the results are cached.


"""

import struct
import typing
from .lazyloaded import LazyLoaded
from .variableinfo import VariableInfo

# This code only supports 32-bit targets. The host can be 32 or 64 bit, but ensure that "I" (which is used where
# the Mathworks C code uses 'uint32_t' or pointer, is indeed 32 bits.
assert struct.calcsize('I') == 4

class RTWCAPIObject(LazyLoaded):
    """
    Base class to parse binary data structures defined in rtw_capi.h

    Derived classes must define a _fields, _format_ and _size_ class attribute
    in the following manner:

    _fields_, _format_, _size_ = RTWCAPIObject.defineFields(
        ('address', 'I', Model.getAddress),
        ('sysnum', 'I'),
        )

    Each tuple has the following items:
    - attribute name           the data is stored as this attribute of the instance
    - struct format specifier  specifies the data type of the field
    - callable (optional)      the callable is applied on the retrieved data,
                               and the returned result is stored as the attribute
                               This is evaluated lazily, only once the attribute
                               is accessed
    - callable arguments (optional)

    The callable is called as
      callable(self.model, *callable_arguments, value)

    where value is the value retrieved from the raw data

    If the attribute name is None (used for padding) or starts with a '#'
    (used for not-yet-implemented behaviour), it is not added as an attribute
    """

    @staticmethod
    def defineFields(*definition):
        """
        Helper function to define _fields_, _format_ and _size_ in derived
        classes

        """

        # fields: copy the definition; add None for callable if not given
        fields = [(attribute, structFormat, callable or (None,))
                  for attribute, structFormat, *callable in definition]

        # format: struct.pack/unpack format
        structFormat = '<' + ''.join(f[1] for f in definition)

        # size: struct.calcsize
        size = struct.calcsize(structFormat)

        return fields, structFormat, size

    def __init__(self, model: 'Model', data: bytes):
        """
        Extract the values from data as defined in self._fields_
        and apply them as attributes of this object
        """
        self.model = model
        super().__init__()
        values = struct.unpack(self._format_, data)

        attributes = {attribute: (value, callable)
                      for (attribute, structFormat, callable), value in zip(self._fields_, values)
                      if attribute is not None and not attribute.startswith('#')
                      }

        self._setattributes_(attributes)

    def _setattributes_(self, attributes):
        """
        Apply the attributes (dict of attribute: (value, callable, *arguments)) as attributes
        of this object. If callable is not None, a lazily loaded attribute
        is created; it is only evaluated using callable once it is accessed.

        (to speed up initialization time on large models where likely only a
        small subset of all signals/parameters/etc are used)

        This method may be overridden in derived classes in order to customize
        the processing of the values extracted from the data
        """
        for attribute, (value, (callable, *args)) in attributes.items():
            if callable:
                self._setlazy(attribute, callable, self.model, *args, value)
            else:
                setattr(self, attribute, value)


class Model:
    def __init__(self, interface):
        self.interface = interface
        self.mmi = None
        self._stringCache = {}
    
    def init(self, mmiAddress: int):
        self.mmi = self.readObject(ModelMappingInfo, mmiAddress)

    def readArray(self, itemType, ptr: int, num: int) -> typing.List:
        size = struct.calcsize(itemType._format_)
        data = self.readMemory(ptr, num * size)
        return [
            itemType(self, data[offset:offset+size]) 
            for offset in range(0, num*size, size)]

    def readMemory(self, address: int, size: int) -> bytes:
        return self.interface.readMemory(address, size)
        
    def writeMemory(self, address: int, data: bytes):
        self.interface.writeMemory(address, data)
    
    def readObject(self, objType, address: int):
        data = self.readMemory(address, objType._size_)
        return objType(self, data)
    
    def readString(self, address: int, blocksize: int = 64, allowCached: bool = True) -> typing.Union[str, None]:
        """
        Read a null-terminated string
        For performance reasons, this method reads blocks of <blocksize> bytes.
        This is a trade-off between the overhead of small reads vs the overhead
        of reading too many bytes. Furthermore, reading a string at the very
        end of a memory region could result in a fault because data outside the
        memory region is accessed!
        
        Returns None if address is 0
        """
        
        # TODO: add page size argument and ensure no single block read crosses
        # a page
        
        address = int(address)
        
        if address == 0:  # NULL pointers result in None
            return None
            
        if allowCached:
            r = self._stringCache.get(address)
            if r is not None:
                return r
        
        result = b''
        nulIdx = -1
        blockAddress = address
        while nulIdx == -1:
            result += self.readMemory(blockAddress, blocksize)
            blockAddress += blocksize
            nulIdx = result.find(b'\x00')
        
        result = result[:nulIdx].decode('latin-1')    

        # Store result in cache
        self._stringCache[address] = result
        
        return result

    def transformBlockpath(self, path, cls=''):
        return path

    def readBlockpath(self, cls: str, address: int, blocksize: int = 64, allowCached: bool = True) -> typing.Union[str, None]:
        """
        Read a blockpath string.
        Blockpaths are treated separately in order to allow a derived class to modify them before further processing
        cls: the name of the class of the object of which to read the blockPath e.g. 'Signal' or 'State'
        """
        return self.transformBlockpath(self.readString(address, blocksize, allowCached), cls)

    def getAddress(self, index: int) -> int:
        """
        Given an index in the data address map, return the corresponding address
        """
        return self.mmi.dataAddrMap[index]
    
    def getDataType(self, index: int):
        """
        Given an index in the data type map, return the corresponding address
        """
        return self.mmi.static.dataTypeMap[index]


class ReadableWritable:
    """MixIn class for Signal/Parameter/State, supports reading/writing"""

    # TODO: code analysis signals problems with .dataType, .fixedPoint etc attributes which are dynamically
    # generated in the classes that derive from this MixIn class

    STRUCT_TYPES = {  # from sl_types_def.h
        0: 'd',  # SS_DOUBLE
        1: 'f',  # SS_SINGLE
        2: 'b',  # SS_INT8
        3: 'B',  # SS_UINT8
        4: 'h',  # SS_INT16
        5: 'H',  # SS_UINT16
        6: 'i',  # SS_INT32
        7: 'I',  # SS_UINT32
        8: '?',  # SS_BOOLEAN
    }

    def __call__(self, *args):
        dt = self.dataType
        
        if dt.isPointer:
            raise NotImplementedError('Pointer access not implemented')
        if dt.isComplex:
            raise NotImplementedError('Complex variable access not implemented')
        if dt.numElements>0:
            raise NotImplementedError('Structured data type access not implemented')
        if self.fixedPoint != 0:
            raise NotImplementedError('Fixed-point data type access not implemented')
        if self.dimension != 0:
            raise NotImplementedError('Array access not implemented')
            
        structtype = '<' + self.STRUCT_TYPES[dt.slDataId]
        
        assert struct.calcsize(structtype) == dt.dataSize
        
        if len(args) == 0:   # Read
            return struct.unpack(structtype, self.model.readMemory(self.address, dt.dataSize))[0]   
        elif len(args) == 1: # Write
            self.model.writeMemory(self.address, struct.pack(structtype, args[0]))
        else:
            raise ValueError('Too many arguments')

    def __invert__(self):
        """
        The ~ operator overload is 'abused' to get auxiliary data from this
        variable, consistent with the remotevariables.Variable class

        It returns a VariableInfo object

        """
        name = f'{self.blockPath}/{self.name}'
        dt = self.dataType
        return VariableInfo(name=name, address=self.address, size=dt.dataSize, dtype=self.STRUCT_TYPES[dt.slDataId])


class Readable(ReadableWritable):
    def __call__(self):
        return super().__call__()  # Do not support writing to a signal or state


class Address:
    """
    Since the addresses in dataAddrMap are only one integer, this is a light-
    weight implementation that just returns an integer instead of a custom object
    """
    _format_ = 'I'
    _size_ = struct.calcsize(_format_)

    def __new__(cls, model: Model, data: bytes) -> int:
        return struct.unpack(cls._format_, data)[0]


class CachedMap:
    """
    dataTypeMap, dimensionMap etc are arrays of fixed-sized items of a certain
    type. The size of the map is not stored so we cannot preload the entire
    map or check out-of bounds access.
    
    Since the items are accessed frequently and are static, they are cached
    to reduce read access
    """
    def __init__(self, model: Model, itemType, address: int):
        self._model = model
        self._address = address
        self._itemType = itemType
        self._itemSize = itemType._size_
        self._items = {}
        
    def __getitem__(self, index: int):
        item = self._items.get(index)
        
        if item is None:  # Not yet in the cache, read the item
            address = self._address + self._itemSize * index
            item = self._itemType(self._model, self._model.readMemory(address, self._itemSize))
            self._items[index] = item
        
        return item


class Signal(RTWCAPIObject, Readable):
    """see rtw_capi.h rtwCAPI_Signals"""
    _fields_, _format_, _size_ = RTWCAPIObject.defineFields(
        ('address', 'I', Model.getAddress),
        ('sysnum', 'I'),
        ('blockPath', 'I', Model.readBlockpath, 'Signal'),
        ('name', 'I', Model.readString),
        ('portNumber', 'H'),
        ('dataType', 'H', Model.getDataType),
        ('dimension', 'H'),
        ('fixedPoint', 'H'),
        ('sampleTime', 'B'),
        (None, '3x'),
        )

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.blockPath}/{self.name}>'


class Parameter(RTWCAPIObject, ReadableWritable):
    """see rtw_capi.h rtwCAPI_BlockParameters"""
    _fields_, _format_, _size_ = RTWCAPIObject.defineFields(
        ('address', 'I', Model.getAddress),
        ('blockPath', 'I', Model.readBlockpath, 'Parameter'),
        ('name', 'I', Model.readString),
        ('dataType', 'H', Model.getDataType),
        ('dimension', 'H'),
        ('fixedPoint', 'H'),
        (None, '2x'),
        )

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.blockPath}/{self.name}>'

        
class State(RTWCAPIObject, Readable):
    """see rtw_capi.h rtwCAPI_States"""
    _fields_, _format_, _size_ = RTWCAPIObject.defineFields(
        ('address', 'I', Model.getAddress),
        ('contStateStartIndex', 'i'),
        ('blockPath', 'I', Model.readBlockpath, 'State'),
        ('name', 'I', Model.readString),
        ('pathAlias', 'I', Model.readString),
        ('#dWork', 'H'),
        ('dataType', 'H', Model.getDataType),
        ('dimension', 'H'),
        ('fixedPoint', 'H'),
        ('sampleTime', 'B'),
        ('isContinuous', '?'),
        (None, '2s'),
        ('#hierInfo', 'i'),
        ('#flatElem', 'I'),
        )
        
    def __repr__(self):
        return f'<{self.__class__.__name__} {self.blockPath}/{self.name}>'


class DataType(RTWCAPIObject):
    """see rtw_capi.h rtwCAPI_DataTypeMap"""
    _fields_, _format_, _size_ = RTWCAPIObject.defineFields(
        ('cDataName', 'I', Model.readString),
        ('mwDataName', 'I', Model.readString),
        ('numElements', 'H'),
        ('elements', 'H'),
        ('dataSize', 'H'),
        ('slDataId', 'B'),
        ('flags', 'B'),
        ('enumStorageType', 'B'),
        (None, '3x'),
        )
        
    def _setattributes_(self, attributes):
        flags = attributes.pop('flags')[0]
        self.isComplex = bool(flags & 1)
        self.isPointer = bool(flags & 2)
        
        super()._setattributes_(attributes)
    
    def __repr__(self):
        qualifiers = ''
        if self.isPointer:
            qualifiers = '*'
        if self.isComplex:
            qualifiers += 'complex '
        
        return f'<{self.__class__.__name__} {qualifiers}{self.cDataName} / {self.mwDataName}>'


class ModelMappingStaticInfo(RTWCAPIObject):
    """see rtw_modelmap.h ModelMappingStaticInfo"""
    _fields_, _format_, _size_ = RTWCAPIObject.defineFields(
            ('ptrSignals', 'I'),
            ('numSignals', 'I'),
            ('ptrRootInputs', 'I'),
            ('numRootInputs', 'I'),
            ('ptrRootOutputs', 'I'),
            ('numRootOutputs', 'I'),
            ('ptrBlockParameters', 'I'),
            ('numBlockParameters', 'I'),
            ('ptrModelParameters', 'I'),
            ('numModelParameters', 'I'),
            ('ptrStates', 'I'),
            ('numStates', 'I'),
            ('dataTypeMap', 'I', CachedMap, DataType),
            ('#dimensionMap', 'I'),
            ('#fixPtMap', 'I'),
            ('#elementMap', 'I'),
            ('#sampleTimeMap', 'I'),
            ('#dimensionArray', 'I'),
            ('targetType', 'I', Model.readString),
            ('checksum1', 'I'),
            ('checksum2', 'I'),
            ('checksum3', 'I'),
            ('checksum4', 'I'),
            ('#logInfo', 'I'),
            ('#rtpSize', 'I'),
            ('isProtectedModel', '?'),
            )
            
    def _setattributes_(self, attributes):
        """
        For signals, root inputs, root outputs, block parameters, model parameters
        and states, the ModelMappingStaticInfo contains a ptrXxx and numXxx field.
        These are converted to lists of objects of the according type, so
        there is an xxx attribute instead of ptrXxx and numXxx.
        
        """
        arrays = [
            (name, attributes.pop('ptr' + name)[0], attributes.pop('num' + name)[0], RTWCAPIType)
            for name, RTWCAPIType in [
                ('Signals', Signal),
                ('RootInputs', Signal),
                ('RootOutputs', Signal),
                ('BlockParameters', Parameter),
                ('ModelParameters', Parameter),
                ('States', State)]
            ]
        
        # Set all other attributes
        super()._setattributes_(attributes)
        
        for name, ptr, num, RTWCAPIType in arrays:
            array = self.model.readArray(RTWCAPIType, ptr, num)
            name = name[0].lower() + name[1:]
            setattr(self, name, array)


class ModelMappingInfo(RTWCAPIObject):
    """see rtw_modelmap.h rtwCAPI_ModelMappingInfo"""
    _fields_, _format_, _size_ = RTWCAPIObject.defineFields(
        ('versionNum', 'B'),
        (None, '3s'),
        ('static', 'I', Model.readObject, ModelMappingStaticInfo),
        ('path', 'I', Model.readString),
        ('fullPath', 'I', Model.readString),
        ('dataAddrMap', 'I', CachedMap, Address),
        ('#rtwCAPI_ModelMappingInfo', 'I'),
        ('#childMMIArrayLen', 'I'),
        ('#contStateStartIndex', 'i'),
        ('#instanceLogInfo', 'I'),
        ('#vardimsAddrMap', 'I'),
        ('#rtpAddress', 'I'),
        ('#RTWLoggingPtrs', 'I'),
        )
        
    def __init__(self, model, data):
        # Check the version before parsing any other data
        versionNum = data[0]
        if versionNum != 1:
            raise ValueError(f'The ModelMappingInfo is version {versionNum} but only version 1 is supported')
        
        super().__init__(model, data)
