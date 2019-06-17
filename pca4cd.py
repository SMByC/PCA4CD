# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PCA4CD
                                 A QGIS plugin
 Principal components analysis for change detection
                              -------------------
        copyright            : (C) 2018-2019 by Xavier Corredor Llano, SMByC
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

import os.path
import shutil
import tempfile
from pathlib import Path

from qgis.PyQt.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.utils import iface

# Initialize Qt resources from file resources.py
from .resources import *

from pca4cd.gui.pca4cd_dialog import PCA4CDDialog
from pca4cd.gui.about_dialog import AboutDialog
from pca4cd.utils.qgis_utils import unload_layer


class PCA4CD:
    """QGIS Plugin Implementation."""
    dialog = None
    tmp_dir = None

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = Path(self.plugin_dir, 'i18n', 'PCA4CD_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        self.menu_name_plugin = self.tr("PCA4CD - PCA for change detection")
        self.pluginIsActive = False
        PCA4CD.dialog = None

        self.about_dialog = AboutDialog()

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('PCA4CD', message)

    def initGui(self):
        ### Main dialog menu
        # Create action that will start plugin configuration
        icon_path = ':/plugins/pca4cd/icons/pca4cd.svg'
        self.dockable_action = QAction(QIcon(icon_path), "PCA4CD", self.iface.mainWindow())
        # connect the action to the run method
        self.dockable_action.triggered.connect(self.run)
        # Add toolbar button and menu item
        self.iface.addToolBarIcon(self.dockable_action)
        self.iface.addPluginToMenu(self.menu_name_plugin, self.dockable_action)

        # Plugin info
        # Create action that will start plugin configuration
        icon_path = ':/plugins/pca4cd/icons/about.svg'
        self.about_action = QAction(QIcon(icon_path), self.tr('About'), self.iface.mainWindow())
        # connect the action to the run method
        self.about_action.triggered.connect(self.about)
        # Add toolbar button and menu item
        self.iface.addPluginToMenu(self.menu_name_plugin, self.about_action)

    def about(self):
        self.about_dialog.show()

    #--------------------------------------------------------------------------

    def run(self):
        """Run method that loads and starts the plugin"""

        if not self.pluginIsActive:
            self.pluginIsActive = True

            # dialog may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if PCA4CD.dialog is None:
                PCA4CD.dialog = PCA4CDDialog()

            # init tmp dir for all process and intermediate files
            PCA4CD.tmp_dir = Path(tempfile.mkdtemp())
            # connect to provide cleanup on closing of dialog
            PCA4CD.dialog.closingPlugin.connect(self.onClosePlugin)

            # show the dialog
            PCA4CD.dialog.show()
            # Run the dialog event loop
            result = PCA4CD.dialog.exec_()
            # See if OK was pressed
            if result:
                # Do something useful here - delete the line containing pass and
                # substitute with your code.
                pass
        else:
            # an instance of PCA4CD is already created
            # brings that instance to front even if it is minimized
            if hasattr(PCA4CD.dialog, "main_analysis_dialog") and PCA4CD.dialog.main_analysis_dialog:  # main dialog
                PCA4CD.dialog.main_analysis_dialog.setWindowState(PCA4CD.dialog.main_analysis_dialog.windowState()
                                                                  & ~Qt.WindowMinimized | Qt.WindowActive)
                PCA4CD.dialog.main_analysis_dialog.raise_()
                PCA4CD.dialog.main_analysis_dialog.activateWindow()
            else:  # the init dialog
                PCA4CD.dialog.setWindowState(PCA4CD.dialog.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
                PCA4CD.dialog.raise_()
                PCA4CD.dialog.activateWindow()

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin is closed"""

        self.removes_temporary_files()

        # disconnects
        PCA4CD.dialog.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dialog is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        PCA4CD.dialog.close()
        PCA4CD.dialog = None

        self.pluginIsActive = False

        from qgis.utils import reloadPlugin
        reloadPlugin("PCA4CD - PCA for change detection")

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        self.removes_temporary_files()
        # Remove the plugin menu item and icon
        self.iface.removePluginMenu(self.menu_name_plugin, self.dockable_action)
        self.iface.removePluginMenu(self.menu_name_plugin, self.about_action)
        self.iface.removeToolBarIcon(self.dockable_action)

        if PCA4CD.dialog:
            PCA4CD.dialog.close()

    @staticmethod
    def removes_temporary_files():
        if not PCA4CD.dialog:
            return
        # unload all layers instances from Qgis saved in tmp dir
        if PCA4CD.tmp_dir and PCA4CD.tmp_dir.is_dir():
            for file_tmp in PCA4CD.tmp_dir.glob("*"):
                unload_layer(file_tmp)

        # clear PCA4CD.tmp_dir
        if PCA4CD.tmp_dir and os.path.isdir(PCA4CD.tmp_dir):
            shutil.rmtree(PCA4CD.tmp_dir, ignore_errors=True)
        PCA4CD.tmp_dir = None

        # clear qgis main canvas
        iface.mapCanvas().clearCache()
        iface.mapCanvas().refresh()

