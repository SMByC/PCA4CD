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
import numpy as np
import dask
import rasterio
from multiprocessing.pool import ThreadPool
from dask_rasterio import read_raster, write_raster
from subprocess import call

from pca4cd.utils.system_utils import wait_process


@wait_process
def pca(A, B, n_pc, estimator_matrix, out_dir, n_threads, block_size):
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

    def get_profile(path):
        """Get geospatial metadata profile such as projections, pixel sizes, etc"""
        with rasterio.open(path) as src:
            return src.profile.copy()

    if B is not None:
        raw_image_a = read_raster(A, block_size=block_size)
        raw_image_b = read_raster(B, block_size=block_size)
        raw_image = dask.array.vstack((raw_image_a, raw_image_b))
    else:
        raw_image = read_raster(A, block_size=block_size)

    # flat each dimension (bands)
    flat_dims = raw_image.reshape((raw_image.shape[0], raw_image.shape[1] * raw_image.shape[2]))

    n_bands = raw_image.shape[0]

    ########
    # subtract the mean of column i from column i, in order to center the matrix.
    band_mean = []
    for i in range(n_bands):
        band_mean.append(dask.delayed(dask.array.mean)(flat_dims[i]))
    band_mean = dask.compute(*band_mean)

    ########
    # compute the matrix correlation/covariance
    estimation_matrix = np.empty((n_bands, n_bands))
    for i in range(n_bands):
        deviation_scores_band_i = flat_dims[i] - band_mean[i]
        for j in range(i, n_bands):
            deviation_scores_band_j = flat_dims[j] - band_mean[j]
            if estimator_matrix == "Correlation":
                estimation_matrix[j][i] = estimation_matrix[i][j] = \
                    dask.array.corrcoef(deviation_scores_band_i, deviation_scores_band_j)[0][1]
            if estimator_matrix == "Covariance":
                estimation_matrix[j][i] = estimation_matrix[i][j] = \
                    dask.array.cov(deviation_scores_band_i, deviation_scores_band_j)[0][1]

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

    # output image profile
    prof = get_profile(A)
    prof.update(count=1, driver='GTiff', dtype=np.float32)

    @dask.delayed
    def get_principal_component(i, j):
        return eigenvectors[j, i] * (raw_image[j] - band_mean[j])

    pca_files = []
    for i in range(n_pc):
        pc = dask.delayed(sum)([get_principal_component(i, j) for j in range(n_bands)])
        pc = pc.astype(np.float32)
        # save component as file
        tmp_pca_file = os.path.join(out_dir, 'pc_{}.tif'.format(i+1))
        write_raster(tmp_pca_file, pc.compute(), **prof)
        pca_files.append(tmp_pca_file)

    # compute the pyramids for each pc image
    @dask.delayed
    def pyramids(pca_file):
        call("gdaladdo --config BIGTIFF_OVERVIEW YES {}".format(pca_file), shell=True)

    dask.compute(*[pyramids(pca_file) for pca_file in pca_files], num_workers=2)

    ########
    # pca statistics
    pca_stats = {}
    pca_stats["eigenvals"] = eigenvals
    pca_stats["eigenvals_%"] = eigenvals*100/n_bands
    pca_stats["eigenvectors"] = eigenvectors

    return pca_files, pca_stats

