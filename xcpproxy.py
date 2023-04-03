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
This script connects the xCP protocol (e.g. Telepathy or Matlab/Simulink external mode)
USB-serial interface to a TCP/IP socket

It is basically a TCP/IP (server) to serial port and vice versa forwarder

"""

import serial
import serial.tools.list_ports
import socket
import sys
import threading
import time
import logging

log = logging.getLogger("xcpproxy")
logging.basicConfig(format="%(asctime)-15s %(levelname)-8s %(name)-15s %(message)s", level=logging.INFO)


class SerialToSocketThread(threading.Thread):
    """
    This thread is responsible for (re-)connecting the serial port, and for
    forwarding data from the serial port to the socket
    """
    def __init__(self, serialConnection: serial.Serial):
        super().__init__()
        self.ser = serialConnection
        self.socket = None
    
    def setSocket(self, socket):
        self.socket = socket
    
    def run(self):
        connected = False
        while True:
            data = b''
            try:
                # Read all data available, in a blocking way:
                # first do a blocking read of 1 byte, then read everything that is available
                data = self.ser.read(1)
                data += self.ser.read(self.ser.inWaiting())
            except IOError:
                self.ser.close()
                try:
                    self.ser.open()
                except IOError:
                    if connected:
                        log.warning('Serial port disconnected')
                        connected = False
                    time.sleep(1)
                else:
                    log.info('Serial port connected')
                    connected = True

            if data:
                try:
                    if self.socket:
                        self.socket.send(data)
                except IOError:
                    pass

def rtiostreamproxy(port):
    ser = serial.Serial()
    ser.port = port
    ser.timeout = 1
    
    conn = None
    
    th = SerialToSocketThread(ser)
    th.start()
    
    # The main thread handles accepting the TCP/IP socket and
    # data from the socket to the serial port
    while True:
    
        listensock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listensock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        listensock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listensock.bind(('0.0.0.0', 17725))
        listensock.listen()
    
        conn, addr = listensock.accept()
    
        listensock.close() # Deny any new incoming socket connections while one client is connected
    
        th.setSocket(conn)
    
        log.info('Socket connected')
        while True:
            try:
                data = conn.recv(1024)
                if not data:  # Socket closed by client
                    break
            except ConnectionResetError:
                break
    
            try:
                ser.write(data)
            except IOError:
                log.error('Error writing to serial port; closing socket')
                th.setSocket(None)
                conn.close()
                break
        log.info('Socket disconnected')


if __name__ == '__main__':
    if len(sys.argv) >= 2:
        rtiostreamproxy(sys.argv[1])
    else:
        raise ValueError('COM port must be supplied as an argument')
