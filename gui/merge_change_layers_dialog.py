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

from qgis.gui import QgsFileWidget
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog

# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    plugin_folder, 'ui', 'merge_change_layers_dialog.ui'))


class MergeChangeLayersDialog(QDialog, FORM_CLASS):
    merged_file_path = None

    def __init__(self, activated_ids, suggested_filename):
        QDialog.__init__(self)
        self.setupUi(self)
        self.LayersToProcess.setText(" - ".join(activated_ids))
        self.MergedFileWidget.setDialogTitle("Save the merged layer")
        self.MergedFileWidget.setFilter("Raster files (*.tif)")
        self.MergedFileWidget.setStorageMode(QgsFileWidget.SaveFile)
        if MergeChangeLayersDialog.merged_file_path is not None:
            self.MergedFileWidget.setFilePath(MergeChangeLayersDialog.merged_file_path)
        else:
            self.MergedFileWidget.setFilePath(suggested_filename)

        if len(activated_ids) == 1:
            self.LabelMergedMethod.setEnabled(False)
            self.MergedMethod.setEnabled(False)
            self.LabelMergedFileWidget.setText("Save the change layer")
            self.MergedFileWidget.setDialogTitle("Save the change layer")
