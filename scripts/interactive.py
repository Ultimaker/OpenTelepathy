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
This script connects to an xCP target and allows reading signals and 
reading and writing parameters interactively

Run from within an IDE (e.g. Spyder) or python3 -i to get the Python prompt
after the script code is finished.

Run with command line argument -h (help) for more information

"""


import telepathy.remotevariables
import telepathy.scriptutils
import telepathy.xcpclient
import telepathy.transport
import telepathy.simulink


def connect(hostname, axffile):
    xcpClient = telepathy.xcpclient.XcpClient(telepathy.transport.TransportTCP(hostname))
    xcpClient.connect()

    if axffile:
        variables = telepathy.remotevariables.RemoteVariables(xcpClient, axffile)
    else:
        variables = None

    model = telepathy.simulink.IMXRTModel(xcpClient)
    model.init()
    
    return model, variables


model, variables = connect(**telepathy.scriptutils.parseargs('Interactive console', ('hostname', 'axffile')))


# Define some short-cuts to be used from the console
signals = model.signals
parameters = model.parameters
root = model.root
nan = float("nan")


print( """
Interactive xCP console

signals()                  get a list of signals of the connected model
parameters()               get a list of parameters of the connected model
root.<signal>()            read a signal value
root.<parameter>()         read a parameter value
root.<parameter>(<value>)  set a parameter value

For setting 'override' block parameters, there is the constant 'nan' which
can be used to mean 'no override'
""")