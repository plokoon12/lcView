#!/usr/bin/env python3

import sys
from PyQt5 import QtCore, QtGui, uic, QtWidgets
import pyqtgraph as pg
import pandas as pd
import numpy as np
from astropy import units as u
from os import system
import os
from scripts.boxcar import smooth as bcsmooth

dir_path = os.path.realpath(__file__).replace(__file__.split('/')[-1], '')
qtCreatorFile = dir_path + "lcdft.ui"  # Enter file here.
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)


class TableModel(QtCore.QAbstractTableModel):
    def __init__(self):
        super(TableModel, self).__init__()
        self.datatable = None
        self.colLabels = None

    def update(self, datain):
        # print('Updating Model')
        self.datatable = datain
        self.colLabels = datain.columns.values

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.datatable.index)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.datatable.columns.values)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        i = index.row()
        j = index.column()
        index_data = self.datatable.iloc[i][j]
        if role == QtCore.Qt.DisplayRole:
            return '{0}'.format(index_data)
        else:
            return QtCore.QVariant()

    def flags(self, index):
        return QtCore.Qt.ItemIsEnabled

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant(self.colLabels[section])
        if orientation == QtCore.Qt.Vertical and role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant("%s" % str(section + 1))
        return QtCore.QVariant()


class lcdftMain(QtGui.QMainWindow, Ui_MainWindow):

    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        pg.setConfigOptions(antialias=True)

        self.setupUi(self)

        self.populate()
        self.treeView.clicked.connect(self.onClicked)

        self.dir_path = os.path.realpath(__file__).replace(__file__.split('/')[-1],
                                                           '')  # path to directory where app is opened
        # Initialize pens
        self.symredpen = (240, 24, 24)
        self.symbckpen = (24, 24, 24)
        self.sympen = (240, 240, 240)
        self.symgrepen = (24, 240, 24)

        self.redpen = pg.mkPen(color=self.symredpen)
        self.bckpen = pg.mkPen(color=self.symbckpen)
        self.whipen = pg.mkPen(color=self.sympen)
        self.grepen = pg.mkPen(color=self.symgrepen)

        # Initialize variables
        self.current_point = [
            0]  # needed, because sigMouseClicked and sigMouseMoved give slighlty different values (moved is correct)
        self.time, self.flux, self.ferr = [0, 0, 0]
        self.flux_ph, self.flux_smoothed, self.phase = [0, 0, 0]
        self.freq, self.ampl = [0, 0]
        # --------------------------- Mouse position -------------------------------- #

        # Initialize plots to connect with mouse
        self.curve_lc = self.lc.plot(x=[], y=[], pen=self.bckpen)
        self.curve_ph = self.ph.plot(x=[], y=[], pen=self.bckpen)
        self.curve_dft = self.dft.plot(x=[], y=[], pen=self.bckpen)

        # Show positions of the mouse
        self.curve_lc.scene().sigMouseMoved.connect(self.onMouseMoved)
        self.curve_ph.scene().sigMouseMoved.connect(self.onMouseMoved)
        self.curve_dft.scene().sigMouseMoved.connect(self.onMouseMoved)

        # Get position from click
        self.mouse_x = 1.
        self.mouse_y = 1.
        self.curr_per = 1. / self.mouse_x
        self.curr_per_n = 1. / self.mouse_x
        self.curr_ampl = 1. / self.mouse_y
        self.curve_dft.scene().sigMouseClicked.connect(self.onMouseClicked)
        # --------------------------------------------------------------------------- #

        # ------------------------------ Graphics ----------------------------------- #
        self.file_path = 'first_run'  # path to recognize when first run
        self.max_per = 1.
        self.plot_lc()  # plot lc graph
        self.plot_ph()  # plot lc graph
        self.plot_dft()  # plot dft graph
        self.errors.stateChanged.connect(lambda: self.state_changed(True))
        self.smooth.stateChanged.connect(lambda: self.state_changed(True))
        self.curve_dft.scene().sigMouseClicked.connect(lambda: self.state_changed(True))
        self.smooth_spin.valueChanged.connect(lambda: self.state_changed(False))
        self.phase_slider.valueChanged.connect(lambda: self.state_changed(False))
        # --------------------------------------------------------------------------- #

        # -------------------- Start table with frequency data ---------------------- #
        #                                                                             #
        freq_cdf = df = pd.DataFrame(data={'Frequency': [], 'Period': []})  # Create table data
        # freq_cdf = df = pd.DataFrame(data={'Frequency': [], 'Period': [], 'Amplitude': []})  # Create table data
        self._freqtm = TableModel()  # Create table model
        self._freqtm.update(freq_cdf)
        self._freqtv = self.freq_list
        self._freqtv.setModel(self._freqtm)
        self._freqtv.horizontalHeader().setResizeMode(QtGui.QHeaderView.Stretch)
        # self._freqtv.resizeColumnsToContents()
        # self._freqtv.resizeRowsToContents()
        #                                                                             #
        # --------------------------------------------------------------------------- #

    def state_changed(self, click_flag=False):  # click_flat to know if is executed by sigMouseClick
        if click_flag is False:
            self.curr_per_n = 1. / (1. / self.curr_per + float(self.phase_slider.value()) * 1e-4)
            self.update_line()  # update vertical line with current slider
            self.show_table()  # update table values with slider
        self.phase = (self.time % self.curr_per_n) / self.curr_per_n
        try:
            temp = zip(self.phase, self.flux)
            temp = sorted(temp)
            self.phase, self.flux_ph = zip(*temp)
            self.phase = np.array(self.phase)
            self.flux_ph = np.array(self.flux_ph)
            self.flux_smoothed = bcsmooth(self.flux_ph, self.smooth_spin.value())

            err_lc = pg.ErrorBarItem(x=self.time, y=self.flux, height=self.ferr, beam=0.0,
                                     pen={'color': 'w', 'width': 0})
            err_ph = pg.ErrorBarItem(x=self.phase, y=self.flux_ph, height=self.ferr, beam=0.0,
                                     pen={'color': 'w', 'width': 0})

            if self.errors.isChecked() is True and self.smooth.isChecked() is True:
                self.lc.clear()
                self.ph.clear()

                self.lc.addItem(err_lc)
                self.ph.addItem(err_ph)

                self.lc.plot(self.time, self.flux, pen=None, symbol='o', symbolSize=2.5, symbolPen=self.sympen,
                             symbolBrush=self.sympen)
                self.ph.plot(self.phase, self.flux_ph, pen=None, symbol='o', symbolSize=2.5,
                             symbolPen=self.sympen,
                             symbolBrush=self.sympen)
                self.ph.plot(self.phase, self.flux_smoothed, pen=None, symbol='o', symbolSize=2.5,
                             symbolPen=self.symgrepen,
                             symbolBrush=self.symgrepen)
                self.lc.autoRange()
                self.ph.autoRange()

            elif self.errors.isChecked() is False and self.smooth.isChecked() is True:
                self.lc.clear()
                self.ph.clear()

                self.lc.plot(self.time, self.flux, pen=None, symbol='o', symbolSize=2.5, symbolPen=self.sympen,
                             symbolBrush=self.sympen)
                self.ph.plot(self.phase, self.flux_ph, pen=None, symbol='o', symbolSize=2.5,
                             symbolPen=self.sympen,
                             symbolBrush=self.sympen)
                self.ph.plot(self.phase, self.flux_smoothed, pen=None, symbol='o', symbolSize=2.5,
                             symbolPen=self.symgrepen,
                             symbolBrush=self.symgrepen)
                self.lc.autoRange()
                self.ph.autoRange()

            elif self.errors.isChecked() is True and self.smooth.isChecked() is False:
                self.lc.clear()
                self.ph.clear()

                self.lc.addItem(err_lc)
                self.ph.addItem(err_ph)

                self.lc.plot(self.time, self.flux, pen=None, symbol='o', symbolSize=2.5, symbolPen=self.sympen,
                             symbolBrush=self.sympen)
                self.ph.plot(self.phase, self.flux_ph, pen=None, symbol='o', symbolSize=2.5, symbolPen=self.sympen,
                             symbolBrush=self.sympen)
                self.lc.autoRange()
                self.ph.autoRange()

            elif self.errors.isChecked() is False and self.smooth.isChecked() is False:
                self.lc.clear()
                self.ph.clear()
                self.lc.plot(self.time, self.flux, pen=None, symbol='o', symbolSize=2.5, symbolPen=self.sympen,
                             symbolBrush=self.sympen)
                self.ph.plot(self.phase, self.flux_ph, pen=None, symbol='o', symbolSize=2.5, symbolPen=self.sympen,
                             symbolBrush=self.sympen)
                self.lc.autoRange()
                self.ph.autoRange()
        except TypeError:
            print("ERROR: Probably file is not loaded.")

    def show_table(self):
        freq_cdf = df = pd.DataFrame(
            data={'Frequency': [1. / self.curr_per_n], 'Period': [self.curr_per_n]}).round(
            5)  # Create table data
        # freq_cdf = df = pd.DataFrame(
        #     data={'Frequency': [1./self.curr_per], 'Period': [self.curr_per], 'Amplitude': [self.curr_ampl]}).round(
        #     3)  # Create table data
        self._freqtm = TableModel()  # Create table model
        self._freqtm.update(freq_cdf)
        self._freqtv = self.freq_list
        self._freqtv.setModel(self._freqtm)
        self._freqtv.horizontalHeader().setResizeMode(QtGui.QHeaderView.Stretch)
        # self._freqtv.resizeColumnsToContents()
        # self._freqtv.resizeRowsToContents()

    def onMouseClicked(self, point):
        if point.button() == 1:
            # print(point)
            # tt = QtCore.QPointF(point.pos()[0], point.pos()[1])
            tt = self.current_point
            self.mouse_x = self.dft.plotItem.vb.mapSceneToView(tt).x()
            self.mouse_y = self.dft.plotItem.vb.mapSceneToView(tt).y()
            self.curr_per = 1. / self.mouse_x
            self.curr_per_n = self.curr_per
            self.plot_ph()  # update phase plot
            self.show_table()  # update frequency list
            self.plot_line()  # plot vertical line
            self.phase_slider.setValue(0)  # reset slider

    def onMouseMoved(self, point):
        # print(point)
        self.current_point = point
        mousePoint_lc = self.lc.plotItem.vb.mapSceneToView(point)
        mousePoint_ph = self.ph.plotItem.vb.mapSceneToView(point)
        mousePoint_dft = self.dft.plotItem.vb.mapSceneToView(point)
        self.statusBar().showMessage(
            '{:2s}\tx: {:6.3f}   y: {:6.3f}\t{:>20s}\tx: {:6.3f}   y: {:6.3f}\t{:>20s}\tx: {:6.3f}   y: {:6.3f}'.format(
                'LC: ', mousePoint_lc.x(), mousePoint_lc.y(), 'TRF: ', mousePoint_dft.x(), mousePoint_dft.y(), 'PHS: ',
                mousePoint_ph.x(), mousePoint_ph.y()))

    def onClicked(self, index):
        self.file_path = self.sender().model().filePath(index)
        self.time, self.flux, self.ferr = np.loadtxt(self.file_path, unpack=True)
        system('bash ' + self.dir_path + 'lcdft.bash ' + self.file_path + ' 0 300 ' + self.dir_path)
        self.freq, self.ampl = np.loadtxt('lcf.trf', unpack=True)
        self.plot_lc()  # plot lc graph
        self.plot_dft()  # plot dft graph
        self.plot_ph()  # plot dft graph
        self.show_table()  # update frequency list
        self.state_changed()

    def populate(self):
        path = QtCore.QDir.currentPath()
        self.model = QtWidgets.QFileSystemModel()
        self.model.setRootPath((QtCore.QDir.rootPath()))
        self.treeView.setModel(self.model)
        self.treeView.setRootIndex(self.model.index(path))
        # self.treeView.setSortingEnabled(True)
        for i in range(self.model.columnCount()):
            self.treeView.hideColumn(i + 1)

    def plot_ph(self):
        self.ph.setBackground('#1C1717')
        if self.file_path != 'first_run':
            self.phase = (self.time % self.curr_per) / self.curr_per
            temp = zip(self.phase, self.flux)
            temp = sorted(temp)
            self.phase, self.flux_ph = zip(*temp)
            self.phase = np.array(self.phase)
            self.flux_ph = np.array(self.flux_ph)
            self.ph.clear()
            self.ph.plot(np.r_[self.phase, self.phase + 1], np.r_[self.flux_ph, self.flux_ph], pen=None, symbol='o',
                         symbolSize=2.5,
                         symbolPen=self.sympen, symbolBrush=self.sympen)
            self.ph.autoRange()

    def plot_lc(self):
        self.lc.setBackground('#1C1717')
        if self.file_path != 'first_run':
            self.lc.clear()
            self.lc.plot(self.time, self.flux, pen=None, symbol='o', symbolSize=2.5, symbolPen=self.sympen,
                         symbolBrush=self.sympen)
            self.lc.autoRange()

    def update_line(self):
        try:
            self.dft.removeItem(self.line_curr_freq)
        except AttributeError:
            pass
        self.line_curr_freq = pg.InfiniteLine(pos=1. / self.curr_per_n, pen=self.redpen)
        self.dft.addItem(self.line_curr_freq)

    def plot_line(self):
        try:
            self.dft.removeItem(self.line_curr_freq)
        except AttributeError:
            pass
        self.line_curr_freq = pg.InfiniteLine(pos=self.mouse_x, pen=self.redpen)
        self.dft.addItem(self.line_curr_freq)

    def plot_dft(self):
        self.dft.setBackground('#1C1717')
        if self.file_path != 'first_run':
            self.curr_per_n = 1. / self.freq[
                np.where(self.ampl == max(self.ampl[np.where(np.abs(self.freq - 0.5) <= 1e-6)[0][0]:]))[0][0]]
            self.curr_per = self.curr_per_n
            self.curr_ampl = max(self.ampl[np.where(np.abs(self.freq - 0.5) <= 1e-6)[0][0]:])
            self.max_per = self.curr_per
            self.dft.clear()
            self.dft.plot(self.freq, self.ampl, pen=self.sympen)
            self.dft.autoRange()

    def closeEvent(self, event):
        msg_box = QtWidgets.QMessageBox()
        msg_box.setIcon(QtWidgets.QMessageBox.Information)
        msg_box.setText("Do you really want to quit?")
        msg_box.setWindowTitle("Exit?")
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        return_value = msg_box.exec_()
        if return_value == QtWidgets.QMessageBox.Ok:
            print('Bye bye')
            event.accept()
        else:
            event.ignore()


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon(dir_path + 'kzhya_ico-64.png'))
    app.setStyle('Fusion')
    app.setApplicationName('lcView')
    window = lcdftMain()
    # window.setWindowFlags(QtCore.Qt.FramelessWindowHint)
    window.move(0, 0)
    window.show()
    sys.exit(app.exec_())