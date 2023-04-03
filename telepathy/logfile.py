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

'''
The logfile format can be either uncompressed or gzip-compressed. In both cases,
the uncompressed contents is as follows:

- 1 line header ('\n' terminated), ascii-encoded, representation of the datatype

- followed by the raw binary data

Since the header does not encode the size of the data, this format allows appending
data without the need to update the header. readlogfile is capable of reading any
log files which are not terminated properly i.e. which contain data whose size is not an
interal multiple of the data type itemsize. Such cases may occur if the logging application
or hardware crashes during logging. Compressed files will still cause an error due to a
missing checksum, but this can be resolved using `zcat <corruptfile> | gzip > <fixedfile>`

Uncompressed files are read as a memory mapped array, which allows opening a large file
without reading it completely, only reading data once required. This feature is not
possible on compressed files as they are not random seekable.

'''

import numpy
import ast
import gzip

def header_for_dtype(dtype):
    """
    Get a dict representation of the datatype
    """

    names, formats, offsets = list(zip(*((name, dt.descr[0][1], offset) for name, (dt, offset) in dtype.fields.items())))
    dtype_as_dict = dict(names=names, formats=formats, offsets=offsets, itemsize=dtype.itemsize)

    # Verify round-trip
    assert numpy.dtype(dtype_as_dict) == dtype

    # Convert to string, multiple of 8 bytes to improve alignment of the data in the file
    # (can improve performance in case of memory mapped data reads)
    header = repr(dtype_as_dict)

    # pad to 8 bytes multiple -1
    padsize = (-(len(header) + 1) % 8)

    header += ' ' * padsize + '\n'

    assert len(header) % 8 == 0

    return header.encode('ascii')


def readheader(file):
    """
    Read and parse the header from an open file
    returns numpy.dtype object
    """
    header = ast.literal_eval(file.readline().decode('ascii'))
    print(header)
    dtype = numpy.dtype(header)
    return dtype


def readlogfile(filename):
    """
    Read a log file (either compressed or uncompressed format)
    """
    with open(filename, "rb") as file:

        magic = file.read(2)
        file.seek(0)

        if magic[0] == b'{':
            # format: repr(dtype)
            dtype = readheader(file)
            offset = file.tell()

            # handle unterminated files
            file.seek(0, 2)  # seek to end
            size = file.tell() - offset
            data = numpy.memmap(file, dtype, "r", offset=offset, shape=size // dtype.itemsize)

        elif magic == b'\x1f\x8b':  # gzip magic
            file = gzip.open(file, 'rb')  # insert gzip wrapper
            dtype = readheader(file)
            rawdata = file.read()
            data = numpy.frombuffer(rawdata, dtype, count=len(rawdata) // dtype.itemsize)

        else:
            raise IOError(f'Unrecognised file format {magic}')

        return data
