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
import functools
import traceback
import os, sys, subprocess

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication, QMessageBox
from qgis.PyQt.QtGui import QCursor
from qgis.core import QgsMessageLog, Qgis
from qgis.utils import iface


def error_handler(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # restore mouse
            QApplication.restoreOverrideCursor()
            QApplication.processEvents()
            # message in status bar
            msg_error = "An error has occurred in PCA4CD plugin. " \
                        "See more in Qgis log messages panel."
            iface.messageBar().pushMessage("PCA4CD", msg_error,
                                           level=Qgis.Critical, duration=10)
            # message in log
            msg_error = "\n################## ERROR IN PCA4CD PLUGIN:\n"
            msg_error += traceback.format_exc()
            msg_error += "\nPlease report the error in:\n" \
                         "\thttps://bitbucket.org/smbyc/qgisplugin-pca4cd/issues"
            msg_error += "\n################## END REPORT"
            QgsMessageLog.logMessage(msg_error)
    return wrapper


def wait_process(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # mouse wait
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        # do
        obj_returned = func(*args, **kwargs)
        # restore mouse
        QApplication.restoreOverrideCursor()
        QApplication.processEvents()
        # finally return the object by f
        return obj_returned
    return wrapper


def open_file(filename):
    """Open a file with the standard application"""
    filename = os.path.abspath(filename)

    if sys.platform == "linux" or sys.platform == "linux2":
        # Linux
        subprocess.call(["xdg-open", filename])
    elif sys.platform == "darwin":
        # OS X
        subprocess.call(["open", filename])
    elif sys.platform == "win32":
        # Windows
        os.startfile(filename)


class block_signals_to(object):
    """Block all signals emits from specific QT object"""
    def __init__(self, object_to_block):
        self.object_to_block = object_to_block

    def __enter__(self):
        # block
        self.object_to_block.blockSignals(True)

    def __exit__(self, type, value, traceback):
        # unblock
        self.object_to_block.blockSignals(False)


def external_deps(deps):
    # https://gis.stackexchange.com/questions/196002/development-of-a-plugin-which-depends-on-an-external-python-library

    deps_not_installed = []
    for dependency in deps:
        try:
            __import__(dependency)
        except:
            deps_not_installed.append(dependency)

    if deps_not_installed:
        msg_info = QMessageBox()
        msg_info.setIcon(QMessageBox.Information)
        msg_info.setWindowTitle("PCA4CD plugin dependencies")
        msg_info.setText("installing python dependencies")
        msg_info.open()

        for dependency in deps_not_installed:
            msg_info.setText("installing python dependencies: {}".format(dependency))
            QApplication.processEvents()
            status = subprocess.call([sys.executable, '-m', 'pip', 'install', dependency, '--user'])
            if status != 0:
                msg_info.close()
                QMessageBox.warning(None, "PCA4CD plugin", "Error installing python dependencies for PCA4CD plugin: {}"
                                    .format(dependency))
                return False

        msg_info.close()

    return True
