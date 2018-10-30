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
from pathlib import Path
from subprocess import call

from qgis.core import QgsVectorFileWriter

from pca4cd.utils.qgis_utils import get_file_path_of_layer


def mask(input_list, boolean_mask):
    """Apply boolean mask to input list

    Args:
        input_list (list): Input list for apply mask
        boolean_mask (list): The boolean mask list

    Examples:
        >>> mask(['A','B','C','D'], [1,0,1,0])
        ['A', 'C']
    """
    return [i for i, b in zip(input_list, boolean_mask) if b]


def clip_raster_with_shape(target_layer, shape_layer, out_path, dst_nodata=None):
    target_file = get_file_path_of_layer(target_layer)
    # set the nodata
    dst_nodata = "-dstnodata {}".format(dst_nodata) if dst_nodata is not None else ""
    # set the file path for the area of interest
    # check if the shape is a memory layer, then save and used it
    if get_file_path_of_layer(shape_layer).startswith("memory"):
        tmp_memory_file = Path(tempfile.gettempdir(), "memory_layer_aoi.gpkg")
        QgsVectorFileWriter.writeAsVectorFormat(shape_layer, str(tmp_memory_file), "System", shape_layer.crs(), "GPKG")
        shape_file = tmp_memory_file
    else:
        shape_file = get_file_path_of_layer(shape_layer)

    # clipping in shape
    return_code = call('gdalwarp --config GDALWARP_IGNORE_BAD_CUTLINE YES -cutline "{}" {} "{}" "{}"'
                       .format(shape_file, dst_nodata, target_file, out_path), shell=True)

    # clean tmp file
    if get_file_path_of_layer(shape_layer).startswith("memory") and tmp_memory_file.is_file():
        os.remove(tmp_memory_file)

    if return_code == 0:  # successfully
        return True
    else:
        return False

