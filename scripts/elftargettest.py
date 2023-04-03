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

# TODO: be able to generate .pyi file from a model and use those

from telepathy.elftarget import ELFTarget
from telepathy import remotevariables, simulink
from telepathy.scriptutils import parseargs

filename = parseargs('telepathy.elftarget demo', ('axffile'), need_axf=True)['axffile']


e = ELFTarget(filename)

vars = remotevariables.RemoteVariables(e, e.elf)


e.initializeDataMapInfo(vars.ctrl_M, '../simulink/ctrl_grt_rtw/ctrl_capi.c')


model = simulink.IMXRTModel(e)
model.init()

print(model.root.ctrl.EMC230x_tacho_to_RPM.RPM)
