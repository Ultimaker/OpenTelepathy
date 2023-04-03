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
This module facilitates logging of signals to file or to memory.

The base class, BaseLogger, is a higher-level wrapper around XcpClient DAQ
functionality, combined with TCP transport and simulink and remotevariables
variable access

MemoryLogger is a thin wrapper around xcpclient.XcpOdt memory logging

FileLogger implements streaming logged data to disk, with optional compression
It uses a custom file format which enables streaming (see logfile.py)

This module also defines SignalLogger as a sysnonym for FileLogger for
backwards compatibility of existing scripts (deprecated)
"""


from telepathy import simulink, remotevariables, logfile
from telepathy.xcpclient import XcpClient
from telepathy.transport import TransportTCP
import gzip

import datetime


class BaseLogger:
    def __init__(self, hostname='localhost', axffile=None, initmodel=True):
        """
        Base class for shared functionality of MemoryLogger and SignalLogger

        hostname [str]:   hostname or ip-address which runs the xcpproxy
        axffile [str]:    optional path to the xcf file of the binary running on the target
                          if given, self.variables is a RemoteVariables object which
                          provides access to all global C variables
        initmodel [bool]: True (default) to init the Simulink model structure
                          This takes several seconds on startup, and is required
                          to get access to self.model.root structure of Simulink blocks.
                          Alternatively, one may call self.model.init() later

        """

        self._signals = []
        self.daq = None
        self.odt = None
        self._signals_set = False

        self.xcpClient = XcpClient(TransportTCP(hostname))
        self.xcpClient.connect()

        if axffile:
            self.variables = remotevariables.RemoteVariables(self.xcpClient, axffile)
        else:
            self.variables = None

        self.model = simulink.IMXRTModel(self.xcpClient)
        if initmodel:
            self.model.init()

    def addSignal(self, signal):
        """
        Add an xcp signal to the list of signals to be logged. Once the logging
        is started for the first time, the list of signals is uploaded to the
        target and can no longer be modified
        """
        assert not self._signals_set, 'Signal added while signals were already set'
        self._signals.append(~signal)

    def setSignals(self):
        """
        Upload the list of signals that were added via addSignal to the target.
        After this, addSignal may no longer be called. setSignals is
        automatically called from start() so it is usually not necessary to call
        it yourself.
        """
        if not self._signals_set:
            self.daq, = self.xcpClient.allocDaqs(1)
            self.odt, = self.daq.allocOdts(1)
            self.odt.setSignals(self._signals)
            self.daq.setMode(True, 0, 0)
            self._signals_set = True

    def start(self):
        """
        Start a measurement. If not yet done before, list of signals to be logged
        is uploaded. After this, no more calls to addSignal are allowed
        """
        self.setSignals()
        self.daq.start()

    def stop(self):
        """
        Stop a measurement in progress
        """
        self.daq.stop()

class MemoryLogger(BaseLogger):
    """
    Logger which logs xCP signals to memory
    """
    def clearData(self):
        """
        Clear measured data
        """
        if self.odt is not None:  # If a measurement has been started at least once
            self.odt.clearData()

    def getData(self, size=None):
        """
        Get measured data. This may be called during the measurement or after
        it has been stopped.

        if size is not None, it specifies the number of samples to be returned
        (counted from the most recently measured value). If it is None, all
        samples are returned
        """
        return self.odt.getData()


class FileLogger(BaseLogger):

    # These are defined as class members so they can be overridden in derived classes
    FILEMODE = 'xb'
    FILEOPENARGS = {}

    def __init__(self, filename, hostname='localhost', axffile=None, compress=True, initmodel=True):
        """
        Logger which logs xCP signals to file (streaming), with optional compression
        It uses a custom file format which enables streaming (see logfile.py)

        filename [str]:   filename to log to. See also start() for details
        hostname [str]:   see BaseLogger
        axffile [str]:    see BaseLogger
        compress [bool]:  if True (default), gzip-compress the file (streaming)
        initmodel [bool]: see BaseLogger


        """

        self._filename = filename
        self._file = None
        self._compress = compress
        super().__init__(hostname=hostname, axffile=axffile, initmodel=initmodel)

    def start(self, filename=None):
        """
        Start the measurement

        filename [str or None]: filename to write the data to
                                if None, use filename specified in __init__
                                Any '*' caracter in filename is expanded to a ISO8601
                                timestamp in the format YYYYMMDDTHHMMSS (T=literal T)

        """
        if filename is None:
            filename = self._filename

        timestamp = datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
        filename = filename.replace('*', timestamp)

        # Set the signals to the odt, this must be done before writing the headers
        # since it is required by self.odt.getdtype()
        self.setSignals()

        if self._compress:
            self._file = gzip.open(filename, self.FILEMODE, **self.FILEOPENARGS)
        else:
            self._file = open(filename, self.FILEMODE, **self.FILEOPENARGS)

        self.writeheader(self.odt.getdtype())

        self.odt.setCallback(self.writeData)
        super().start()


    def writeheader(self, dtype):
        """
        Write the header to the file. Called from start. May be overridden in derived classes.
        """
        self._file.write(logfile.header_for_dtype(dtype))

    def stop(self):
        """
        Stop the measurement and close the file
        """
        super().stop()

        # Set a dummy callback to prevent writes to a closed file
        # (in case any data is still in the pipeline after stop())
        self.odt.setCallback(lambda x: None)

        self._file.close()

    def writeData(self, data: bytes):
        """
        Write received data to the file. May be overridden in derived classes
        """
        self._file.write(data)

# For backwards compatibility, deprecated
SignalLogger = FileLogger

