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
import tempfile

from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QTableWidgetItem, QSplitter, QColorDialog, QDialog, QDialogButtonBox, QPushButton
from qgis.PyQt.QtGui import QColor, QIcon
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, Qgis, QgsProject, QgsUnitTypes

from pca4cd.utils.qgis_utils import valid_file_selected_in, get_current_file_path_in, \
    load_and_select_filepath_in
from pca4cd.utils.system_utils import open_file, block_signals_to
from pca4cd.gui.change_analysis_view_widget import ChangeAnalysisViewWidget

# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    plugin_folder, 'ui', 'change_analysis_dialog.ui'))


class ChangeAnalysisDialog(QDialog, FORM_CLASS):
    is_opened = False
    view_widgets = []
    current_sample = None
    instance = None

    def __init__(self, layer_a, layer_b, pca_layers):
        QDialog.__init__(self)
        self.layer_a = layer_a
        self.layer_b = layer_b
        self.pca_layers = pca_layers
        self.setupUi(self)
        ChangeAnalysisDialog.instance = self

        # dialog buttons box
        self.closeButton.rejected.connect(self.closing)
        # disable enter action
        self.closeButton.button(QDialogButtonBox.Ok).setAutoDefault(False)
        self.closeButton.button(QDialogButtonBox.Discard).setAutoDefault(False)

        # create dynamic size of the view render widgets windows
        # inside the grid with columns x rows divide by splitters
        grid_columns = [2]
        if len(pca_layers) <= 4:
            grid_rows = 2
            grid_columns.append(len(pca_layers))
        elif len(pca_layers) <= 6:
            grid_rows = 3
            grid_columns += [3, 3]
        elif len(pca_layers) <= 8:
            grid_rows = 3
            grid_columns += [4, 4]
        elif len(pca_layers) <= 9:
            grid_rows = 4
            grid_columns += [3, 3, 3]
        elif len(pca_layers) <= 12:
            grid_rows = 4
            grid_columns += [4, 4, 4]
        elif len(pca_layers) <= 15:
            grid_rows = 4
            grid_columns += [5, 5, 5]
        elif len(pca_layers) <= 16:
            grid_rows = 5
            grid_columns += [4, 4, 4, 4]
        elif len(pca_layers) <= 20:
            grid_rows = 5
            grid_columns += [5, 5, 5, 5]

        h_splitters = []
        view_widgets = []
        for row in range(grid_rows):
            splitter = QSplitter(Qt.Horizontal)
            for column in range(grid_columns[row]):
                new_view_widget = ChangeAnalysisViewWidget()
                splitter.addWidget(new_view_widget)
                h_splitters.append(splitter)
                view_widgets.append(new_view_widget)
        v_splitter = QSplitter(Qt.Vertical)
        for splitter in h_splitters:
            v_splitter.addWidget(splitter)
        # add to change analysis dialog
        self.widget_view_windows.layout().addWidget(v_splitter)
        # save instances
        ChangeAnalysisDialog.view_widgets = view_widgets
        # setup view widget
        [view_widget.setup_view_widget(crs=self.layer_a.crs()) for view_widget in ChangeAnalysisDialog.view_widgets]
        for idx, view_widget in enumerate(ChangeAnalysisDialog.view_widgets):
            view_widget.id = idx
        # set views
        for num_view, view_widget in enumerate(ChangeAnalysisDialog.view_widgets, start=1):
            if num_view == 1:
                view_widget.QLabel_ViewName.setText("Layer A")
                file_index = view_widget.QCBox_RenderFile.findText(self.layer_a.name(), Qt.MatchFixedString)
                view_widget.QCBox_RenderFile.setCurrentIndex(file_index)
                view_widget.widget_rangeChangeDetection.setVisible(False)
            if num_view == 2:
                view_widget.QLabel_ViewName.setText("Layer B")
                file_index = view_widget.QCBox_RenderFile.findText(self.layer_b.name(), Qt.MatchFixedString)
                view_widget.QCBox_RenderFile.setCurrentIndex(file_index)
                view_widget.widget_rangeChangeDetection.setVisible(False)
            if 2 < num_view <= len(self.pca_layers)+2:
                view_widget.QLabel_ViewName.setText("Principal Component {}".format(num_view-2))
                file_index = view_widget.QCBox_RenderFile.findText(self.pca_layers[num_view-3].name(), Qt.MatchFixedString)
                view_widget.QCBox_RenderFile.setCurrentIndex(file_index)

    def show(self):
        from pca4cd.gui.pca4cd_dockwidget import PCA4CDDockWidget as pca4cd
        ChangeAnalysisDialog.is_opened = True
        # adjust some objects in the dockwidget
        pca4cd.dockwidget.QGBox_InputData.setDisabled(True)
        pca4cd.dockwidget.QGBox_PrincipalComponents.setDisabled(True)
        pca4cd.dockwidget.QPBtn_OpenChangeAnalysisDialog.setText("Analysis dialog is opened, click to show")

        super(ChangeAnalysisDialog, self).show()

    def closeEvent(self, event):
        self.closing()
        event.ignore()

    def closing(self):
        """
        Do this before close the dialog
        """
        from pca4cd.gui.pca4cd_dockwidget import PCA4CDDockWidget as pca4cd

        ChangeAnalysisDialog.is_opened = False
        # adjust some objects in the dockwidget
        pca4cd.dockwidget.QGBox_InputData.setEnabled(True)
        pca4cd.dockwidget.QGBox_PrincipalComponents.setEnabled(True)
        pca4cd.dockwidget.QPBtn_OpenChangeAnalysisDialog.setText("Components Analysis")
        self.reject(is_ok_to_close=True)

    def reject(self, is_ok_to_close=False):
        if is_ok_to_close:
            super(ChangeAnalysisDialog, self).reject()

