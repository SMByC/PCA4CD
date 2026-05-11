# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PCA4CD
                                 A QGIS plugin
 Principal components analysis for change detection
                              -------------------
        copyright            : (C) 2018-2026 by Xavier Corredor Llano, SMByC
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
 This script initializes the plugin, making it known to QGIS.
"""
import os
import site

from qgis.PyQt.QtWidgets import QMessageBox

from pca4cd.utils import extralibs


def check_dependencies() -> bool:
    """Return True if all required extra libraries are importable."""
    try:
        import dask  # noqa: F401
        import pyqtgraph  # noqa: F401
        return True
    except ImportError:
        return False


def pre_init_plugin() -> None:
    """Add the bundled *extlibs* directory into plugin folder so that extra
    Python packages can be imported before loading the plugin.
    """
    extra_libs_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "extlibs")
    )
    if os.path.isdir(extra_libs_path):
        site.addsitedir(extra_libs_path)
        # Register with pkg_resources when available (removed in Python 3.12+)
        try:
            import pkg_resources  # noqa: F401
            pkg_resources.working_set.add_entry(extra_libs_path)
        except ImportError:
            pass


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load PCA4CD class from file PCA4CD.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    # Attempt to load bundled extra dependencies first
    pre_init_plugin()

    if not check_dependencies():
        # Extra libs missing – download and install them, then retry
        extralibs.install()
        pre_init_plugin()

        if not check_dependencies():
            msg = (
                "Error loading libraries for PCA4CD.\n\n"
                "Read the install instructions here:\n"
                "https://github.com/SMByC/PCA4CD#installation"
            )
            QMessageBox.critical(
                None,
                "PCA4CD: Error loading",
                msg,
                QMessageBox.StandardButton.Ok,
            )

    from .pca4cd import PCA4CD
    return PCA4CD(iface)
