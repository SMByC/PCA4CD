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
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QGridLayout

from pca4cd.gui.layer_view_widget import LayerViewWidget

# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    plugin_folder, 'ui', 'main_analysis_dialog.ui'))


class MainAnalysisDialog(QDialog, FORM_CLASS):
    is_opened = False
    view_widgets = []
    pca_stats = None
    current_sample = None
    instance = None

    def __init__(self, layer_a, layer_b, pca_layers, pca_stats):
        QDialog.__init__(self)
        self.layer_a = layer_a
        self.layer_b = layer_b
        self.pca_layers = pca_layers
        MainAnalysisDialog.pca_stats = pca_stats

        self.setupUi(self)
        MainAnalysisDialog.instance = self

        # dialog buttons box
        self.closeButton.rejected.connect(self.closing)
        # disable enter action
        self.closeButton.button(QDialogButtonBox.Ok).setAutoDefault(False)
        self.closeButton.button(QDialogButtonBox.Discard).setAutoDefault(False)

        # size of the grid with view render widgets windows
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

        # configure the views layout
        views_layout = QGridLayout()
        views_layout.setSpacing(0)
        views_layout.setMargin(0)
        view_widgets = []
        for row in range(grid_rows):
            for column in range(grid_columns):
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
            view_widget.setup_view_widget(crs=self.layer_a.crs())
        # set views
        for num_view, view_widget in enumerate(MainAnalysisDialog.view_widgets, start=1):
            if num_view == 2:
                view_widget.QLabel_ViewName.setText("Layer A")
                file_index = view_widget.QCBox_RenderFile.findText(self.layer_a.name(), Qt.MatchFixedString)
                view_widget.QCBox_RenderFile.setCurrentIndex(file_index)
            if num_view == 3:
                view_widget.QLabel_ViewName.setText("Layer B")
                file_index = view_widget.QCBox_RenderFile.findText(self.layer_b.name(), Qt.MatchFixedString)
                view_widget.QCBox_RenderFile.setCurrentIndex(file_index)
            if grid_columns < num_view <= len(self.pca_layers)+grid_columns:
                pc_id = num_view-grid_columns
                view_widget.pc_id = pc_id
                view_widget.QLabel_ViewName.setText("Principal Component {}".format(pc_id))
                file_index = view_widget.QCBox_RenderFile.findText(self.pca_layers[num_view-grid_columns-1].name(), Qt.MatchFixedString)
                view_widget.WidgetDetectionLayer.setEnabled(True)
                view_widget.QCBox_RenderFile.setCurrentIndex(file_index)
                view_widget.QCBox_RenderFile.setEnabled(False)
                view_widget.QCBox_browseRenderFile.setEnabled(False)
            else:
                view_widget.EnableChangeDetection.setToolTip("Only for principal components")
                view_widget.QPBtn_ComponentAnalysisDialog.setToolTip("Only for principal components")

    def show(self):
        from pca4cd.pca4cd import PCA4CD as pca4cd
        MainAnalysisDialog.is_opened = True
        # adjust some objects in the dockwidget
        pca4cd.dockwidget.QGBox_InputData.setDisabled(True)
        pca4cd.dockwidget.QGBox_PrincipalComponents.setDisabled(True)
        pca4cd.dockwidget.QPBtn_OpenChangeAnalysisDialog.setText("Analysis dialog is opened, click to show")
        # show dialog
        super(MainAnalysisDialog, self).show()

    def closeEvent(self, event):
        self.closing()
        event.ignore()

    def closing(self):
        """
        Do this before close the dialog
        """
        from pca4cd.pca4cd import PCA4CD as pca4cd

        MainAnalysisDialog.is_opened = False
        # adjust some objects in the dockwidget
        pca4cd.dockwidget.QGBox_InputData.setEnabled(True)
        pca4cd.dockwidget.QGBox_PrincipalComponents.setEnabled(True)
        pca4cd.dockwidget.QPBtn_OpenChangeAnalysisDialog.setText("Components Analysis")
        self.reject(is_ok_to_close=True)

    def reject(self, is_ok_to_close=False):
        if is_ok_to_close:
            super(MainAnalysisDialog, self).reject()

