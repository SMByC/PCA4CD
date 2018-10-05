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
import numpy as np
from osgeo import gdal
from osgeo.gdalconst import GA_ReadOnly

from qgis.PyQt import uic
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QWidget, QGridLayout, QFileDialog
from qgis.PyQt.QtCore import QSettings, pyqtSlot, QTimer
from qgis.core import QgsRaster
from qgis.gui import QgsMapCanvas, QgsMapToolPan, QgsMapTool
from qgis.utils import iface

from pca4cd.libs import gdal_calc
from pca4cd.utils.qgis_utils import load_and_select_filepath_in, StyleEditorDialog, get_file_path_of_layer, \
    load_layer_in_qgis, apply_symbology
from pca4cd.utils.system_utils import block_signals_to, wait_process


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
        self.render_widget.parent_view.canvas_changed()


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
        if pixel_value is not None:
            self.picker_widget.setValue(pixel_value)

    def canvasMoveEvent(self, event):
        self.update_pixel_value_to_widget(event)

    def canvasPressEvent(self, event):
        self.update_pixel_value_to_widget(event)
        # restart point tool
        QTimer.singleShot(200, lambda: self.render_widget.canvas.setMapTool(self.render_widget.pan_zoom_tool))


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
        self.canvas.setMapTool(self.pan_zoom_tool)

        gridLayout.addWidget(self.canvas)

    def render_layer(self, layer):
        with block_signals_to(self):
            # set the CRS of the canvas view
            if self.crs:
                self.canvas.setDestinationCrs(self.crs)
            # set the sampling over the layer to view
            self.canvas.setLayers([layer])
            # set init extent from other view if any is activated else set layer extent
            from pca4cd.gui.change_analysis_dialog import ChangeAnalysisDialog
            others_view = [view_widget.render_widget.canvas.extent() for view_widget in ChangeAnalysisDialog.view_widgets
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

    def show_detection_layer(self):
        if self.detection_layer and self.layer:
            self.canvas.setLayers([self.detection_layer, self.layer])
            self.canvas.refresh()

    def hide_detection_layer(self):
        if self.layer:
            self.canvas.setLayers([self.layer])
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
        self.pc_id = None
        self.is_active = False
        self.setupUi(self)
        # init as unactivated render widget for new instances
        self.disable()

    def setup_view_widget(self, crs):
        self.render_widget.parent_view = self
        self.render_widget.crs = crs
        self.detection_layers = None
        # set properties to QgsMapLayerComboBox
        self.QCBox_RenderFile.setCurrentIndex(-1)
        #self.QCBox_RenderFile.setFilters(QgsMapLayerProxyModel.All)
        # ignore and not show the sampling layer
        #self.QCBox_RenderFile.setExceptedLayerList([self.detection_layers])
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
            from pca4cd.gui.change_analysis_dialog import ChangeAnalysisDialog
            for view_widget in ChangeAnalysisDialog.view_widgets:
                if view_widget.is_active and view_widget != self:
                    view_widget.render_widget.update_canvas_to(new_extent)

    @pyqtSlot()
    def detection_layer_toggled(self):
        if self.EnableChangeDetection.isChecked():
            self.render_widget.show_detection_layer()
        else:
            self.render_widget.hide_detection_layer()

    @pyqtSlot()
    def open_component_analysis_dialog(self):
        self.change_detection_layer = ComponentAnalysisDialog(view_widget=self)
        if self.change_detection_layer.show():
            # ok button -> accept the new buttons config
            pass
        else:
            # cancel button -> restore the old button config
            pass


# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    plugin_folder, 'ui', 'component_analysis_dialog.ui'))


class ComponentAnalysisDialog(QWidget, FORM_CLASS):
    def __init__(self, view_widget, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)
        self.render_widget.parent_view = self
        self.render_widget.crs = view_widget.render_widget.crs
        # principal component ID
        self.pc_id = view_widget.pc_id
        # edit layer properties
        self.layerStyleEditor.clicked.connect(self.render_widget.layer_style_editor)
        # set layer
        self.render_widget.render_layer(view_widget.render_widget.layer)
        # set name
        self.QLabel_ViewName.setText(view_widget.QLabel_ViewName.text())
        # picker pixel value widget
        self.PickerRangeFrom.clicked.connect(lambda: self.picker_mouse_value(self.RangeChangeFrom))
        self.PickerRangeTo.clicked.connect(lambda: self.picker_mouse_value(self.RangeChangeTo))
        # detection layer
        self.GenerateDetectionLayer.clicked.connect(self.generate_detection_layer)
        # active/deactive
        self.EnableChangeDetection.toggled.connect(self.detection_layer_toggled)

        # statistics
        self.statistics()
        # plot
        self.histogram_plot()

    @pyqtSlot()
    def canvas_changed(self):
        new_extent = self.render_widget.canvas.extent()
        # update canvas for all view activated except this view
        from pca4cd.gui.change_analysis_dialog import ChangeAnalysisDialog
        for view_widget in ChangeAnalysisDialog.view_widgets:
            if view_widget.is_active and view_widget != self:
                view_widget.render_widget.update_canvas_to(new_extent)

    @pyqtSlot()
    def detection_layer_toggled(self):
        if self.EnableChangeDetection.isChecked():
            self.render_widget.show_detection_layer()
        else:
            self.render_widget.hide_detection_layer()

    @pyqtSlot()
    def picker_mouse_value(self, picker_widget):
        self.render_widget.canvas.setMapTool(PickerPointTool(self.render_widget, picker_widget))

    @pyqtSlot()
    @wait_process()
    def generate_detection_layer(self):
        from pca4cd.pca4cd import PCA4CD as pca4cd
        detection_from = self.RangeChangeFrom.value()
        detection_to = self.RangeChangeTo.value()
        pca_layer = self.render_widget.layer
        output_change_layer = os.path.join(pca4cd.tmp_dir, pca_layer.name()+"_detection.tif")

        gdal_calc.Calc(calc="0*logical_and(A<{range_from},A>{range_to})+1*logical_and(A>={range_from},A<={range_to})"
                       .format(range_from=detection_from, range_to=detection_to), A=get_file_path_of_layer(pca_layer),
                       outfile=output_change_layer, type="Byte", NoDataValue=0)

        detection_layer = load_layer_in_qgis(output_change_layer, "raster")
        apply_symbology(detection_layer, [("detection", 1, (255, 255, 0, 255))])

        self.render_widget.set_detection_layer(detection_layer)

    @wait_process()
    def statistics(self):
        from pca4cd.gui.change_analysis_dialog import ChangeAnalysisDialog
        self.stats_eigenvalue.setText("{} ({}%)".format(round(ChangeAnalysisDialog.pca_stats["eigenvals"][self.pc_id-1], 2),
                                                        round(ChangeAnalysisDialog.pca_stats["eigenvals_%"][self.pc_id-1], 2)))

        gdal.AllRegister()
        pca_layer = self.render_widget.layer
        dataset = gdal.Open(get_file_path_of_layer(pca_layer), GA_ReadOnly)
        band = dataset.GetRasterBand(1).ReadAsArray()
        pca_flat = band.flatten()

        self.stats_min.setText(str(round(np.min(pca_flat), 2)))
        self.stats_max.setText(str(round(np.max(pca_flat), 2)))
        self.stats_std.setText(str(round(np.std(pca_flat), 2)))
        self.stats_p25.setText(str(round(np.percentile(pca_flat, 25), 2)))
        self.stats_p50.setText(str(round(np.percentile(pca_flat, 50), 2)))
        self.stats_p75.setText(str(round(np.percentile(pca_flat, 75), 2)))

    @wait_process()
    def histogram_plot(self):
        # config plot
        self.HistogramPlot.setTitle('Histogram of PC {}'.format(self.pc_id))
        self.HistogramPlot.setBackground('w')
        self.HistogramPlot.showGrid(x=True, y=True, alpha=0.2)



        x, y = range(10), range(10)
        self.HistogramPlot.plot(x, y)