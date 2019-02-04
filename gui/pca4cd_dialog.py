# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PCA4CD
                                 A QGIS plugin
 Principal components analysis for change detection
                              -------------------
        copyright            : (C) 2018-2019 by Xavier Corredor Llano, SMByC
        email                : xcorredorl@ideam.gov.co
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
import configparser
import webbrowser
import numpy as np
from multiprocessing import cpu_count
from pathlib import Path
from osgeo import gdal

from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, pyqtSlot
from qgis.PyQt.QtWidgets import QFileDialog, QDialog
from qgis.core import QgsMapLayerProxyModel, Qgis

from pca4cd.core.pca_dask_gdal import pca
from pca4cd.gui.about_dialog import AboutDialog
from pca4cd.gui.main_analysis_dialog import MainAnalysisDialog
from pca4cd.utils.qgis_utils import load_and_select_filepath_in, load_layer_in_qgis, get_file_path_of_layer
from pca4cd.utils.system_utils import error_handler, wait_process

# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(Path(plugin_folder, 'ui', 'pca4cd_dialog.ui'))

cfg = configparser.ConfigParser()
cfg.read(str(Path(plugin_folder, 'metadata.txt')))
VERSION = cfg.get('general', 'version')
HOMEPAGE = cfg.get('general', 'homepage')


