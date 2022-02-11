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
from pathlib import Path
import numpy as np
import dask
from osgeo import gdal
from dask import array as da
from multiprocessing.pool import ThreadPool
from subprocess import call

from pca4cd.utils.system_utils import wait_process


@wait_process
def pca(A, B, n_pc, estimator_matrix, out_dir, n_threads, block_size, nodata=None):
    """Calculate the principal components for the vertical stack A or with
    combinations of the stack B

    :param A: first input raster data (fists period)
    :param B: second input raster data (second period) or None
    :param n_pc: number of principal components to output
    :param estimator_matrix: pca with correlation of covariance
    :param out_dir: directory to save the outputs
    :return: pca files list and statistics
    """
    # init dask as threads (shared memory is required)
    dask.config.set(pool=ThreadPool(n_threads))

    raw_image = []
    nodata_mask = None
    src_ds_A = gdal.Open(str(A), gdal.GA_ReadOnly)
    src_ds_B = None
    for band in range(src_ds_A.RasterCount):
        ds = src_ds_A.GetRasterBand(band + 1).ReadAsArray().flatten().astype(np.float32)
        if np.isnan(nodata):
            nodata_mask = np.isnan(ds) if nodata_mask is None else np.logical_or(nodata_mask, np.isnan(ds))
        elif nodata is not None:
            nodata_mask = ds==nodata if nodata_mask is None else np.logical_or(nodata_mask, ds==nodata)
        raw_image.append(ds)
    if B:
        src_ds_B = gdal.Open(str(B), gdal.GA_ReadOnly)
        for band in range(src_ds_B.RasterCount):
            ds = src_ds_B.GetRasterBand(band + 1).ReadAsArray().flatten().astype(np.float32)
            if np.isnan(nodata):
                nodata_mask = np.logical_or(nodata_mask, np.isnan(ds))
            elif nodata is not None:
                nodata_mask = np.logical_or(nodata_mask, ds==nodata)
            raw_image.append(ds)

    # pair-masking data, let only the valid data across all dimensions/bands
    if nodata is not None:
        raw_image = [b[~nodata_mask] for b in raw_image]
    # flat each dimension (bands)
    flat_dims = da.vstack(raw_image).rechunk((1, block_size ** 2))
    # bands
    n_bands = flat_dims.shape[0]

    ########
    # compute the mean of each band, in order to center the matrix.
    band_mean = []
    for i in range(n_bands):
        band_mean.append(dask.delayed(np.mean)(flat_dims[i]))
    band_mean = dask.compute(*band_mean)

    ########
    # compute the matrix correlation/covariance
    estimation_matrix = np.empty((n_bands, n_bands))
    if estimator_matrix == "Correlation":
        for i in range(n_bands):
            deviation_scores_band_i = flat_dims[i] - band_mean[i]
            for j in range(i, n_bands):
                deviation_scores_band_j = flat_dims[j] - band_mean[j]
                estimation_matrix[j][i] = estimation_matrix[i][j] = \
                    da.corrcoef(deviation_scores_band_i, deviation_scores_band_j)[0][1]
    if estimator_matrix == "Covariance":
        for i in range(n_bands):
            deviation_scores_band_i = flat_dims[i] - band_mean[i]
            for j in range(i, n_bands):
                deviation_scores_band_j = flat_dims[j] - band_mean[j]
                estimation_matrix[j][i] = estimation_matrix[i][j] = \
                    da.cov(deviation_scores_band_i, deviation_scores_band_j)[0][1]
    # free mem
    del raw_image, flat_dims, ds

    if estimation_matrix[~np.isnan(estimation_matrix)].size == 0:
        return False, False

    ########
    # calculate eigenvectors & eigenvalues of the matrix
    # use 'eigh' rather than 'eig' since estimation_matrix
    # is symmetric, the performance gain is substantial
    eigenvals, eigenvectors = np.linalg.eigh(estimation_matrix)

    # sort eigenvalue in decreasing order
    idx_eigenvals = np.argsort(eigenvals)[::-1]
    eigenvectors = eigenvectors[:,idx_eigenvals]
    # sort eigenvectors according to same index
    eigenvals = eigenvals[idx_eigenvals]
    # select the first n eigenvectors (n is desired dimension
    # of rescaled data array, or dims_rescaled_data)
    eigenvectors = eigenvectors[:, :n_pc]

    ########
    # save the principal components separated in tif images

    def get_raw_band_from_stack(band):
        if band < src_ds_A.RasterCount:
            return src_ds_A.GetRasterBand(band + 1).ReadAsArray().flatten().astype(np.float32)
        if band >= src_ds_A.RasterCount:
            return src_ds_B.GetRasterBand(band - src_ds_A.RasterCount + 1).ReadAsArray().flatten().astype(np.float32)

    pca_files = []
    for i in range(n_pc):
        pc = 0
        for j in range(n_bands):
            pc = pc + eigenvectors[j, i] * (get_raw_band_from_stack(j) - band_mean[j])

        if nodata is not None:
            pc[nodata_mask] = nodata
        pc = pc.reshape((src_ds_A.RasterYSize, src_ds_A.RasterXSize))
        # save component as file
        tmp_pca_file = Path(out_dir) / 'pc_{}.tif'.format(i+1)
        driver = gdal.GetDriverByName("GTiff")
        out_pc = driver.Create(str(tmp_pca_file), src_ds_A.RasterXSize, src_ds_A.RasterYSize, 1, gdal.GDT_Float32)
        pcband = out_pc.GetRasterBand(1)
        if nodata is not None:
            pcband.SetNoDataValue(nodata)
        pcband.WriteArray(pc)
        # set projection and geotransform
        if src_ds_A.GetGeoTransform() is not None:
            out_pc.SetGeoTransform(src_ds_A.GetGeoTransform())
        if src_ds_A.GetProjection() is not None:
            out_pc.SetProjection(src_ds_A.GetProjection())
        out_pc.FlushCache()
        del pc, pcband, out_pc

        pca_files.append(tmp_pca_file)

    # free mem
    del src_ds_A, nodata_mask

    # compute the pyramids for each pc image
    for pca_file in pca_files:
        call('gdaladdo -q --config BIGTIFF_OVERVIEW YES "{}"'.format(pca_file), shell=True)

    ########
    # pca statistics
    pca_stats = {}
    pca_stats["eigenvals"] = eigenvals
    pca_stats["eigenvals_%"] = eigenvals*100/n_bands
    pca_stats["eigenvectors"] = eigenvectors

    return pca_files, pca_stats

