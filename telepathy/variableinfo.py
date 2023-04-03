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
The VariableInfo namedtuple is used as a common interface between
remotevariables.Variable, modelmap.ReadableWritable and xcpClient.XcpOdt.setSignals
"""

from collections import namedtuple

# Note: xcpclient.XcpOdt.setSignals depends on the first fields to be name, address, dtype (in that order)
VariableInfo = namedtuple('VariableInfo', 'name address dtype size')
