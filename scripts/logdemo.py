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
Logging script for storing data
"""
import time
from telepathy.signallogger import FileLogger
from telepathy.scriptutils import parseargs

logger = FileLogger(**parseargs('Logging of measured signals', ('filename', 'hostname', 'axffile')))

logger.addSignal(logger.model.root.SomeBlock.SubBlock.SignalName1)
logger.addSignal(logger.model.root.SomeBlock.SubBlock.SignalName2)

print("Starting XCP logging")
logger.start()

print("Press ctrl + c to finish")
try:
    while True:
        time.sleep(300)
except KeyboardInterrupt:
    print("SIGINT signal received. Stopping XCP logging")
finally:
    logger.stop()
