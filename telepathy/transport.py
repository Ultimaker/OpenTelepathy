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

import socket
import serial


class TransportTCP:
    def __init__(self, host='127.0.0.1'):
        self.sock = None
        self.host = host

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.host, 17725))
        except ConnectionRefusedError as e:
            raise ConnectionRefusedError(f'{e!s}\nCheck that xcpproxy.py is running on host {self.host} '
                                         f'and is not already connected to another client.\n'
                                         f'run systemctl restart xcpproxy on the target machine to close existing connections.')

    def disconnect(self):
        self.sock.close()

    def cancel_read(self):
        pass

    def write(self, data):
        return self.sock.send(data)

    def read(self, size):
        return self.sock.recv(size)


class TransportSerial:
    def __init__(self, port):
        self.port = port
        self.ser = None

    def connect(self):
        self.ser = serial.Serial(self.port, timeout=1)

    def disconnect(self):
        self.ser.close()

    def cancel_read(self):
        self.ser.cancel_read()

    def write(self, data):
        return self.ser.write(data)

    def read(self, data):
        return self.ser.read(data)
