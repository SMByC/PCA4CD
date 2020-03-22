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
import platform
import shutil
import tempfile
import subprocess

import numpy as np
from pathlib import Path
from osgeo import gdal

from qgis.core import Qgis, QgsSingleBandGrayRenderer, QgsContrastEnhancement
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, pyqtSlot
from qgis.PyQt.QtWidgets import QDialog, QGridLayout, QMessageBox, QFileDialog
from qgis.utils import iface

from pca4cd.gui.layer_view_widget import LayerViewWidget
from pca4cd.gui.merge_change_layers_dialog import MergeChangeLayersDialog
from pca4cd.utils.qgis_utils import load_layer, apply_symbology, get_file_path_of_layer, unload_layer
from pca4cd.utils.system_utils import wait_process

# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(Path(plugin_folder, 'ui', 'main_analysis_dialog.ui'))


class MainAnalysisDialog(QDialog, FORM_CLASS):
    view_widgets = []
    pca_layers = None
    pca_stats = None
    nodata = None

    def __init__(self, layer_a, layer_b, pca_layers, pca_stats, nodata=None):
        QDialog.__init__(self)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.layer_a = layer_a
        self.layer_b = layer_b
        self.pca_layers = pca_layers
        MainAnalysisDialog.pca_layers = pca_layers
        MainAnalysisDialog.pca_stats = pca_stats
        MainAnalysisDialog.nodata = nodata
        # flags
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)

        self.setupUi(self)

        # dialog buttons box
        self.CloseButton.clicked.connect(self.closing)
        # return
        self.ReturnToMainDialog.clicked.connect(self.return_to_main_dialog)
        # save all components in a stack
        self.SavePCA.clicked.connect(self.save_pca)
        if self.layer_a is None:
            self.SavePCA.setDisabled(True)
            self.SavePCA.setToolTip("Not available if the components are loaded externally")
        # merge change layer
        self.OpenMergeChangeLayers.clicked.connect(self.open_merge_change_layers)

        # size of the grid with view render widgets windows
        if self.layer_b is not None:
            if len(pca_layers) <= 4:
                grid_rows = 2
                grid_columns = 4
            elif len(pca_layers) <= 8:
                grid_rows = 3
                grid_columns = 4
            elif len(pca_layers) <= 12:
                grid_rows = 4
                grid_columns = 4
            elif len(pca_layers) <= 16:
                grid_rows = 5
                grid_columns = 4
            elif len(pca_layers) <= 20:
                grid_rows = 5
                grid_columns = 5
        if self.layer_b is None:
            if len(pca_layers) <= 3:
                grid_rows = 2
                grid_columns = 3
            elif len(pca_layers) <= 6:
                grid_rows = 3
                grid_columns = 3
            elif len(pca_layers) <= 9:
                grid_rows = 4
                grid_columns = 3
            elif len(pca_layers) <= 12:
                grid_rows = 4
                grid_columns = 4
            elif len(pca_layers) <= 16:
                grid_rows = 5
                grid_columns = 4
            elif len(pca_layers) <= 20:
                grid_rows = 5
                grid_columns = 5

        # configure the views layout
        views_layout = QGridLayout()
        views_layout.setSpacing(0)
        views_layout.setMargin(0)
        view_widgets = []
        for row in range(grid_rows):
            if row == 0:
                for column in range(grid_columns):
                    new_view_widget = LayerViewWidget()
                    views_layout.addWidget(new_view_widget, row, column)
                    view_widgets.append(new_view_widget)
            else:
                for column in range(grid_columns):
                    if (row-1)*grid_columns + column < len(pca_layers):
                        new_view_widget = LayerViewWidget()
                        views_layout.addWidget(new_view_widget, row, column)
                        view_widgets.append(new_view_widget)

        # add to change analysis dialog
        self.widget_view_windows.setLayout(views_layout)
        # save instances
        MainAnalysisDialog.view_widgets = view_widgets
        # setup view widget
        for idx, view_widget in enumerate(MainAnalysisDialog.view_widgets, start=1):
            view_widget.id = idx
            view_widget.setup_view_widget(crs=self.pca_layers[0].crs())
        # set views
        for num_view, view_widget in enumerate(MainAnalysisDialog.view_widgets, start=1):
            if num_view == 2 and self.layer_a is not None:
                view_widget.QLabel_ViewName.setText("Layer A")
                file_index = view_widget.QCBox_RenderFile.findText(self.layer_a.name(), Qt.MatchFixedString)
                view_widget.QCBox_RenderFile.setCurrentIndex(file_index)
            if num_view == 3 and self.layer_b is not None:
                view_widget.QLabel_ViewName.setText("Layer B")
                file_index = view_widget.QCBox_RenderFile.findText(self.layer_b.name(), Qt.MatchFixedString)
                view_widget.QCBox_RenderFile.setCurrentIndex(file_index)
            if grid_columns < num_view <= len(self.pca_layers)+grid_columns:
                view_widget.pc_id = num_view-grid_columns
                view_widget.QLabel_ViewName.setText("Principal Component {}".format(view_widget.pc_id))
                file_index = view_widget.QCBox_RenderFile.findText(self.pca_layers[num_view-grid_columns-1].name(), Qt.MatchFixedString)
                view_widget.WidgetDetectionLayer.setEnabled(True)
                view_widget.QCBox_RenderFile.setCurrentIndex(file_index)
                view_widget.QCBox_RenderFile.setEnabled(False)
                view_widget.QCBox_browseRenderFile.setEnabled(False)
                # disconnect set_render_layer signal
                view_widget.QCBox_RenderFile.currentIndexChanged.disconnect()
            else:
                view_widget.QCBox_RenderFile.setExceptedLayerList(self.pca_layers)  # hide pca layers in combobox menu
                view_widget.EnableChangeDetection.setToolTip("Show/hide the merged change layer")
                view_widget.QPBtn_ComponentAnalysisDialog.setText("Merged change layer")
                view_widget.QPBtn_ComponentAnalysisDialog.setToolTip("The merged change layer has not been generated yet")
                # disconnect button action
                view_widget.QPBtn_ComponentAnalysisDialog.clicked.disconnect()
            if not view_widget.QLabel_ViewName.text():
                view_widget.QLabel_ViewName.setPlaceholderText("Auxiliary View")

        self.MsgBar.pushMessage("{} principal components were generated and loaded successfully".format(len(self.pca_layers)),
                                level=Qgis.Success)

    def show(self):
        from pca4cd.pca4cd import PCA4CD as pca4cd
        # hide main dialog
        pca4cd.dialog.hide()
        # show dialog
        super(MainAnalysisDialog, self).show()

    def closeEvent(self, event):
        self.closing()
        event.ignore()

    def return_to_main_dialog(self):
        # first prompt
        quit_msg = "Are you sure you want to return to the main dialog? you will lose all the products generated"
        reply = QMessageBox.question(None, 'Return to Compute the Principal Components',
                                     quit_msg, QMessageBox.Yes, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        # clear/close components analysis
        for view_widget in MainAnalysisDialog.view_widgets:
            if view_widget.component_analysis_dialog and view_widget.component_analysis_dialog.is_opened:
                view_widget.component_analysis_dialog.deleteLater()
            # clean view widget and its component analysis
            view_widget.clean()

        # clear and recover
        from pca4cd.pca4cd import PCA4CD as pca4cd
        self.reject(is_ok_to_close=True)
        self.deleteLater()
        pca4cd.removes_temporary_files()
        pca4cd.tmp_dir = Path(tempfile.mkdtemp())
        iface.mapCanvas().clearCache()
        # recover the main dialog
        pca4cd.dialog.show()

    def closing(self):
        """
        Do this before close the dialog
        """
        # first prompt
        quit_msg = "Are you sure you want close the PCA4CD plugin?"
        reply = QMessageBox.question(None, 'Closing the PCA4CD plugin',
                                     quit_msg, QMessageBox.Yes, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        # close components analysis opened
        for view_widget in MainAnalysisDialog.view_widgets:
            if view_widget.component_analysis_dialog and view_widget.component_analysis_dialog.is_opened:
                view_widget.component_analysis_dialog.deleteLater()
            # clean view widget and its component analysis
            view_widget.clean()

        # clear and close main dialog
        from pca4cd.pca4cd import PCA4CD as pca4cd
        pca4cd.dialog.close()
        iface.mapCanvas().clearCache()
        self.reject(is_ok_to_close=True)

    def reject(self, is_ok_to_close=False):
        if is_ok_to_close:
            super(MainAnalysisDialog, self).reject()

    @wait_process
    def update_pc_style(self):
        """Update the grey style using mean+-5*std for all principal components
        """
        for view_widget in MainAnalysisDialog.view_widgets:
            if view_widget.pc_id is not None:
                src_ds = gdal.Open(str(get_file_path_of_layer(view_widget.render_widget.layer)), gdal.GA_ReadOnly)
                ds = src_ds.GetRasterBand(1).ReadAsArray().flatten().astype(np.float32)
                ds = ds[ds != 0]
                try:
                    mean = np.mean(ds)
                    std = np.std(ds)
                except:
                    continue
                renderer = QgsSingleBandGrayRenderer(view_widget.render_widget.layer.dataProvider(), 1)
                ce = QgsContrastEnhancement(view_widget.render_widget.layer.dataProvider().dataType(0))
                ce.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
                ce.setMinimumValue(mean - 5*std)
                ce.setMaximumValue(mean + 5*std)
                renderer.setContrastEnhancement(ce)
                view_widget.render_widget.layer.setRenderer(renderer)
                del src_ds, ds

    @pyqtSlot()
    def save_pca(self):
        # suggested filename
        path, filename = os.path.split(get_file_path_of_layer(self.layer_a))
        suggested_filename = os.path.splitext(Path(path, filename))[0] + "_pca.tif"
        # filesave dialog
        file_out, _ = QFileDialog.getSaveFileName(self, self.tr("Save the PCA stack"), suggested_filename,
                                                  self.tr("GeoTiff files (*.tif);;All files (*.*)"))

        @wait_process
        def save():
            nodata = ['-a_nodata', '0'] if MainAnalysisDialog.nodata is not None else []
            cmd = ['gdal_merge' if platform.system() == 'Windows' else 'gdal_merge.py', '-q'] + \
                  ['', '-separate', '-of', 'GTiff', '-o', '"{}"'.format(file_out)] + nodata + \
                  ['"{}"'.format(get_file_path_of_layer(layer)) for layer in self.pca_layers]
            subprocess.run(cmd)

            self.MsgBar.pushMessage("PCA stack saved successfully: \"{}\"".format(os.path.basename(file_out)), level=Qgis.Success)

        if file_out != '':
            save()

    @pyqtSlot()
    def open_merge_change_layers(self):
        # select all activated change layers
        self.activated_ids = []
        self.activated_change_layers = []
        for view_widget in MainAnalysisDialog.view_widgets:
            if view_widget.pc_id is not None and view_widget.render_widget.detection_layer is not None \
                    and view_widget.EnableChangeDetection.isChecked():
                self.activated_ids.append("PC{}".format(view_widget.pc_id))
                self.activated_change_layers.append(view_widget.render_widget.detection_layer)
        if len(self.activated_change_layers) == 0:
            self.MsgBar.pushMessage(
                "There is not change detection layers activated/generated in the Principal Components view",
                level=Qgis.Warning)
            return
        # suggested filename
        if self.layer_a is not None:
            path, filename = os.path.split(str(get_file_path_of_layer(self.layer_a)))
        else:
            from pca4cd.pca4cd import PCA4CD as pca4cd
            path, filename = os.path.split(str(get_file_path_of_layer(pca4cd.dialog.QCBox_LoadStackPCA.currentLayer())))
        suggested_filename = os.path.splitext(Path(path, filename))[0] + "_pca4cd.tif"
        # merge dialog
        merge_dialog = MergeChangeLayersDialog(self.activated_ids, suggested_filename)
        if merge_dialog.exec_():
            self.do_merge_change_layers(merge_dialog)

    @pyqtSlot()
    def do_merge_change_layers(self, merge_dialog):
        merged_change_layer = Path(merge_dialog.MergeFileWidget.filePath())
        MergeChangeLayersDialog.merged_file_path = merged_change_layer
        # first unload layer from qgis if exists
        unload_layer(merged_change_layer)

        merge_method = merge_dialog.MergeMethod.currentText()

        if len(self.activated_change_layers) == 1:
            shutil.copy(get_file_path_of_layer(self.activated_change_layers[0]), merged_change_layer)

        if len(self.activated_change_layers) > 1 and merge_method == "Union":
            cmd = ['gdal_merge' if platform.system() == 'Windows' else 'gdal_merge.py',
                   '-of', 'GTiff', '-o', str(merged_change_layer), '-n', '0', '-a_nodata', '0', '-ot',
                   'Byte'] + [str(get_file_path_of_layer(layer)) for layer in self.activated_change_layers]
            subprocess.run(cmd)

        if len(self.activated_change_layers) > 1 and merge_method == "Intersection":
            alpha_list = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S",
                          "T", "U", "V", "W", "X", "Y", "Z"]
            input_files = {alpha_list[x]: str(get_file_path_of_layer(f)) for x, f in enumerate(self.activated_change_layers)}
            filter_ones = ",".join([alpha_list[x] + "==1" for x in range(len(self.activated_change_layers))])
            filter_zeros = ",".join([alpha_list[x] + "==0" for x in range(len(self.activated_change_layers))])

            cmd = ['gdal_calc' if platform.system() == 'Windows' else 'gdal_calc.py', '--overwrite',
                   '--calc', '0*(numpy.any([{filter_zeros}], axis=0)) + 1*(numpy.all([{filter_ones}], axis=0))'
                       .format(filter_zeros=filter_zeros, filter_ones=filter_ones),
                   '--outfile', str(merged_change_layer), '--NoDataValue=0', '--type=Byte'] + \
                  [i for sl in [["-{}".format(letter), filepath] for letter, filepath in input_files.items()] for i in sl]
            subprocess.run(cmd)

        # unset nodata
        cmd = ['gdal_edit' if platform.system() == 'Windows' else 'gdal_edit.py',
               '"{}"'.format(merged_change_layer), '-unsetnodata']
        subprocess.run(cmd)
        # apply style
        merged_layer = load_layer(merged_change_layer, add_to_legend=True if merge_dialog.LoadInQgis.isChecked() else False)
        apply_symbology(merged_layer, [("0", 0, (255, 255, 255, 0)), ("1", 1, (255, 255, 0, 255))])
        # save named style in QML aux file
        merged_layer.saveNamedStyle(str(merged_change_layer.with_suffix(".qml")))

        # add the merged layer to input and auxiliary view
        for view_widget in MainAnalysisDialog.view_widgets:
            if view_widget.pc_id is None:
                view_widget.WidgetDetectionLayer.setEnabled(True)
                view_widget.QPBtn_ComponentAnalysisDialog.setToolTip("")
                view_widget.render_widget.set_detection_layer(merged_layer)
                if view_widget.is_active:
                    view_widget.EnableChangeDetection.setChecked(True)
                    view_widget.QPBtn_ComponentAnalysisDialog.setEnabled(True)

        if len(self.activated_ids) == 1:
            self.MsgBar.pushMessage(
                "The change detection for {} was saved and loaded successfully".format(
                    self.activated_ids[0]), level=Qgis.Success)
        else:
            self.MsgBar.pushMessage(
                "The change detection for {} were merged, saved and loaded successfully".format(
                    ", ".join(self.activated_ids)), level=Qgis.Success)

