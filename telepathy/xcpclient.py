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
This module implements the XCP protocol. This allows reading from and writing to target memory, and synchrounous
sampling of signals using the Data AcQuisition (DAQ) functionality.
"""


import struct
import threading
import queue
import array
from collections import namedtuple
from typing import Sequence
from enum import Enum
import numpy as np
from .variableinfo import VariableInfo
from .targetinterface import TargetInterface


class XCP_PID(Enum):
    """XCP packet ids"""
    CONNECT = 0xFF
    DISCONNECT = 0xFE

    SHORT_UPLOAD = 0xF4
    SHORT_DOWNLOAD = 0xED

    START_STOP_DAQ_LIST = 0xDE
    START_STOP_SYNCH = 0xDD
    GET_DAQ_PROCESSOR_INFO = 0xDA
    GET_DAQ_RESOLUTION_INFO = 0xD9
    SET_DAQ_PTR = 0xE2
    WRITE_DAQ = 0xE1
    SET_DAQ_LIST_MODE = 0xE0
    FREE_DAQ = 0xD6
    ALLOC_DAQ = 0xD5
    ALLOC_ODT = 0xD4
    ALLOC_ODT_ENTRY = 0xD3


class XCP_DAQ_LIST_COMMAND(Enum):
    STOP = 0x00
    START = 0x01
    SELECT = 0x02


DaqProcessorInfo = namedtuple('DaqProcessorInfo',
                              'dynamicDaqSupport prescalerSupport resumeSupport bitStimSupport '
                              'timestampSupport pidOffSupport overloadMsbSupport overloadEventSupport '
                              'maxDaq maxEventChannel minDaq daqKeyByte')


class XcpClient(TargetInterface):
    def __init__(self, transport):
        self._transport = transport
        self._txcounter = 1
        self._rxcounter = None
        self._replyQueue = queue.Queue()
        self._pidMap = {}
        self._daqs = []
        self._stopReadWorker = False
        self._readThread = None

    def cmd(self, pid: XCP_PID, payload: bytes) -> bytes:
        """
        Send an XCP command to the target and receive the accompanying reply
        """
        # Ensure replyqueue is empty
        try:
            reply = self._replyQueue.get(block=False)
        except queue.Empty:
            pass
        else:
            raise IOError(f'A reply without a command was received: {reply!r}')


        # length = payload + PID
        header = struct.pack('<HHB', len(payload) + 1, self._txcounter, pid.value)
        self._transport.write(header + payload)
        self._txcounter = (self._txcounter + 1) & 0xffff

        # All packets from the target are received by the _readWorker thread. The non-DAQ packets are
        # put into the _replyQueue; we get them from there
        try:
            pid, reply = self._replyQueue.get(timeout=1)
        except queue.Empty:
            raise TimeoutError("Did not receive a reply")

        if pid == 0xff:
            return reply
        elif pid == 0xfe:
            # Unfortunately the protocol has no way of finding out what the error was
            raise IOError('Received telepathy Error response')
        else:
            raise IOError(f'Received unknown telepathy reply PID 0x{pid:02x}')

    def _receiveBytes(self, size) -> bytes:
        """Receive <size> bytes from the transport"""
        received = b''
        while len(received) < size:
            data = self._transport.read(size - len(received))
            if self._stopReadWorker:
                raise EOFError
            received += data
        return received

    def _receivePacket(self):
        """Receive a packet from the transport"""
        header = self._receiveBytes(4)
        length, rxcounter = struct.unpack('<HH', header)
        if self._rxcounter is None:
            self._rxcounter = rxcounter
        assert rxcounter == self._rxcounter
        assert length >= 1
        self._rxcounter = (self._rxcounter + 1) & 0xffff
        data = self._receiveBytes(length)
        pid = data[0]
        return pid, data[1:]

    def connect(self) -> None:
        self._transport.connect()

        self._stopReadWorker = False
        self._readThread = threading.Thread(target=self._readWorker)
        self._readThread.start()

        try:
            reply = self.cmd(XCP_PID.CONNECT, b'\x00')  # connect normal mode
        except TimeoutError as e:
            raise TimeoutError(f'{e}. Try restarting xcpproxy.py')

        assert reply == b'\x05\x00\xff\xfc\xff\x01\x01'  # TODO

    def disconnect(self):
        # TODO: test re-use and test TCP transport
        self._stopReadWorker = True
        self._transport.cancel_read()
        self._readThread.join()
        self._transport.disconnect()

    def _readWorker(self):
        """
        This worker function runs in a separate thread, splitting the incoming
        packets in replies to commands (these go into the replyQueue) and
        streaming Daq data (these are handled by callbacks registered in self._pidMap).
        """

        while True:
            try:
                packet = self._receivePacket()
            except EOFError:  # Raised if _stopReadWorker is set to True
                break

            pid, data = packet
            if pid >= 0xc0:
                self._replyQueue.put(packet)
            else:
                callback = self._pidMap.get(pid)
                if callback:
                    callback(data)

    def readMemory(self, address: int, size: int) -> bytes:
        """
        Read target memory: size bytes at given address

        size<254 is done in one command; larger sizes are split into separate commands
        """

        remaining = size
        result = b''

        while remaining:
            blocksize = min(remaining, 254)  # Should be 255, but isValidUploadSize checks for size < max instead of <= max
            result += self.cmd(XCP_PID.SHORT_UPLOAD, struct.pack('<BxBL', blocksize, 0, address))
            remaining -= blocksize
            address += blocksize

        assert len(result) == size

        return result

    def writeMemory(self, address: int, data: int) -> None:
        """
        Write target memory: data to given address

        data size<254 bytes is done in one command; larger sizes are split into separate commands
        """
        while data:
            size = min(len(data), 255 - 8)
            self.cmd(XCP_PID.SHORT_DOWNLOAD, struct.pack('<BxBL', size, 0, address) + data)

            address += size
            data = data[size:]

    def getDaqProcessorInfo(self) -> DaqProcessorInfo:
        """
        Get DAQ processor info from the target
        """
        reply = self.cmd(XCP_PID.GET_DAQ_PROCESSOR_INFO, b'')
        properties, maxDaq, maxEventChannel, minDaq, daqKeyByte = struct.unpack('<BHHBB', reply)

        return DaqProcessorInfo(
            dynamicDaqSupport=bool(properties & 0x01),
            prescalerSupport=bool(properties & 0x02),
            resumeSupport=bool(properties & 0x04),
            bitStimSupport=bool(properties & 0x08),
            timestampSupport=bool(properties & 0x10),
            pidOffSupport=bool(properties & 0x20),
            overloadMsbSupport=bool(properties & 0x40),
            overloadEventSupport=bool(properties & 0x80),
            maxDaq=maxDaq,
            maxEventChannel=maxEventChannel,
            minDaq=minDaq,
            daqKeyByte=daqKeyByte)

    def allocDaqs(self, count: int):
        assert not self._daqs, 'allocDaqs called with daqs already allocated'

        assert count > 0
        if count > 1:
            raise NotImplementedError('Due to a bug in the Mathworks telepathy handler, only one DAQ is supported')

        self.cmd(XCP_PID.ALLOC_DAQ, struct.pack('<xH', count))

        self._daqs = [XcpDaq(self, i) for i in range(count)]
        return self._daqs

    def freeDaqs(self) -> None:
        self._rxcounter = None  # FREE_DAQ resets the whole protocol, so reset _rxcounter uninitialized

        # TODO: a stale DAQ packet could still cause an error related to non-sequential
        # rxcounter values
        self.cmd(XCP_PID.FREE_DAQ, b'')
        self._daqs = []


class XcpDaq:
    def __init__(self, xcpClient: XcpClient, id: int):
        self._xcpClient = xcpClient
        self._id = id
        self._timestamp = False
        self._odts = []
        self._valid = True

    def invalidate(self):
        self._valid = False
        for odt in self._odts:
            odt.invalidate()

    def setMode(self, timestamp: bool, eventId: int, priority: int):
        assert self._valid, 'DAQ deallocated'
        prescaler = 1  # Prescaler is not implemented on Mathworks telepathy implementation
        mode = 0x10 if timestamp else 0x00
        self._xcpClient.cmd(XCP_PID.SET_DAQ_LIST_MODE,
                            struct.pack('<BHHBB', mode, self._id, eventId, prescaler, priority))
        self._timestamp = timestamp

    def start(self):
        assert self._valid, 'DAQ deallocated'
        assert self._odts, 'No ODTs allocated'

        # First select the DAQ to find its firstPid, so we can assign PIDs to
        # our ODTs
        reply = self._xcpClient.cmd(XCP_PID.START_STOP_DAQ_LIST, struct.pack('<BH',XCP_DAQ_LIST_COMMAND.SELECT.value, self._id))

        # Note: there is a bug in the Mathworks telepathy code that causes it to always
        # return the firstPid of the fist daq as opposed to the current daq
        # details:
        # startStopDaqListOutputPacketHandler relies on *packet containing the input
        # packet, but it is zeroed in xcpRun
        firstPid, = struct.unpack('B', reply)

        # Register this PID and the subsequent ones to our ODTs
        for pid, odt in enumerate(self._odts, firstPid):
            self._xcpClient._pidMap[pid] = odt.dataReceived

        self._xcpClient.cmd(XCP_PID.START_STOP_DAQ_LIST, struct.pack('<BH', XCP_DAQ_LIST_COMMAND.START.value, self._id))

    def stop(self):
        assert self._valid, 'DAQ deallocated'
        self._xcpClient.cmd(XCP_PID.START_STOP_DAQ_LIST, struct.pack('<BH', 0, self._id))

    def allocOdts(self, count: int):
        assert self._valid, 'DAQ deallocated'
        assert count > 0
        assert not self._odts, 'allocOdts called with ODTs already allocated'

        self._xcpClient.cmd(XCP_PID.ALLOC_ODT, struct.pack('<xHB', self._id, count))

        self._odts = [XcpOdt(self._xcpClient, self, self._id, i) for i in range(count)]
        return self._odts


class XcpOdt:
    def __init__(self, xcpClient: XcpClient, daq: XcpDaq, daqId: int, id: int):
        self._xcpClient = xcpClient
        self._daq = daq
        self._daqId = daqId
        self._id = id
        self._dtype = None
        self._valid = True
        self._callback = self.appendData
        self._data = array.array('B')

    def invalidate(self):
        self._valid = False

    def setSignals(self, signals: Sequence[VariableInfo]):
        """
        signals: sequence of (name, address, size) tuples or sequence of VariableInfo
                 (VariableInfo NamedTuple has name, address, size as first fields)
        """

        assert self._valid, 'ODT deallocated'

        num = len(signals)

        # Allocate the required number of signals
        self._xcpClient.cmd(XCP_PID.ALLOC_ODT_ENTRY, struct.pack('<xHBB', self._daqId, self._id, num))

        dtypes = []
        for i, (name, address, dtype, *rest) in enumerate(signals):
            size = np.dtype(dtype).itemsize
            # Set DAQ pointer to this entry
            self._xcpClient.cmd(XCP_PID.SET_DAQ_PTR, struct.pack('<xHBB', self._daqId, self._id, i))

            # Set the ODT entry
            bit = 0xff  # Bit access is not supported due to a bug in isValidDaqEntry
            self._xcpClient.cmd(XCP_PID.WRITE_DAQ, struct.pack('<BBBL', bit, size, 0, address))

            dtypes.append((name, dtype))

        self._dtype = dtypes

    def clearData(self):
        del self._data[:]

    def getData(self, size=None) -> np.array:
        """
        Get the 'size' last samples of DAQ data. The returned array is a record
        array with a field for each signal
        """
        assert self._valid, 'ODT deallocated'

        dtype = self.getdtype()
        if size is not None:
            size_bytes = size * dtype.itemsize
        else:
            size_bytes = len(self._data)  # even for all data, use slice to create a copy of the data

        size_bytes = min(size_bytes, len(self._data))
        size_bytes = (size_bytes // dtype.itemsize) * dtype.itemsize

        data = self._data[-size_bytes:]

        return np.frombuffer(data, dtype)

    def getdtype(self):
        dtype = self._dtype
        if self._daq._timestamp:
            dtype = [('timestamp', 'I')] + dtype

        return np.dtype(dtype)

    def setCallback(self, callback):
        """
        Set the callback function which will receive the incoming data for this ODT. Be aware that the callback
        will be called from the receiving thread of the XcpClient!
        """
        self._callback = callback

    def appendData(self, data):
        """
        This is the default callback, appending the newly received data to self._data which can be
        retrieved using getData()
        """
        self._data.frombytes(data)

    def dataReceived(self, data):
        """
        This method is called from the receive thread of xcpClient
        Call the callback function (by default it is appendData())
        """
        self._callback(data)
