# Copyright (c) 2018, DEMCON advanced mechatronics
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# 2021, R. Reilink, Ultimaker:
#
# This browser code was taken from python-ads (https://github.com/DEMCON/python-ads),
# adapted to work with Telepathy
#

from PyQt5 import QtCore, QtGui, QtWidgets


class TreeItem:
    """
    Represents a single item in the variable tree

    Stores its parent, name, and variable that it is associated to

    Children can be requested using the getChildren() method; this creates the
    child TreeItem objects only when it is called for the first time and then
    caches these
    """
    def __init__(self, parent, row, name, variable):
        self.parent = parent
        self.row = row
        self.children = None
        self.name = name
        self.variable = variable

    def getChildren(self):
        if self.children is None:
            children = []
            try:
                l = list(self.variable)
            except TypeError:
                # variable is a simple variable (no array or struct)
                l = []
            for i, (name, var) in enumerate(l):
                children.append(TreeItem(self, i,name, var))

            self.children = children

        return self.children


class VariableModel(QtCore.QAbstractItemModel):
    """
    Tree model of an ADS variable tree fit for the QT model-view framework

    """
    def __init__(self, rootVariable):
        super().__init__()
        self.root = TreeItem(None, 0, '', rootVariable)

    def index(self, row, column, parent):
        if not parent.isValid():
            pass

        if not parent.isValid():
            parent = self.root
        else:
            parent = parent.internalPointer()

        item = parent.getChildren()[row]

        return self.createIndex(row, column, item)

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()
        item = index.internalPointer()

        if item is None:
            return QtCore.QModelIndex()

        return self.createIndex(item.row, 0, item.parent)

    def data(self, index, role):
        if not index.isValid():
            return None

        item = index.internalPointer()
        col = index.column()

        if role == QtCore.Qt.DisplayRole:
            if col == 0:
                return item.name

            elif col == 1:
                if len(item.getChildren()) == 0 and callable(item.variable):
                    try:
                        return str(item.variable())
                    except Exception:
                        return '?'
                else:
                    return ''

    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                if section < 2:
                    return ('Variable', 'Value')[section]

    def columnCount(self, parent):
        return 2

    def rowCount(self, parent):
        if not parent.isValid():
            parent = self.root
        else:
            parent = parent.internalPointer()
        return len(parent.getChildren())


class VariableBrowser(QtWidgets.QTreeView):
    def __init__(self, parent, rootVariable, updateInterval):
        """
        updateInterval: update interval [s]
        """
        super().__init__(parent)
        self.setWindowTitle('Variable browser')
        model = VariableModel(rootVariable)
        self.setModel(model)
        self.setColumnWidth(0, 400)
        self.resize(800,800)

        def update():
            # Signal all data (may) have changed
            model.dataChanged.emit(QtCore.QModelIndex(), QtCore.QModelIndex())

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(update)
        self.timer.start(int(updateInterval * 1000))


def main():
    global varsBrowser, modelBrowser, model, variables, app
    import sys
    sys.path.append('..')
    from telepathy.xcpclient import XcpClient
    from telepathy.transport import TransportTCP
    from telepathy import remotevariables, simulink
    from telepathy.scriptutils import parseargs

    args = parseargs('Embedded variable browser', ('hostname', 'axffile'))

    # Create QApplication object; keep track of whether it already existed (this is the case if the IDE
    # has QT Event loop integration, like ipython %gui qt)
    qtApp_already_existed = bool(QtWidgets.QApplication.instance())
    app = QtWidgets.QApplication([])

    xcpClient = XcpClient(TransportTCP(args['hostname']))
    xcpClient.connect()

    model = simulink.IMXRTModel(xcpClient)
    model.init()

    if args['axffile']:
        variables = remotevariables.RemoteVariables(xcpClient, args['axffile'])
        varsBrowser = VariableBrowser(None, variables, 0.1)
        varsBrowser.show()

    modelBrowser = VariableBrowser(None, model.root, 0.1)
    modelBrowser.show()

    # If the QApplication was created by us, start the event loop (this is not the case when the IDE
    # has QT Event loop integration)
    if not qtApp_already_existed:
        app.exec_()


if __name__ == '__main__':
    main()
__all__ = ['VariableBrowser']
