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
import functools
import traceback
import os, sys, subprocess

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication, QPushButton, QMessageBox
from qgis.PyQt.QtGui import QCursor
from qgis.core import Qgis
from qgis.utils import iface


def error_handler(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as err:
            # restore mouse
            QApplication.restoreOverrideCursor()
            QApplication.processEvents()

            # select the message bar
            from pca4cd.pca4cd import PCA4CD as pca4cd
            if hasattr(pca4cd.dialog, "main_analysis_dialog") and pca4cd.dialog.main_analysis_dialog:
                msg_bar = pca4cd.dialog.main_analysis_dialog.MsgBar
            else:
                msg_bar = iface.messageBar()

            msg_bar.clearWidgets()

            # message in status bar with details
            def details_message_box(error, more_details):
                msgBox = QMessageBox()
                msgBox.setWindowTitle("PCA4CD - Error handler")
                msgBox.setText("<i>{}</i>".format(error))
                msgBox.setInformativeText("If you consider this as an error of PCA4CD, report it in "
                                          "<a href='https://github.com/SMByC/PCA4CD/issues'>issue tracker</a>")
                msgBox.setDetailedText(more_details)
                msgBox.setTextFormat(Qt.RichText)
                msgBox.setStandardButtons(QMessageBox.Ok)
                msgBox.exec()
                del msgBox

            msg_error = "Ups! an error has occurred in PCA4CD plugin"
            widget = msg_bar.createMessage("PCA4CD", msg_error)
            error = err
            more_details = traceback.format_exc()

            button = QPushButton(widget)
            button.setText("Show details...")
            button.pressed.connect(lambda: details_message_box(error, more_details))
            widget.layout().addWidget(button)

            msg_bar.pushWidget(widget, level=Qgis.Warning, duration=20)

    return wrapper


def wait_process(func):
    @error_handler
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

