# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PCA4CD
                                 A QGIS plugin
 Principal components analysis for change detections
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
from qgis.PyQt.QtWidgets import QWidget, QGridLayout, QFileDialog
from qgis.PyQt.QtCore import QSettings, pyqtSlot, QTimer
from qgis.core import QgsGeometry, QgsMapLayerProxyModel, QgsWkbTypes, QgsPoint
from qgis.gui import QgsMapCanvas, QgsMapToolPan
from qgis.utils import iface

from pca4cd.utils.qgis_utils import load_and_select_filepath_in, StyleEditorDialog
from pca4cd.utils.system_utils import block_signals_to


class RenderWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi()
        self.layer = None
        self.crs = None

    def setupUi(self):
        gridLayout = QGridLayout(self)
        gridLayout.setContentsMargins(0, 0, 0, 0)
        self.canvas = QgsMapCanvas()
        self.canvas.setCanvasColor(QColor(255, 255, 255))
        self.canvas.setStyleSheet("border: 0px;")
        settings = QSettings()
        self.canvas.enableAntiAliasing(settings.value("/qgis/enable_anti_aliasing", False, type=bool))
        self.setMinimumSize(15, 15)
        # action pan
        self.toolPan = QgsMapToolPan(self.canvas)
        self.canvas.setMapTool(self.toolPan)

        gridLayout.addWidget(self.canvas)

    def render_layer(self, layer):
        from pca4cd.gui.change_analysis_dialog import ChangeAnalysisDialog

        with block_signals_to(self):
            if not layer:
                self.canvas.setLayers([])
                self.canvas.clearCache()
                self.canvas.refresh()
                self.layer = None
                # deactivate some parts of this view
                self.parent().QLabel_ViewName.setDisabled(True)
                self.parent().render_widget.setDisabled(True)
                self.parent().layerStyleEditor.setDisabled(True)
                self.canvas.setCanvasColor(QColor(245, 245, 245))
                # set status for view widget
                self.parent().is_active = False
                return
            # activate some parts of this view
            self.parent().QLabel_ViewName.setEnabled(True)
            self.parent().render_widget.setEnabled(True)
            self.parent().layerStyleEditor.setEnabled(True)
            self.canvas.setCanvasColor(QColor(255, 255, 255))

            # set the CRS of the canvas view
            if self.crs:
                self.canvas.setDestinationCrs(self.crs)
            # set the sampling over the layer to view
            #self.canvas.setLayers([self.parent().sampling_layer, layer])
            self.canvas.setLayers([layer])
            # set init extent from other view if any is activated else set layer extent

            others_view = [(view_widget.render_widget.canvas.extent(), view_widget.current_scale_factor) for view_widget
                           in ChangeAnalysisDialog.view_widgets if not view_widget.render_widget.canvas.extent().isEmpty()]
            if others_view:
                extent, scale = others_view[0]
                extent.scale(1 / scale)
                self.set_extents_and_scalefactor(extent)
            else:
                self.canvas.setExtent(layer.extent())

            self.canvas.refresh()
            self.layer = layer
            # show marker

            # set status for view widget
            self.parent().is_active = True

    def set_extents_and_scalefactor(self, extent):
        with block_signals_to(self.canvas):
            self.canvas.setExtent(extent)
            self.canvas.zoomByFactor(1)

    def layer_style_editor(self):
        style_editor_dlg = StyleEditorDialog(self.layer, self.canvas, self.parent())
        if style_editor_dlg.exec_():
            style_editor_dlg.apply()


# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    plugin_folder, 'ui', 'change_analysis_view_widget.ui'))


class ChangeAnalysisViewWidget(QWidget, FORM_CLASS):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.id = None
        self.is_active = False
        self.current_scale_factor = 1.0
        self.qgs_main_canvas = iface.mapCanvas()
        self.setupUi(self)
        # init as unactivated render widget for new instances
        self.render_widget.render_layer(None)

    def setup_view_widget(self, crs):
        self.render_widget.crs = crs
        self.change_layer = None
        # set properties to QgsMapLayerComboBox
        self.QCBox_RenderFile.setCurrentIndex(-1)
        self.QCBox_RenderFile.setFilters(QgsMapLayerProxyModel.All)
        # ignore and not show the sampling layer
        self.QCBox_RenderFile.setExceptedLayerList([self.change_layer])
        # handle connect layer selection with render canvas
        self.QCBox_RenderFile.currentIndexChanged.connect(lambda: self.render_widget.render_layer(
            self.QCBox_RenderFile.currentLayer()))
        # call to browse the render file
        self.QCBox_browseRenderFile.clicked.connect(lambda: self.fileDialog_browse(
            self.QCBox_RenderFile,
            dialog_title=self.tr("Select the file for this view"),
            dialog_types=self.tr("Raster or vector files (*.tif *.img *.gpkg *.shp);;All files (*.*)"),
            layer_type="any"))

        # edit layer properties
        self.layerStyleEditor.clicked.connect(self.render_widget.layer_style_editor)
        # action for synchronize all view extent
        self.render_widget.canvas.extentsChanged.connect(self.extent_changed)
        # disable enter action
        self.QCBox_browseRenderFile.setAutoDefault(False)

    @pyqtSlot()
    def fileDialog_browse(self, combo_box, dialog_title, dialog_types, layer_type):
        file_path, _ = QFileDialog.getOpenFileName(self, dialog_title, "", dialog_types)
        if file_path != '' and os.path.isfile(file_path):
            # load to qgis and update combobox list
            load_and_select_filepath_in(combo_box, file_path, layer_type)

            self.render_widget.render_layer(combo_box.currentLayer())

    @pyqtSlot()
    def extent_changed(self):
        if self.is_active:
            from pca4cd.gui.change_analysis_dialog import ChangeAnalysisDialog
            view_extent = self.render_widget.canvas.extent()
            view_extent.scale(1/self.current_scale_factor)

            # set extent and scale factor for all view activated except this view
            for view_widget in ChangeAnalysisDialog.view_widgets:
                if view_widget.is_active and view_widget != self:
                    view_widget.render_widget.set_extents_and_scalefactor(view_extent)
