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


def pre_init_plugin_libs_inside():
    extra_libs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "extlibs"))

    if os.path.isdir(extra_libs_path):
        # add to python path
        site.addsitedir(extra_libs_path)
        # keep pkg_resources working set in sync if it is in use
        try:
            import pkg_resources
            pkg_resources.working_set.add_entry(extra_libs_path)
        except ImportError:
            pass


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load PCA4CD class from file PCA4CD.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    # load/install extra python dependencies
    pre_init_plugin_libs_inside()

    # start
    from .pca4cd import PCA4CD
    return PCA4CD(iface)
