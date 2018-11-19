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
from PyQt5.QtCore import Qt, QTimer, QSettings, pyqtSlot
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QGridLayout
from qgis.gui import QgsMapToolPan, QgsMapCanvas

from pca4cd.utils.qgis_utils import StyleEditorDialog
from pca4cd.utils.system_utils import block_signals_to


class PanAndZoomPointTool(QgsMapToolPan):
    def __init__(self, render_widget):
        QgsMapToolPan.__init__(self, render_widget.canvas)
        self.render_widget = render_widget

    def update_canvas(self):
        self.render_widget.parent_view.canvas_changed()

    def canvasReleaseEvent(self, event):
        if event.button() != Qt.RightButton:
            QgsMapToolPan.canvasReleaseEvent(self, event)
            self.update_canvas()

    def wheelEvent(self, event):
        QgsMapToolPan.wheelEvent(self, event)
        QTimer.singleShot(10, self.update_canvas)

    def canvasPressEvent(self, event):
        if event.button() != Qt.RightButton:
            QgsMapToolPan.canvasPressEvent(self, event)


class RenderWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi()
        self.layer = None
        self.detection_layer = None
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
        # action pan and zoom
        self.pan_zoom_tool = PanAndZoomPointTool(self)
        self.canvas.setMapTool(self.pan_zoom_tool, clean=True)

        gridLayout.addWidget(self.canvas)

    def render_layer(self, layer):
        with block_signals_to(self):
            # set the CRS of the canvas view
            if self.crs:
                self.canvas.setDestinationCrs(self.crs)
            # set the sampling over the layer to view
            self.canvas.setLayers([layer])
            # set init extent from other view if any is activated else set layer extent
            from pca4cd.gui.main_analysis_dialog import MainAnalysisDialog
            others_view = [view_widget.render_widget.canvas.extent() for view_widget in MainAnalysisDialog.view_widgets
                           if not view_widget.render_widget.canvas.extent().isEmpty()]
            if others_view:
                extent = others_view[0]
                self.update_canvas_to(extent)
            else:
                self.canvas.setExtent(layer.extent())

            self.canvas.refresh()
            self.layer = layer

    def update_canvas_to(self, new_extent):
        with block_signals_to(self.canvas):
            self.canvas.setExtent(new_extent)
            self.canvas.refresh()

    def set_detection_layer(self, detection_layer):
        self.detection_layer = detection_layer
        self.show_detection_layer()
        # hide the detection layer in combobox menu
        from pca4cd.gui.main_analysis_dialog import MainAnalysisDialog
        detection_layers = [view_widget.render_widget.detection_layer for view_widget in MainAnalysisDialog.view_widgets
                            if view_widget.pc_id is not None and view_widget.render_widget.detection_layer is not None
                            and view_widget.id != self.parent_view.id] + [self.detection_layer]
        for view_widget in MainAnalysisDialog.view_widgets:
            if view_widget.pc_id is None:
                view_widget.QCBox_RenderFile.setExceptedLayerList(MainAnalysisDialog.pca_layers + detection_layers)

    def show_detection_layer(self):
        if self.layer:
            self.canvas.setLayers([self.detection_layer, self.layer])
            self.canvas.refreshAllLayers()

    def hide_detection_layer(self):
        if self.layer:
            self.canvas.setLayers([self.layer])
            self.canvas.refresh()

    @pyqtSlot()
    def layer_style_editor(self):
        style_editor_dlg = StyleEditorDialog(self.layer, self.canvas, self.parent())
        if style_editor_dlg.exec_():
            style_editor_dlg.apply()
