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
import configparser
import webbrowser

from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, pyqtSlot
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog, QDockWidget
from qgis.core import QgsProject, QgsVectorFileWriter, QgsMapLayerProxyModel, Qgis, QgsUnitTypes
from qgis.utils import iface

from pca4cd.gui.about_dialog import AboutDialog

# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    plugin_folder, 'ui', 'pca4cd_dockwidget.ui'))

cfg = configparser.ConfigParser()
cfg.read(os.path.join(plugin_folder, 'metadata.txt'))
VERSION = cfg.get('general', 'version')
HOMEPAGE = cfg.get('general', 'homepage')


class PCA4CDDockWidget(QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()
    dockwidget = None

    def __init__(self, parent=None):
        """Constructor."""
        super(PCA4CDDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.setup_gui()
        # tmp dir for all process and intermediate files
        self.tmp_dir = tempfile.mkdtemp()
        # save instance
        PCA4CDDockWidget.dockwidget = self

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def setup_gui(self):
        # ######### plugin info ######### #
        self.about_dialog = AboutDialog()
        self.QPBtn_PluginInfo.setText("v{}".format(VERSION))
        self.QPBtn_PluginInfo.clicked.connect(self.about_dialog.show)
        self.QPBtn_PluginDocs.clicked.connect(lambda: webbrowser.open("https://smbyc.bitbucket.io/qgisplugins/pca4cd"))
