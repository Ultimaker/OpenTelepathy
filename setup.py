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
The following packages are required for some functionality, but not for all, and therefore they are not
listed here:

pyserial    For connections over serial port
pyelftools  For connections with the c-variables (telepathy.remotevariables)
PyQt5       For the browser demo
pyqtgraph   For the DAQ graph demo

"""

from setuptools import setup, find_packages
import sys

# Default action is to install if the script is run without arguments
if len(sys.argv) <= 1:
    sys.argv.append('install')


setup(
    name='telepathy',
    version='0.1',
    description='Introspection into embedded targets, at C-level and in running Simulink models',
    packages=find_packages(),
)