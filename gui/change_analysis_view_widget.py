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
from qgis.PyQt.QtCore import QSettings, pyqtSlot, QTimer, Qt
from qgis.core import QgsRaster, QgsVectorLayer, QgsFeature, QgsWkbTypes, edit
from qgis.gui import QgsMapCanvas, QgsMapToolPan, QgsMapTool, QgsRubberBand
from qgis.utils import iface

from pca4cd.libs import gdal_calc
from pca4cd.utils.others_utils import clip_raster_with_shape
from pca4cd.utils.qgis_utils import load_and_select_filepath_in, StyleEditorDialog, get_file_path_of_layer, \
    load_layer_in_qgis, apply_symbology
from pca4cd.utils.system_utils import block_signals_to, wait_process


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
        self.component_analysis_dialog = None
        # init as unactivated render widget for new instances
        self.disable()

    def setup_view_widget(self, crs):
        self.render_widget.parent_view = self
        self.render_widget.crs = crs
        self.detection_layers = None
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
        if not self.component_analysis_dialog:
            self.component_analysis_dialog = ComponentAnalysisDialog(parent_view_widget=self)
        self.component_analysis_dialog.show()


# #### component analysis dialog


class PickerPixelPointTool(QgsMapTool):
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
        self.clean()
        QTimer.singleShot(180, lambda:
            self.render_widget.canvas.setMapTool(self.render_widget.pan_zoom_tool, clean=True))


class PickerAOIPointTool(QgsMapTool):
    def __init__(self, cad):
        QgsMapTool.__init__(self, cad.render_widget.canvas)
        self.cad = cad
        # create the polygon rubber band associated to the current canvas
        self.rubber_band = QgsRubberBand(cad.render_widget.canvas, QgsWkbTypes.PolygonGeometry)
        # set rubber band style
        color = QColor("red")
        color.setAlpha(90)
        self.rubber_band.setColor(color)
        self.rubber_band.setWidth(3)

    def finish_drawing(self):
        self.rubber_band = None
        # restart point tool
        self.clean()
        QTimer.singleShot(180, lambda:
            self.cad.render_widget.canvas.setMapTool(self.cad.render_widget.pan_zoom_tool, clean=True))

    def canvasMoveEvent(self, event):
        if self.rubber_band is None:
            return
        if self.rubber_band and self.rubber_band.numberOfVertices():
            x = event.pos().x()
            y = event.pos().y()
            point = self.cad.render_widget.canvas.getCoordinateTransform().toMapCoordinates(x, y)
            self.rubber_band.removeLastPoint()
            self.rubber_band.addPoint(point)

    def canvasPressEvent(self, event):
        if self.rubber_band is None:
            self.finish_drawing()
            return
        # new point on polygon
        if event.button() == Qt.LeftButton:
            x = event.pos().x()
            y = event.pos().y()
            point = self.cad.render_widget.canvas.getCoordinateTransform().toMapCoordinates(x, y)
            self.rubber_band.addPoint(point)
        # delete the last point
        if event.button() == Qt.RightButton:
            if self.rubber_band and self.rubber_band.numberOfVertices():
                self.rubber_band.removeLastPoint()
                self.canvasMoveEvent(event)

    def canvasDoubleClickEvent(self, event):
        if self.rubber_band is None:
            self.finish_drawing()
            return
        # save polygon
        if event.button() == Qt.LeftButton:
            if self.rubber_band.numberOfVertices() < 3:
                self.finish_drawing()
                return
            self.rubber_band.removeLastPoint()
            new_feature = QgsFeature()
            new_feature.setGeometry(self.rubber_band.asGeometry())
            self.rubber_band = None
            # add the new feature and update the statistics
            self.cad.aoi_changes(new_feature)
            self.finish_drawing()


# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    plugin_folder, 'ui', 'component_analysis_dialog.ui'))


