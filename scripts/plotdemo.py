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
Plotting script for live plot of nozzle heater control
"""
from telepathy.plotapp import PlotApp
from telepathy.scriptutils import parseargs

app = PlotApp(**parseargs('Live plots of measured signals', ('hostname', 'axffile')))

for title, ctrl in (
        ('Nozzle 0', app.model.root.Extrusion_Controller.Nozzle_Temperature_Controller_0),
        ('Nozzle 1', app.model.root.Extrusion_Controller.Nozzle_Temperature_Controller_1),
        ('Bed', app.model.root.Heated_Bed_Controller.Heated_bed_temperature_controller)
        ):

root = app.model.root

controller1 = root.SomeBlock.SubBlock.Controller

win = app.addPlotWindow(title)
plot1 = win.addPlot(0, 0)
plot1.addTrace(controller.setpoint)
plot1.addTrace(controller.actual)

plot2 = win.addPlot(1, 0)
plot1.addTrace(controller.output, 100)  # scaled output

app.start()
