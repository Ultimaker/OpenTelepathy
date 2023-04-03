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
Use this module to easily create several live plots of signals
"""

from telepathy import simulink,  remotevariables
from telepathy.xcpclient import XcpClient
from telepathy.transport import TransportTCP
import platform
import warnings
import ctypes
import itertools
import pyqtgraph as pg
import numpy as np
import os
import datetime

class Plot(pg.PlotItem):
    def __init__(self, app):
        self._app = app
        self._traces = []
        self._colors = itertools.cycle('rgbcym')
        super().__init__()

    def addTrace(self, signal, scale=1, color=None):
        name = self._app._addSignal(signal)
        trace = self.plot([], [])
        self._traces.append((trace, name, scale))

        if color is None:
            color = next(self._colors)

        trace.setPen(color)

    def _update(self, data):
        for trace, name, scale in self._traces:

            trace.setData(data['timestamp'], data[name] * scale)
            trace.update()

class PlotWindow(pg.GraphicsLayoutWidget):
    def __init__(self, app, title=None):
        self._app = app
        self._plots = []

        # PyQtGraph GraphicsLayoutWidget code does some ugly thing that breaks overriding addPlot.
        # Need to store and restore self.addPlot to make it work
        addPlot = self.addPlot
        super().__init__()
        self.addPlot = addPlot

        if title is not None:
            self.setWindowTitle(title)

        self.show()

    def addPlot(self, row=None, col=None, rowspan=1, colspan=1):
        plot = Plot(self._app)
        self.addItem(plot, row, col, rowspan, colspan)
        self._plots.append(plot)
        return plot

    def _update(self, data):
        for plot in self._plots:
            plot._update(data)

class PlotApp:
    def __init__(self, hostname='localhost', axffile=None):
        self._t0 = None
        self._windows = []
        self._signals = []
        self._odt = None
        self._daq = None
        self._windowtitles = []  # For default save file name

        self._qtApp_already_existed = bool(pg.Qt.App.instance())
        self._qtApp = pg.mkQApp()

        self.make_dpi_aware()

        self._updateTimer = pg.QtCore.QTimer()
        self._updateTimer.timeout.connect(self._update)

        self.xcpClient = XcpClient(TransportTCP(hostname))
        self.xcpClient.connect()

        if axffile:
            self.variables = remotevariables.RemoteVariables(self.xcpClient, axffile)
        else:
            self.variables = None

        self.model = simulink.IMXRTModel(self.xcpClient)
        self.model.init()

        self.saveButton = pg.QtGui.QPushButton("Save data")
        self.saveButton.clicked.connect(self.saveDataWithGui)
        self.saveButton.show()

    @staticmethod
    def make_dpi_aware():
        """
        On Windows, setting the process as Dpi Aware is required to make the axes of the plots
        align correctly on multi-monitor setups which have different scaling

        https://github.com/pyqtgraph/pyqtgraph/issues/756#issuecomment-705930693

        """
        if platform.system() == "Windows" and int(platform.release()) >= 8:
                result = ctypes.windll.shcore.SetProcessDpiAwareness(True)
                if result != 0:
                    warnings.warn("Could not set DpiAwareness. Maybe QApplication is already created. Plots may not "
                                  "render correctly on multi-monitor setups with different scaling")
                    # If you are using an interactive IDE e.g. PyCharm with iPython with %gui qt magic, add
                    # the above code to your startup before calling the gui qt magic command

    def saveDataWithGui(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")

        defaultfilename = f'{"_".join(self._windowtitles)}_{timestamp}.npz'

        defaultpath = os.path.join(os.getcwd(), defaultfilename)
        filename, _ = pg.QtGui.QFileDialog.getSaveFileName(None, "Filename to save to", defaultpath,
                                                           "Numpy compressed file (*.npz)")

        if not filename:  # User pressed cancel
            return
        try:
            self.saveData(filename)
        except Exception as e:
            pg.QtGui.QMessageBox.critical(None, "Error saving file", str(e))

    def saveData(self, filename):
        np.savez_compressed(filename, data=self.odt.getData())

    def addPlotWindow(self, title=None):
        window = PlotWindow(self, title)
        if title:
            self._windowtitles.append(title)

        self._windows.append(window)
        return window

    def _addSignal(self, signal):
        signalInfo = ~signal
        self._signals.append(signalInfo)
        return signalInfo.name  # Return the name of the added signal; this will be the column name of the daq data

    def start(self, start_qt_eventloop = True):
        daq, = self.xcpClient.allocDaqs(1)
        odt, = daq.allocOdts(1)
        odt.setSignals(self._signals)
        daq.setMode(True, 0, 0)
        self.odt = odt
        self.daq = daq

        daq.start()

        self._updateTimer.start(40)

        if start_qt_eventloop:
            # Call QApplication.exec_ if there is no event loop running yet
            # Note: if there this is run from an IDE which has QT event loop integration, there will already be an
            # event loop running, and exec_ is not to be called as that might break the event loop integration

            if not self._qtApp_already_existed:
                self._qtApp.exec_()

    def _update(self):
        data = self.odt.getData(5000)
        if len(data):
            if self._t0 is None:
                self._t0 = data['timestamp'][0]
            data['timestamp'] -= self._t0

            for window in self._windows:
                window._update(data)

if __name__ == '__main__':
    # example: plotting nozzle temperature, setpoint, heater output and runaway check variables
    app = PlotApp()

    nozzle_ctrl = app.model.root.ctrl.Extrusion_Controller.Nozzle_Temperature_Controller_0

    win1 = app.addPlotWindow()
    plot1 = win1.addPlot()
    plot1.addTrace(nozzle_ctrl.actual)
    plot1.addTrace(nozzle_ctrl.setpoint)
    plot1.addTrace(nozzle_ctrl.output, 100)

    plot2 = win1.addPlot()
    plot2.addTrace(nozzle_ctrl.Check_thermal_runaway.minimum_temperature_derivative)
    plot2.addTrace(nozzle_ctrl.Check_thermal_runaway.measured_temperature_derivative)


    app.start()
