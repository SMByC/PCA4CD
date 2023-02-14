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
import os
import platform
import site
import pkg_resources


def pre_init_plugin_libs_inside():
    if platform.system() == "Windows":
        extlib_path = 'extlibs_windows'
    if platform.system() == "Darwin":
        extlib_path = 'extlibs_darwin'
    if platform.system() == "Linux":
        extlib_path = 'extlibs_linux'
    extra_libs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), extlib_path))

    if os.path.isdir(extra_libs_path):
        # add to python path
        site.addsitedir(extra_libs_path)
        # pkg_resources doesn't listen to changes on sys.path.
        pkg_resources.working_set.add_entry(extra_libs_path)


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

