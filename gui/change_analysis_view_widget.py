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
from qgis.core import QgsMapLayerProxyModel, QgsRaster
from qgis.gui import QgsMapCanvas, QgsMapToolPan, QgsMapTool
from qgis.utils import iface

from pca4cd.utils.qgis_utils import load_and_select_filepath_in, StyleEditorDialog
from pca4cd.utils.system_utils import block_signals_to


class PanAndZoomPointTool(QgsMapToolPan):
    def __init__(self, render_widget):
        QgsMapToolPan.__init__(self, render_widget.canvas)
        self.render_widget = render_widget

    def canvasReleaseEvent(self, event):
        QgsMapToolPan.canvasReleaseEvent(self, event)
        self.update_canvas()

    def wheelEvent(self, event):
        QgsMapToolPan.wheelEvent(self, event)
        QTimer.singleShot(10, self.update_canvas)

    def update_canvas(self):
        self.render_widget.parent().view_changed()


class PickerPointTool(QgsMapTool):
    def __init__(self, render_widget, picker_widget):
        QgsMapTool.__init__(self, render_widget.canvas)
        self.render_widget = render_widget
        self.picker_widget = picker_widget

    def update_pixel_value_to_widget(self, event):
        x = event.pos().x()
        y = event.pos().y()
        point = self.render_widget.canvas.getCoordinateTransform().toMapCoordinates(x, y)
        pixel_value = self.render_widget.layer.dataProvider().identify(point, QgsRaster.IdentifyFormatValue).results()[1]
        self.picker_widget.setValue(pixel_value)

    def canvasMoveEvent(self, event):
        self.update_pixel_value_to_widget(event)

    def canvasPressEvent(self, event):
        self.update_pixel_value_to_widget(event)
        # restart point tool
        QTimer.singleShot(200, lambda: self.render_widget.canvas.setMapTool(self.render_widget.toolPan))


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
        # action pan and zoom
        self.toolPan = PanAndZoomPointTool(self)
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
            #self.canvas.setLayers([self.parent().sampling_layer, layer])  # TODO
            self.canvas.setLayers([layer])
            # set init extent from other view if any is activated else set layer extent

            others_view = [view_widget.render_widget.canvas.extent() for view_widget in ChangeAnalysisDialog.view_widgets
                           if not view_widget.render_widget.canvas.extent().isEmpty()]
            if others_view:
                extent = others_view[0]
                self.update_canvas_to(extent)
            else:
                self.canvas.setExtent(layer.extent())

            self.canvas.refresh()
            self.layer = layer
            # show marker

            # set status for view widget
            self.parent().is_active = True

    def update_canvas_to(self, new_extent):
        with block_signals_to(self.canvas):
            self.canvas.setExtent(new_extent)
            self.canvas.refresh()

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
        # picker pixel value widget
        self.PickerRangeFrom.clicked.connect(lambda: self.picker_mouse_value(self.RangeChangeFrom))
        self.PickerRangeTo.clicked.connect(lambda: self.picker_mouse_value(self.RangeChangeTo))
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
    def view_changed(self):
        if self.is_active:
            new_extent = self.render_widget.canvas.extent()
            # update canvas for all view activated except this view
            from pca4cd.gui.change_analysis_dialog import ChangeAnalysisDialog
            for view_widget in ChangeAnalysisDialog.view_widgets:
                if view_widget.is_active and view_widget != self:
                    view_widget.render_widget.update_canvas_to(new_extent)

    @pyqtSlot()
    def picker_mouse_value(self, picker_widget):
        self.render_widget.canvas.setMapTool(PickerPointTool(self.render_widget, picker_widget))