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
import keyword
import warnings
from . import modelmap


def makeValidIdentifier(name):
    """
    Given an (Simulink) block/signal/parameter/... name, make a valid identifier, by changing all invalid chars to _.
    If the result is a Python keyword, add an additional _
    """
    result = ''
    for char in name:
        if not (result + char).isidentifier():
            result += '_'
        else:
            result += char
    if keyword.iskeyword(result):
        result += '_'

    return result

def makeValidIdentifierPath(path):
    return '.'.join(makeValidIdentifier(part) for part in path.split('/'))

class NicePrintList(list):
    """
    Helper for model.signals / model.parameters to easily display all
    signals and parameters on the console
    """
    def __repr__(self):
        return '\n'.join(self)


class Block:
    def __init__(self, path):
        self.__path = path
        self.__children = {}

    def __setitem__(self, name, value):
        """
        Children are added via block[name] = child. This adds it to __children,
        thus allowing access via block[name] and via iteration, and additionally
        adds the name as attribute for access as block.name
        
        If required, the attribute name is mangled to make it a valid Python identifier
        """
        mangled = makeValidIdentifier(name)
        if hasattr(self, mangled):
            warnings.warn(f'{value!r} is shadowed in {self!r} and therefore inaccessible')
        else:
            self.__children[name] = value
            setattr(self, mangled, value)

    def __getitem__(self, name):
        return self.__children[name]

    def __iter__(self):
        """Iterating over a block yields its children"""
        yield from self.__children.items()

    def __str__(self):
        return self.__path

    def __repr__(self):
        return f"<Block '{self.__path}'>"


def subpaths(s):
    path = ''
    for name in s.split('/'):
        path += '/' + name
        yield path[1:], name


class Model(modelmap.Model):
    def __init__(self, interface):
        super().__init__(interface)
        self.root = Block('')

    def init(self, mmi_address: int):
        super().init(mmi_address)

        # Build a tree of all blocks in the Simulink model. The set of blockPaths of all parameters,
        # signals and states is used to build this tree
        mmi_static = self.mmi.static
        blockpaths_set = set(p.blockPath
                             for cls in (mmi_static.blockParameters, mmi_static.signals, mmi_static.states)
                             for p in cls)

        self.root = root = Block('')

        allblocks = {'': root}

        for blockpath in blockpaths_set:
            parent = root

            for subpath, nodename in subpaths(blockpath):
                node = allblocks.get(subpath)
                if node is None:
                    node = Block(subpath)
                    allblocks[subpath] = node
                    parent[nodename] = node

                parent = node

        # Add parameters, signals and states, in that order
        # Thus if a name exists both as parameter and as signal, the second will
        # not be accessible

        for param in mmi_static.blockParameters:
            allblocks[param.blockPath][param.name] = param

        for signal in mmi_static.signals:
            if signal.name and signal.blockPath:
                allblocks[signal.blockPath][signal.name] = signal

        for state in mmi_static.states:
            allblocks[state.blockPath][state.name] = state

    def transformBlockpath(self, path, cls=''):
        # All paths start with the name of the model + /. This strips that part
        path = path.partition('/')[2]
        if cls == 'Signal':
            # the API shows signals as a child of the block from which they originate, while it makes more
            # sense to have them as child from the block in which they are defined
            path = path.rpartition('/')[0]

        path = path.replace('\n', ' ')

        return path
    
    
    @staticmethod
    def __identifierlist(items):
        # Helper for signals() and parameters(): return a NicePrintList (
        # list with a __repr__ of one item per line) for all items which have
        # both a blockPath and a name set. Transform the path to the identifier
        # path as it would be used in Python code
        return NicePrintList(
            sorted(
            makeValidIdentifierPath(f'{item.blockPath}/{item.name}') 
            for item in items 
            if item.blockPath and item.name
            )
            )
    
    def signals(self):
        """
        return a list of Python identifiers for all signals in the model
        """
        return self.__identifierlist(self.mmi.static.signals)
                
    def parameters(self):
        """
        return a list of Python identifiers for all parameters in the model
        """
        return self.__identifierlist(self.mmi.static.blockParameters)       


class IMXRTModel(Model):
    # iMXRT vector table is at 0x70002000; using reserved vector 68
    #
    # in your C-code, include:
    # void* Reserved68_IRQHandler = 0;   // as a global variable
    #
    # Reserved68_IRQHandler = mdl_getModelMapInfo(); // in your initialization code
    #
    # Reserved68_IRQHandler is included in the interrupt vector table in startup_mimxrt1064.c

    VECTOR_ADDRESS = 0x70002000 + 68 * 4

    def init(self):
        def readPtr(address: int) -> int:
            return struct.unpack('<I', self.readMemory(address, 4))[0]

        # The interrupt vector contains a pointer to a pointer to the
        # ModelMappingInfo
        mmi_address = readPtr(readPtr(self.VECTOR_ADDRESS))
        super().init(mmi_address)



