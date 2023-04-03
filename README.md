Telepathy
=========

Telepathy allows looking into the brains of your machine. It connects to
an embedded target, and allows reading and writing its global variables. For
embedded targets running a Simulink model, it exposes the model structure, giving
access to all parameters, signals and states. Furthermore, Telepathy enables
real-time tracing of variables or signals on your target.


## Getting Started

The power of Telepathy is best used from an interactive development environment. 
Follow either of the following getting started guides, for Spyder or PyCharm IDE:

[Spyder setup](doc/spyder_setup.md)

[Pycharm setup](doc/pycharm_setup.md)

## Implementation notes 

### C global variable access

Access to C global variables is performed by reading from and reading to the
appropriate place in target memory. The ELF linker file from the target is
used to extract the addresses and data types of the variables. This requires
the sources to be compiled with DWARF debug information (gcc -g).

C global variable access is implemented in `telepathy.remotevariables `

### Simulink model access

Access to the running Simulink model does not require the linker file of the
target code. Simulink embeds all required information on variable data types and
addresses in the target. The only thing Telepathy needs to know is the address
of the root of this information the rtwCAPI_ModelMappingInfo struct, and everything
is derived from there. 

Simulink model access is implemented in `telepathy.simulink`, supported by 
`telepathy.modelmap`

### Target interface

Both C global variable access and Simulink model access require a means to read
from and write to memory. This is done by means of a target interface, as defined
in `telepathy.targetinterface.TargetInterface`. Telepathy provides the 
[xCP](https://en.wikipedia.org/wiki/XCP_(protocol)) target interface in 
`telepathy.xcpclient`. The xCP client can communicate either over a (USB-) serial
port or over a TCP socket. These are implemented in `telepathy.transport`.

### Signal tracing (data acquisition)

The xCP protocol allows tracing of real-time signals using its Data AcQuisition
(DAQ) features. One defines the variables to be traced, and once the data
acquisition is started, these are sampled synchronously, and streamed to the
host. This functionality is implemented in `telepathy.xcpclient.XCPClient`


## License
[LGPLv3](https://choosealicense.com/licenses/lgpl-3.0/)

+SPDX-License-Identifier: LGPL-3.0