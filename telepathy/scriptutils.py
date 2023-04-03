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

import argparse


def parseargs(description, args, need_axf=False):
    parser = argparse.ArgumentParser(description=description)

    def add_argument(name, **kwargs):
        if name in args:
            parser.add_argument(name, **kwargs)

    add_argument('filename', help='filename to store the data to')
    add_argument('hostname', nargs='?', default='localhost', help='hostname to connect to')
    add_argument('axffile', nargs=(None if need_axf else '?'), default=None,
                 help='location of the .axf file containing the debug symbols for the binary on the target')

    return parser.parse_args().__dict__
