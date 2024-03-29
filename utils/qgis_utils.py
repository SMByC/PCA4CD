# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PCA4CD
                                 A QGIS plugin
 Principal components analysis for change detection
                              -------------------
        copyright            : (C) 2018-2023 by Xavier Corredor Llano, SMByC
        email                : xavier.corredor.llano@gmail.com
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
from pathlib import Path

from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.gui import QgsRendererPropertiesDialog, QgsRendererRasterPropertiesWidget
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, Qgis, QgsStyle, QgsMapLayer, QgsRasterShader, \
    QgsColorRampShader, QgsSingleBandPseudoColorRenderer, QgsRasterRange
from qgis.utils import iface


def get_file_path_of_layer(layer):
    if layer and layer.isValid():
        file_path = Path(os.path.realpath(layer.source().split("|layername")[0]))
        return file_path if os.path.exists(file_path) else Path("")
    return None


def valid_file_selected_in(combo_box, combobox_name=False):
    if combo_box.currentLayer() is None:
        return False
    if combo_box.currentLayer().isValid():
        return True
    else:
        if combobox_name:
            iface.messageBar().pushMessage("PCA4CD", "Error, please browse/select a valid file in "
                                           + combobox_name, level=Qgis.Warning)
        combo_box.setCurrentIndex(-1)
        return False


def get_layer_by_name(layer_name):
    layer = QgsProject.instance().mapLayersByName(layer_name)
    if layer:
        return layer[0]


def get_current_file_path_in(combo_box, show_message=True):
    file_path = get_file_path_of_layer(combo_box.currentLayer())
    if file_path.is_file():
        return file_path
    elif show_message:
        iface.messageBar().pushMessage("PCA4CD", "Error, please select a valid file", level=Qgis.Warning)
    return None


def load_and_select_filepath_in(combo_box, file_path):
    filename = os.path.splitext(os.path.basename(file_path))[0]
    layer = get_layer_by_name(filename)
    # load
    if not layer:
        load_layer(file_path)
    # select the sampling file in combobox
    selected_index = combo_box.findText(filename, Qt.MatchFixedString)
    combo_box.setCurrentIndex(selected_index)

    return get_layer_by_name(filename)


def add_layer(layer, add_to_legend=True):
    QgsProject.instance().addMapLayer(layer, add_to_legend)


def load_layer(file_path, name=None, add_to_legend=True):
    file_path = Path(file_path)
    # first unload layer from qgis if exists
    unload_layer(file_path)

    name = name or file_path.stem
    # vector
    qgslayer = QgsVectorLayer(str(file_path), name, "ogr")
    if not qgslayer.isValid():
        # raster
        qgslayer = QgsRasterLayer(str(file_path), name, "gdal")

    # load
    if qgslayer.isValid():
        add_layer(qgslayer, add_to_legend)
    else:
        iface.messageBar().pushMessage("PCA4CD", "Could not load layer: {}".format(file_path))

    return qgslayer


def unload_layer(layer_path):
    layers_loaded = QgsProject.instance().mapLayers().values()
    for layer_loaded in layers_loaded:
        if layer_loaded.isValid() and layer_path.resolve() == get_file_path_of_layer(layer_loaded).resolve():
            QgsProject.instance().removeMapLayer(layer_loaded.id())


# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(Path(plugin_folder, 'ui', 'style_editor.ui'))


class StyleEditorDialog(QDialog, FORM_CLASS):
    def __init__(self, layer, canvas, parent=None):
        QDialog.__init__(self)
        self.setupUi(self)
        self.layer = layer

        self.setWindowTitle("{} - Style Editor".format(self.layer.name()))

        if self.layer.type() == QgsMapLayer.VectorLayer:
            self.StyleEditorWidget = QgsRendererPropertiesDialog(self.layer, QgsStyle(), True, parent)

        if self.layer.type() == QgsMapLayer.RasterLayer:
            self.StyleEditorWidget = QgsRendererRasterPropertiesWidget(self.layer, canvas, parent)

        self.scrollArea.setWidget(self.StyleEditorWidget)

        self.DialogButtons.button(QDialogButtonBox.Cancel).clicked.connect(self.reject)
        self.DialogButtons.button(QDialogButtonBox.Ok).clicked.connect(self.accept)
        self.DialogButtons.button(QDialogButtonBox.Apply).clicked.connect(self.apply)

    def apply(self):
        self.StyleEditorWidget.apply()
        self.layer.triggerRepaint()


def apply_symbology(rlayer, symbology, transparent=None):
    """ Apply classification symbology to raster layer """
    # See: QgsRasterRenderer* QgsSingleBandPseudoColorRendererWidget::renderer()
    # https://github.com/qgis/QGIS/blob/master/src/gui/raster/qgssinglebandpseudocolorrendererwidget.cpp
    # Get raster shader
    raster_shader = QgsRasterShader()
    # Color ramp shader
    color_ramp_shader = QgsColorRampShader()
    # Loop over Fmask values and add to color item list
    color_ramp_item_list = []
    for name, value, color in symbology:
        # Color ramp item - color, label, value
        color_ramp_item = QgsColorRampShader.ColorRampItem(value, QColor(color[0], color[1], color[2], color[3]), name)
        color_ramp_item_list.append(color_ramp_item)

    # After getting list of color ramp items
    color_ramp_shader.setColorRampItemList(color_ramp_item_list)
    # Exact color ramp
    color_ramp_shader.setColorRampType('EXACT')
    # Add color ramp shader to raster shader
    raster_shader.setRasterShaderFunction(color_ramp_shader)
    # Create color renderer for raster layer
    renderer = QgsSingleBandPseudoColorRenderer(rlayer.dataProvider(), 1, raster_shader)
    # Set renderer for raster layer
    rlayer.setRenderer(renderer)

    # Set NoData transparency to layer qgis (temporal)
    if transparent is not None:
        if not isinstance(transparent, list):
            transparent = [transparent]
        nodata = [QgsRasterRange(t, t) for t in transparent]
        if nodata:
            rlayer.dataProvider().setUserNoDataValue(1, nodata)

    # Repaint
    if hasattr(rlayer, 'setCacheImage'):
        rlayer.setCacheImage(None)
    rlayer.triggerRepaint()
