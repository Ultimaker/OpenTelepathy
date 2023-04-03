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
This module defines the target interface which allows reading from and writing to memory
"""


class TargetInterface:
    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def readMemory(self, address: int, size: int) -> bytes:
        raise NotImplementedError

    def writeMemory(self, address: int, data: bytes) -> None:
        raise NotImplementedError
