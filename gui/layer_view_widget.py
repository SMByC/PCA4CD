# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PCA4CD
                                 A QGIS plugin
 Principal components analysis for change detection
                              -------------------
        copyright            : (C) 2018 by Xavier Corredor Llano, SMByC
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

from qgis.PyQt import uic
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QWidget, QFileDialog
from qgis.PyQt.QtCore import pyqtSlot

from pca4cd.gui.component_analysis_dialog import ComponentAnalysisDialog
from pca4cd.utils.qgis_utils import load_and_select_filepath_in
from pca4cd.utils.system_utils import block_signals_to

# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    plugin_folder, 'ui', 'layer_view_widget.ui'))


class LayerViewWidget(QWidget, FORM_CLASS):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.id = None
        self.pc_id = None
        self.is_active = False
        self.setupUi(self)
        self.component_analysis_dialog = None
        # init as unactivated render widget for new instances
        self.disable()

    def setup_view_widget(self, crs):
        self.render_widget.parent_view = self
        self.render_widget.crs = crs
        # set properties to QgsMapLayerComboBox
        self.QCBox_RenderFile.setCurrentIndex(-1)
        # handle connect layer selection with render canvas
        self.QCBox_RenderFile.currentIndexChanged.connect(lambda: self.set_render_layer(self.QCBox_RenderFile.currentLayer()))
        # call to browse the render file
        self.QCBox_browseRenderFile.clicked.connect(lambda: self.fileDialog_browse(
            self.QCBox_RenderFile,
            dialog_title=self.tr("Select the file for this view"),
            dialog_types=self.tr("Raster or vector files (*.tif *.img *.gpkg *.shp);;All files (*.*)"),
            layer_type="any"))
        # edit layer properties
        self.layerStyleEditor.clicked.connect(self.render_widget.layer_style_editor)
        # active/deactive
        self.EnableChangeDetection.toggled.connect(self.detection_layer_toggled)
        # disable enter action
        self.QCBox_browseRenderFile.setAutoDefault(False)

        # component analysis layer
        self.QPBtn_ComponentAnalysisDialog.clicked.connect(self.open_component_analysis_dialog)

    def enable(self):
        with block_signals_to(self.render_widget):
            # activate some parts of this view
            self.QLabel_ViewName.setEnabled(True)
            self.render_widget.setEnabled(True)
            self.layerStyleEditor.setEnabled(True)
            self.render_widget.canvas.setCanvasColor(QColor(255, 255, 255))
            # set status for view widget
            self.is_active = True

    def disable(self):
        with block_signals_to(self.render_widget):
            self.render_widget.canvas.setLayers([])
            self.render_widget.canvas.clearCache()
            self.render_widget.canvas.refresh()
            self.render_widget.layer = None
            # deactivate some parts of this view
            self.QLabel_ViewName.setDisabled(True)
            self.render_widget.setDisabled(True)
            self.layerStyleEditor.setDisabled(True)
            self.render_widget.canvas.setCanvasColor(QColor(245, 245, 245))
            # set status for view widget
            self.is_active = False

    def set_render_layer(self, layer):
        if not layer:
            self.disable()
            return

        self.enable()
        self.render_widget.render_layer(layer)

    @pyqtSlot()
    def fileDialog_browse(self, combo_box, dialog_title, dialog_types, layer_type):
        file_path, _ = QFileDialog.getOpenFileName(self, dialog_title, "", dialog_types)
        if file_path != '' and os.path.isfile(file_path):
            # load to qgis and update combobox list
            load_and_select_filepath_in(combo_box, file_path, layer_type)

            self.set_render_layer(combo_box.currentLayer())

    @pyqtSlot()
    def canvas_changed(self):
        if self.is_active:
            new_extent = self.render_widget.canvas.extent()
            # update canvas for all view activated except this view
            from pca4cd.gui.main_analysis_dialog import MainAnalysisDialog
            for view_widget in MainAnalysisDialog.view_widgets:
                # for layer view widget in main analysis dialog
                if view_widget.is_active and view_widget != self:
                    view_widget.render_widget.update_canvas_to(new_extent)
                # for components analysis opened
                if view_widget.component_analysis_dialog and view_widget.component_analysis_dialog.is_opened:
                    view_widget.component_analysis_dialog.render_widget.update_canvas_to(new_extent)

    @pyqtSlot()
    def detection_layer_toggled(self):
        if self.EnableChangeDetection.isChecked():
            self.render_widget.show_detection_layer()
        else:
            self.render_widget.hide_detection_layer()

    @pyqtSlot()
    def open_component_analysis_dialog(self):
        if not self.component_analysis_dialog:
            self.component_analysis_dialog = ComponentAnalysisDialog(parent_view_widget=self)
        if self.component_analysis_dialog.is_opened:
            self.component_analysis_dialog.activateWindow()
            return
        self.component_analysis_dialog.show()
        # synchronize extent canvas for the component analysis dialog respect to parent view widget
        new_extent = self.render_widget.canvas.extent()
        self.component_analysis_dialog.render_widget.update_canvas_to(new_extent)

