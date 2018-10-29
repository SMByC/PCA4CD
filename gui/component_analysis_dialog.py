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
import pyqtgraph as pg
from PyQt5.QtCore import QTimer, Qt, pyqtSlot
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget
from osgeo import gdal
from osgeo.gdalconst import GA_ReadOnly

from qgis.PyQt import uic
from qgis.core import QgsRaster, QgsWkbTypes, QgsFeature, QgsVectorLayer
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.core import edit

from pca4cd.libs import gdal_calc
from pca4cd.utils.others_utils import clip_raster_with_shape
from pca4cd.utils.qgis_utils import get_file_path_of_layer, load_layer_in_qgis, apply_symbology
from pca4cd.utils.system_utils import wait_process, block_signals_to


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
            self.cad.rubber_bands.append(self.rubber_band)
            self.rubber_band = None
            # add the new feature and update the statistics
            self.cad.aoi_changes(new_feature)
            self.finish_drawing()


# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    plugin_folder, 'ui', 'component_analysis_dialog.ui'))


class ComponentAnalysisDialog(QWidget, FORM_CLASS):
    @wait_process
    def __init__(self, parent_view_widget, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)
        self.is_opened = False
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
        self.aoi_features = QgsVectorLayer("Polygon?crs=" + self.pc_layer.crs().toWkt(), "aoi", "memory")
        # aoi
        self.rubber_bands = []
        self.AOI_Picker.clicked.connect(lambda: self.render_widget.canvas.setMapTool(PickerAOIPointTool(self), clean=True))
        self.DeleteAllAOI.clicked.connect(self.delete_all_aoi)
        # set statistics from combobox
        self.QCBox_StatsLayer.addItems([self.pc_name, "Areas Of Interest"])
        self.QCBox_StatsLayer.currentIndexChanged[str].connect(self.set_statistics)

        # init histogram plot
        self.hist_data = None
        self.hist_bins = {"pc": {"type": "auto", "bins": None}, "aoi": {"type": "auto", "bins": None}}
        self.HistogramPlot.setTitle('Histogram', size='9pt')
        self.HistogramPlot.setBackground('w')
        self.HistogramPlot.showGrid(x=True, y=True, alpha=0.3)
        self.HistogramTypeBins.currentIndexChanged[str].connect(lambda value: self.histogram_plot(bins=value))
        self.HistogramCustomBins.hide()
        self.HistogramCustomBins.valueChanged.connect(lambda value: self.histogram_plot(bins=value))
        # init region and synchronize the region on plot with range values
        self.linear_region = pg.LinearRegionItem(brush=(255, 255, 0, 40))
        self.HistogramPlot.addItem(self.linear_region)
        self.linear_region.sigRegionChanged.connect(self.update_region_from_plot)
        self.RangeChangeFrom.valueChanged.connect(self.update_region_from_values)
        self.RangeChangeTo.valueChanged.connect(self.update_region_from_values)
        # statistics for current principal component
        dataset = gdal.Open(get_file_path_of_layer(self.pc_layer), GA_ReadOnly)
        band = dataset.GetRasterBand(1).ReadAsArray()
        self.pc_data = band.flatten()
        self.set_statistics(stats_for=self.pc_name)
        # init aoi data
        self.aoi_data = np.array([np.nan])

    @pyqtSlot()
    def show(self):
        self.is_opened = True
        self.parent_view_widget.QPBtn_ComponentAnalysisDialog.setText("Opened, click to show")
        super(ComponentAnalysisDialog, self).show()

    def closeEvent(self, event):
        self.is_opened = False
        self.parent_view_widget.QPBtn_ComponentAnalysisDialog.setText("Change detection layer")
        super(ComponentAnalysisDialog, self).closeEvent(event)

    @pyqtSlot()
    def canvas_changed(self):
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
        if self.ShowHideChangeDetection.isChecked():
            self.render_widget.show_detection_layer()
        else:
            self.render_widget.hide_detection_layer()

    @pyqtSlot()
    def picker_mouse_value(self, picker_widget):
        self.render_widget.canvas.setMapTool(PickerPixelPointTool(self.render_widget, picker_widget), clean=True)

    @pyqtSlot()
    @wait_process
    def generate_detection_layer(self):
        from pca4cd.pca4cd import PCA4CD as pca4cd
        detection_from = self.RangeChangeFrom.value()
        detection_to = self.RangeChangeTo.value()
        output_change_layer = os.path.join(pca4cd.tmp_dir, self.pc_layer.name()+"_detection.tif")

        gdal_calc.Calc(calc="0*logical_and(A<{range_from},A>{range_to})+1*logical_and(A>={range_from},A<={range_to})"
                       .format(range_from=detection_from, range_to=detection_to), A=get_file_path_of_layer(self.pc_layer),
                       outfile=output_change_layer, type="Byte")

        detection_layer = load_layer_in_qgis(output_change_layer, "raster", False)
        apply_symbology(detection_layer, [("detection", 1, (255, 255, 0, 255))])

        self.render_widget.set_detection_layer(detection_layer)
        self.parent_view_widget.render_widget.set_detection_layer(detection_layer)
        self.parent_view_widget.EnableChangeDetection.setChecked(True)
        self.ShowHideChangeDetection.setEnabled(True)
        self.ShowHideChangeDetection.setChecked(True)

        # update visibility of change layer in all PC in main analysis dialog Fixme: this should not be necessary
        from pca4cd.gui.main_analysis_dialog import MainAnalysisDialog
        for view_widget in MainAnalysisDialog.view_widgets:
            if view_widget.is_active and view_widget.pc_id is not None:
                view_widget.detection_layer_toggled()

    def set_statistics(self, stats_for=None):
        if stats_for == self.pc_name:
            from pca4cd.gui.main_analysis_dialog import MainAnalysisDialog
            with block_signals_to(self.QCBox_StatsLayer):
                self.QCBox_StatsLayer.setCurrentIndex(0)
            self.statistics(self.pc_data, MainAnalysisDialog.pca_stats)
            self.histogram_plot(data=self.pc_data)
        if stats_for == "Areas Of Interest":
            with block_signals_to(self.QCBox_StatsLayer):
                self.QCBox_StatsLayer.setCurrentIndex(1)
            self.statistics(self.aoi_data)
            self.histogram_plot(data=self.aoi_data)

    @wait_process
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

    @pyqtSlot()
    @wait_process
    def histogram_plot(self, data=None, bins=None):
        # which plot
        stats_for = self.QCBox_StatsLayer.currentText()
        if stats_for == self.pc_name:
            hist_bins = self.hist_bins["pc"]
        if stats_for == "Areas Of Interest":
            hist_bins = self.hist_bins["aoi"]
        # check and set data
        if data is not None:
            self.hist_data = data
        if self.hist_data is None or self.hist_data.size <= 1:
            self.HistogramPlot.clear()
            return
        # histogram bins
        if bins is not None:
            if isinstance(bins, int):
                set_bins = bins
            elif bins == "custom":
                hist_bins["type"] = bins
                self.HistogramCustomBins.show()
                self.HistogramCustomBins.setValue(hist_bins["bins"])
                return
            else:
                self.HistogramCustomBins.hide()
                hist_bins["type"] = bins
                set_bins = bins
        else:  # from set_statistics functions
            if hist_bins["type"] == "custom":
                set_bins = hist_bins["bins"]
                self.HistogramCustomBins.show()
                with block_signals_to(self.HistogramTypeBins):
                    self.HistogramTypeBins.setCurrentIndex(self.HistogramTypeBins.findText("custom"))
                with block_signals_to(self.HistogramCustomBins):
                    self.HistogramCustomBins.setValue(hist_bins["bins"])
            else:
                set_bins = hist_bins["type"]
                self.HistogramCustomBins.hide()
                with block_signals_to(self.HistogramTypeBins):
                    self.HistogramTypeBins.setCurrentIndex(self.HistogramTypeBins.findText(hist_bins["type"]))
        # plot
        y, x = np.histogram(self.hist_data, bins=set_bins)
        self.HistogramPlot.clear()
        self.HistogramPlot.plot(x, y, stepMode=True, fillLevel=0, brush=(80, 80, 80))
        self.HistogramPlot.autoRange()
        self.HistogramPlot.addItem(self.linear_region)
        hist_bins["bins"] = len(y)  # store bins

    @pyqtSlot()
    def update_region_from_plot(self):
        lower, upper = self.linear_region.getRegion()
        self.RangeChangeFrom.setValue(lower)
        self.RangeChangeTo.setValue(upper)

    @pyqtSlot()
    def update_region_from_values(self):
        lower = self.RangeChangeFrom.value()
        upper = self.RangeChangeTo.value()
        self.linear_region.setRegion((lower, upper))

    @wait_process
    def aoi_changes(self, new_feature):
        """Actions after added each polygon in the AOI"""
        from pca4cd.pca4cd import PCA4CD as pca4cd
        # update AOI
        with edit(self.aoi_features):
            self.aoi_features.addFeature(new_feature)
        # clip the raster component in AOI for get only the pixel values inside it
        pc_aoi = os.path.join(pca4cd.tmp_dir, self.pc_layer.name() + "_clip_aoi.tif")
        clip_raster_with_shape(self.pc_layer, self.aoi_features, pc_aoi)
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

    @pyqtSlot()
    @wait_process
    def delete_all_aoi(self):
        # clear/reset all rubber bands
        for rubber_band in self.rubber_bands:
            rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        self.rubber_bands = []
        # remove all features in aoi
        self.aoi_features.dataProvider().truncate()
        # update statistics and histogram plot
        self.aoi_data = np.array([np.nan])
        self.set_statistics(stats_for="Areas Of Interest")
