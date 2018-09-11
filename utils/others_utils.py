# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PCA4CD
                                 A QGIS plugin
 Principal components analysis for change detections
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