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
 This script initializes the plugin, making it known to QGIS.
"""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.utils import iface

from pca4cd.utils.extra_deps import load_install_extra_deps, WaitDialog


def pre_init_plugin():
    app = QCoreApplication.instance()
    parent = iface.mainWindow()
    dialog = None
    log = ''
    try:
        for msg_type, msg_val in load_install_extra_deps():
            app.processEvents()
            if msg_type == 'log':
                log += msg_val
            elif msg_type == 'needs_install':
                dialog = WaitDialog(parent, 'PCA4CD - installing dependencies')
            elif msg_type == 'install_done':
                dialog.accept()
    except Exception as e:
        if dialog:
            dialog.accept()
        QMessageBox.critical(parent, 'PCA4CD - installing dependencies',
                             'An error occurred during the installation of Python packages. ' +
                             'Click on "Stack Trace" in the QGIS message bar for details.')
        raise RuntimeError('\nPCA4CD: Error installing Python packages. Read install instruction: '
                           'https://smbyc.bitbucket.io/qgisplugins/pca4cd\nLog:\n' + log) from e


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load PCA4CD class from file PCA4CD.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    # load/install extra python dependencies
    pre_init_plugin()

    # start
    from .pca4cd import PCA4CD
    return PCA4CD(iface)

