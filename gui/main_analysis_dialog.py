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
import tempfile

from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QGridLayout, QMessageBox

from pca4cd.gui.layer_view_widget import LayerViewWidget

# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    plugin_folder, 'ui', 'main_analysis_dialog.ui'))


class MainAnalysisDialog(QDialog, FORM_CLASS):
    view_widgets = []
    pca_stats = None
    current_sample = None

    def __init__(self, layer_a, layer_b, pca_layers, pca_stats):
        QDialog.__init__(self)
        self.layer_a = layer_a
        self.layer_b = layer_b
        self.pca_layers = pca_layers
        MainAnalysisDialog.pca_stats = pca_stats

        self.setupUi(self)

        # dialog buttons box
        self.CloseButton.clicked.connect(self.closing)
        # return
        self.ReturnToMainDialog.clicked.connect(self.return_to_main_dialog)

        # size of the grid with view render widgets windows
        if self.layer_b is not None:
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
        if self.layer_b is None:
            if len(pca_layers) <= 3:
                grid_rows = 2
                grid_columns = 3
            elif len(pca_layers) <= 6:
                grid_rows = 3
                grid_columns = 3
            elif len(pca_layers) <= 9:
                grid_rows = 4
                grid_columns = 3
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
            if num_view == 3 and self.layer_b is not None:
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
            if not view_widget.QLabel_ViewName.text():
                view_widget.QLabel_ViewName.setPlaceholderText("Auxiliary View")

    def show(self):
        from pca4cd.pca4cd import PCA4CD as pca4cd
        # hide main dialog
        pca4cd.dialog.hide()
        # show dialog
        super(MainAnalysisDialog, self).show()

    def closeEvent(self, event):
        self.closing()
        event.ignore()

    def return_to_main_dialog(self):
        # first prompt
        quit_msg = "Are you sure you want to return to the main dialog? you will lose all the products generated"
        reply = QMessageBox.question(None, 'Return to Compute the Principal Components',
                                     quit_msg, QMessageBox.Yes, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        from pca4cd.pca4cd import PCA4CD as pca4cd
        self.reject(is_ok_to_close=True)
        self.deleteLater()
        pca4cd.removes_temporary_files()
        pca4cd.tmp_dir = tempfile.mkdtemp()
        # recover the main dialog
        pca4cd.dialog.show()

    def closing(self):
        """
        Do this before close the dialog
        """
        # first prompt
        quit_msg = "Are you sure you want close the PCA4CD plugin?"
        reply = QMessageBox.question(None, 'Closing the PCA4CD plugin',
                                     quit_msg, QMessageBox.Yes, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        from pca4cd.pca4cd import PCA4CD as pca4cd

        # clear and close main dialog
        pca4cd.dialog.close()
        # for components analysis opened
        for view_widget in MainAnalysisDialog.view_widgets:
            if view_widget.component_analysis_dialog and view_widget.component_analysis_dialog.is_opened:
                view_widget.component_analysis_dialog.deleteLater()

        self.reject(is_ok_to_close=True)

    def reject(self, is_ok_to_close=False):
        if is_ok_to_close:
            super(MainAnalysisDialog, self).reject()