class PCA4CDDialog(QDialog, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(PCA4CDDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.setup_gui()

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def setup_gui(self):
        # ######### plugin info ######### #
        self.about_dialog = AboutDialog()
        self.QPBtn_PluginInfo.setText("v{}".format(VERSION))
        self.QPBtn_PluginInfo.clicked.connect(self.about_dialog.show)
        self.QPBtn_PluginDocs.clicked.connect(lambda: webbrowser.open("https://smbyc.bitbucket.io/qgisplugins/pca4cd"))

        # ######### Input Raster Data ######### #
        ## A
        # set properties to QgsMapLayerComboBox
        self.QCBox_InputData_A.setCurrentIndex(-1)
        self.QCBox_InputData_A.setFilters(QgsMapLayerProxyModel.RasterLayer)
        # call to browse the thematic raster file
        self.QPBtn_browseData_A.clicked.connect(lambda: self.fileDialog_browse(
            self.QCBox_InputData_A,
            dialog_title=self.tr("Select the first period of the raster image to analyze"),
            dialog_types=self.tr("Raster files (*.tif *.img);;All files (*.*)"),
            layer_type="raster"))
        self.QCBox_InputData_A.currentIndexChanged.connect(self.set_number_of_components)
        self.QCBox_InputData_A.currentIndexChanged.connect(self.set_nodata_value_in_computePC)
        self.EnableInputData_A.toggled.connect(lambda: self.EnableInputData_A.setChecked(True))
        ## B
        # set properties to QgsMapLayerComboBox
        self.QCBox_InputData_B.setCurrentIndex(-1)
        self.QCBox_InputData_B.setFilters(QgsMapLayerProxyModel.RasterLayer)
        # call to browse the thematic raster file
        self.QPBtn_browseData_B.clicked.connect(lambda: self.fileDialog_browse(
            self.QCBox_InputData_B,
            dialog_title=self.tr("Select the second period of the raster image to analyze"),
            dialog_types=self.tr("Raster files (*.tif *.img);;All files (*.*)"),
            layer_type="raster"))
        self.QCBox_InputData_B.currentIndexChanged.connect(self.set_number_of_components)
        self.EnableInputData_B.toggled.connect(lambda: self.QCBox_InputData_B.setCurrentIndex(-1))

        # ######### Principal Components ######### #
        self.QPBtn_runPCA.clicked.connect(self.generate_principal_components)
        # process settings
        self.group_ProcessSettings.setVisible(False)
        self.nThreads.setValue(cpu_count())

        # ######### Load External Principal Components ######### #
        self.QgsFile_LoadStackPCA.fileChanged.connect(self.set_nodata_value_in_loadPC)
        # load
        self.QPBtn_LoadStackPCA.clicked.connect(self.load_external_pc_in_main_analysis_dialog)

    @pyqtSlot()
    def fileDialog_browse(self, combo_box, dialog_title, dialog_types, layer_type):
        file_path, _ = QFileDialog.getOpenFileName(self, dialog_title, "", dialog_types)
        if file_path != '' and os.path.isfile(file_path):
            # load to qgis and update combobox list
            load_and_select_filepath_in(combo_box, file_path, layer_type)

    @pyqtSlot()
    def set_nodata_value_in_computePC(self):
        if hasattr(self.QCBox_InputData_A.currentLayer(), "dataProvider"):
            nodata_value = self.QCBox_InputData_A.currentLayer().dataProvider().sourceNoDataValue(1)
            nodata_value = str(nodata_value) if not np.isnan(nodata_value) else ""
            self.NoData_ComputePCA.setText(nodata_value)

    @pyqtSlot()
    def set_nodata_value_in_loadPC(self):
        stack_path = self.QgsFile_LoadStackPCA.filePath()
        src_ds = gdal.Open(stack_path, gdal.GA_ReadOnly)
        if src_ds is None:
            self.NoData_LoadPCA.setText("")
            return
        nodata_value = src_ds.GetRasterBand(1).GetNoDataValue()
        nodata_value = str(nodata_value) if nodata_value not in [None, "nan"] else ""
        self.NoData_LoadPCA.setText(nodata_value)
        del src_ds

    @pyqtSlot()
    def set_number_of_components(self):
        current_layer_A = self.QCBox_InputData_A.currentLayer()
        current_layer_B = self.QCBox_InputData_B.currentLayer()
        self.QCBox_nComponents.clear()

        number_components = 0
        if current_layer_A is not None:
            number_components += current_layer_A.bandCount()
        if current_layer_B is not None:
            number_components += current_layer_B.bandCount()

        if number_components != 0:
            # set number of components to combobox
            self.QCBox_nComponents.addItems([str(x) for x in range(1, number_components + 1)])
            # select the last item
            self.QCBox_nComponents.setCurrentIndex(number_components-1)

    def check_input_layers(self, layer_A, layer_B):
        if layer_B is None:
            return True
        if layer_A.crs() != layer_B.crs():
            self.MsgBar.pushMessage("The layers don't have the same projection", level=Qgis.Warning)
            return False
        if layer_A.width() != layer_B.width() or \
           layer_A.height() != layer_B.height():
            self.MsgBar.pushMessage("The layers don't have the same column/row", level=Qgis.Warning)
            return False
        if round(layer_A.rasterUnitsPerPixelX(), 6) != round(layer_B.rasterUnitsPerPixelX(), 6) or \
           round(layer_A.rasterUnitsPerPixelY(), 6) != round(layer_B.rasterUnitsPerPixelY(), 6):
            self.MsgBar.pushMessage("The layers don't have the same pixel size", level=Qgis.Warning)
            return False
        return True

    @pyqtSlot()
    @error_handler
    def generate_principal_components(self):
        from pca4cd.pca4cd import PCA4CD as pca4cd
        # check if is valid the input raster layer
        if self.QCBox_InputData_A.currentLayer() is None:
            self.MsgBar.pushMessage("Select a valid input raster layer", level=Qgis.Warning)
            return
        # check both layers
        if not self.check_input_layers(self.QCBox_InputData_A.currentLayer(), self.QCBox_InputData_B.currentLayer()):
            return
        # check the nodata value
        nodata = self.NoData_ComputePCA.text() if self.NoData_ComputePCA.text() not in ["", "None", "nan"] else None
        if nodata is not None:
            try:
                nodata = float(nodata)
            except:
                self.MsgBar.pushMessage("The nodata value is not valid", level=Qgis.Warning)
                return

        path_layer_A = get_file_path_of_layer(self.QCBox_InputData_A.currentLayer())
        path_layer_B = get_file_path_of_layer(self.QCBox_InputData_B.currentLayer())
        n_pc = int(self.QCBox_nComponents.currentText())
        estimator_matrix = self.QCBox_EstimatorMatrix.currentText()

        pca_files, pca_stats = pca(path_layer_A, path_layer_B, n_pc, estimator_matrix, pca4cd.tmp_dir,
                                   self.nThreads.value(), self.BlockSize.value(), nodata)

        pca_layers = []
        if pca_files:
            for pca_file in pca_files:
                pca_layers.append(load_layer_in_qgis(pca_file, "raster", False))
            # then, open main analysis dialog
            self.open_main_analysis_dialog(pca_layers, pca_stats, nodata)
        else:
            self.MsgBar.pushMessage("Error while generating the principal components, check the Qgis log", level=Qgis.Critical)

    @pyqtSlot()
    def open_main_analysis_dialog(self, pca_layers, pca_stats, nodata):
        current_layer_A = self.QCBox_InputData_A.currentLayer()
        current_layer_B = self.QCBox_InputData_B.currentLayer()
        self.main_analysis_dialog = MainAnalysisDialog(current_layer_A, current_layer_B, pca_layers, pca_stats, nodata)
        # open dialog
        self.main_analysis_dialog.show()
        self.main_analysis_dialog.update_pc_style()

    @pyqtSlot()
    @wait_process
    def load_external_pc_in_main_analysis_dialog(self):
        from pca4cd.pca4cd import PCA4CD as pca4cd
        stack_path = self.QgsFile_LoadStackPCA.filePath()
        if not os.path.isfile(stack_path):
            self.MsgBar.pushMessage("Select a valid stack for load", level=Qgis.Warning)
            return False
        # check the nodata value
        nodata = self.NoData_LoadPCA.text() if self.NoData_LoadPCA.text() not in ["", "None", "nan"] else None
        if nodata is not None:
            try:
                nodata = float(nodata)
            except:
                self.MsgBar.pushMessage("The nodata value is not valid", level=Qgis.Warning)
                return

        # extract each band as component in tmp file
        src_ds = gdal.Open(stack_path, gdal.GA_ReadOnly)
        num_bands = src_ds.RasterCount
        del src_ds
        pca_layers = []
        for component in range(num_bands):
            tmp_pca_file = Path(pca4cd.tmp_dir) / 'pc_{}.tif'.format(component + 1)
            gdal.Translate(str(tmp_pca_file), stack_path, bandList=[component + 1], noData=nodata)
            pca_layers.append(load_layer_in_qgis(tmp_pca_file, "raster", False))

        # pca statistics
        pca_stats = {}
        pca_stats["eigenvals"] = None

        self.main_analysis_dialog = MainAnalysisDialog(None, None, pca_layers, pca_stats, nodata)
        # open dialog
        self.main_analysis_dialog.show()
        self.main_analysis_dialog.update_pc_style()