class ComponentAnalysisDialog(QWidget, FORM_CLASS):
    @wait_process()
    def __init__(self, parent_view_widget, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)
        self.parent_view_widget = parent_view_widget
        self.render_widget.parent_view = self
        self.render_widget.crs = parent_view_widget.render_widget.crs
        # principal component ID
        self.pc_id = parent_view_widget.pc_id
        # edit layer properties
        self.layerStyleEditor.clicked.connect(self.render_widget.layer_style_editor)
        # set layer
        self.render_widget.render_layer(parent_view_widget.render_widget.layer)
        self.pc_layer = self.render_widget.layer
        # set name
        self.pc_name = parent_view_widget.QLabel_ViewName.text()
        self.QLabel_ViewName.setText(self.pc_name)
        # picker pixel value widget
        self.PickerRangeFrom.clicked.connect(lambda: self.picker_mouse_value(self.RangeChangeFrom))
        self.PickerRangeTo.clicked.connect(lambda: self.picker_mouse_value(self.RangeChangeTo))
        # detection layer
        self.GenerateDetectionLayer.clicked.connect(self.generate_detection_layer)
        # active/deactive
        self.ShowHideChangeDetection.toggled.connect(self.detection_layer_toggled)
        # init temporal AOI layer
        self.tmp_aoi = QgsVectorLayer("Polygon?crs=" + self.pc_layer.crs().toWkt(), "aoi", "memory")
        # aoi picker
        self.AOI_Picker.clicked.connect(lambda: self.render_widget.canvas.setMapTool(PickerAOIPointTool(self), clean=True))
        # set statistics from combobox
        self.QCBox_StatsLayer.addItems([self.pc_name, "Areas Of Interest"])
        self.QCBox_StatsLayer.currentIndexChanged[str].connect(self.set_statistics)

        # statistics for current principal component
        gdal.AllRegister()
        dataset = gdal.Open(get_file_path_of_layer(self.pc_layer), GA_ReadOnly)
        band = dataset.GetRasterBand(1).ReadAsArray()
        self.pc_data = band.flatten()
        self.set_statistics(stats_for=self.pc_name)
        # init aoi data
        self.aoi_data = np.array([np.nan])
        # init histogram plot
        self.HistogramPlot.setTitle('Histogram')
        self.HistogramPlot.setBackground('w')
        self.HistogramPlot.showGrid(x=True, y=True, alpha=0.3)

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
        if self.ShowHideChangeDetection.isChecked():
            self.render_widget.show_detection_layer()
        else:
            self.render_widget.hide_detection_layer()

    @pyqtSlot()
    def picker_mouse_value(self, picker_widget):
        self.render_widget.canvas.setMapTool(PickerPixelPointTool(self.render_widget, picker_widget), clean=True)

    @pyqtSlot()
    @wait_process()
    def generate_detection_layer(self):
        from pca4cd.pca4cd import PCA4CD as pca4cd
        detection_from = self.RangeChangeFrom.value()
        detection_to = self.RangeChangeTo.value()
        output_change_layer = os.path.join(pca4cd.tmp_dir, self.pc_layer.name()+"_detection.tif")

        gdal_calc.Calc(calc="0*logical_and(A<{range_from},A>{range_to})+1*logical_and(A>={range_from},A<={range_to})"
                       .format(range_from=detection_from, range_to=detection_to), A=get_file_path_of_layer(self.pc_layer),
                       outfile=output_change_layer, type="Byte", NoDataValue=0)

        detection_layer = load_layer_in_qgis(output_change_layer, "raster", False)
        apply_symbology(detection_layer, [("detection", 1, (255, 255, 0, 255))])

        self.render_widget.set_detection_layer(detection_layer)
        self.parent_view_widget.render_widget.set_detection_layer(detection_layer)
        self.ShowHideChangeDetection.setEnabled(True)
        self.ShowHideChangeDetection.setChecked(True)

    @wait_process()
    def set_statistics(self, stats_for=None):
        if stats_for == self.pc_name:
            from pca4cd.gui.change_analysis_dialog import ChangeAnalysisDialog
            self.statistics(self.pc_data, ChangeAnalysisDialog.pca_stats)
            self.histogram_plot(self.pc_data)
            with block_signals_to(self.QCBox_StatsLayer):
                self.QCBox_StatsLayer.setCurrentIndex(0)
        if stats_for == "Areas Of Interest":
            self.statistics(self.aoi_data)
            self.histogram_plot(self.aoi_data)
            with block_signals_to(self.QCBox_StatsLayer):
                self.QCBox_StatsLayer.setCurrentIndex(1)

    def statistics(self, data, pca_stats=None):
        if pca_stats:  # for pca
            self.stats_header.setText("Eigenvalue: {} ({}%)".format(round(pca_stats["eigenvals"][self.pc_id-1], 2),
                                                                    round(pca_stats["eigenvals_%"][self.pc_id-1], 2)))
            self.stats_header.setToolTip("It shows how are the dispersion of the data with respect to its component")
        else:  # for aoi
            self.stats_header.setText("Pixels in AOI: {}".format(round(data.size if data.size > 1 else 0, 2)))
            self.stats_header.setToolTip("")

        self.stats_min.setText(str(round(np.min(data), 2)))
        self.stats_max.setText(str(round(np.max(data), 2)))
        self.stats_std.setText(str(round(np.std(data), 2)))
        self.stats_p25.setText(str(round(np.percentile(data, 25), 2)))
        self.stats_p50.setText(str(round(np.percentile(data, 50), 2)))
        self.stats_p75.setText(str(round(np.percentile(data, 75), 2)))

    def histogram_plot(self, data):
        if data.size <= 1:
            self.HistogramPlot.clear()
            return
        y, x = np.histogram(data, bins=80)
        self.HistogramPlot.clear()
        self.HistogramPlot.plot(x, y, stepMode=True, fillLevel=0, brush=(80, 80, 80))
        self.HistogramPlot.autoRange()

    @wait_process()
    def aoi_changes(self, new_feature):
        """Actions after added each polygon in the AOI"""
        from pca4cd.pca4cd import PCA4CD as pca4cd
        # update AOI
        with edit(self.tmp_aoi):
            self.tmp_aoi.addFeature(new_feature)
        # clip the raster component in AOI for get only the pixel values inside it
        pc_aoi = os.path.join(pca4cd.tmp_dir, self.pc_layer.name() + "_clip_aoi.tif")
        clip_raster_with_shape(self.pc_layer, self.tmp_aoi, pc_aoi)
        gdal.AllRegister()
        dataset = gdal.Open(pc_aoi, GA_ReadOnly)
        band = dataset.GetRasterBand(1).ReadAsArray()
        self.aoi_data = band.flatten()
        self.aoi_data = np.delete(self.aoi_data, np.where(self.aoi_data == 0))
        if self.aoi_data.size == 0:
            self.aoi_data = np.array([np.nan])
        # update statistics and histogram plot
        self.set_statistics(stats_for="Areas Of Interest")
        # update range values using min/max of AOI with decimal adjusted for include in change layer
        self.RangeChangeFrom.setValue(np.floor(np.min(self.aoi_data)*1000)/1000)
        self.RangeChangeTo.setValue(np.ceil(np.max(self.aoi_data)*1000)/1000)
        # auto generate/update the detection layer
        self.generate_detection_layer()

        del dataset, band
        if os.path.isfile(pc_aoi):
            os.remove(pc_aoi)

