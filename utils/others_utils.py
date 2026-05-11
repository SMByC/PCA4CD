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
"""
import os
from osgeo import gdal

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
    from pca4cd.pca4cd import PCA4CD as pca4cd
    target_file = get_file_path_of_layer(target_layer)
    if target_file is None:
        return
    # set the file path for the area of interest
    # check if the shape is a memory layer, then save and used it
    shape_path = get_file_path_of_layer(shape_layer)
    tmp_memory_file = None
    if shape_path and shape_path.is_file():
        shape_file = shape_path
    else:
        tmp_memory_file = pca4cd.tmp_dir / "memory_layer_aoi.gpkg"
        error, msg = QgsVectorFileWriter.writeAsVectorFormat(shape_layer, str(tmp_memory_file), "System", shape_layer.crs(), "GPKG")
        if error != QgsVectorFileWriter.WriterError.NoError:
            raise RuntimeError("Failed to save memory layer to disk: {}".format(msg))
        shape_file = tmp_memory_file

    # clipping in shape
    warp_opts = gdal.WarpOptions(
        options=['--config', 'GDALWARP_IGNORE_BAD_CUTLINE', 'YES'],
        cutlineDSName=str(shape_file),
        cropToCutline=True,
        dstNodata=dst_nodata,
    )
    gdal.Warp(str(out_path), str(target_file), options=warp_opts)

    # clean tmp file
    if tmp_memory_file is not None and tmp_memory_file.is_file():
        os.remove(tmp_memory_file)
