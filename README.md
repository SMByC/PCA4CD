# PCA4CD - PCA for change detection #

The PCA4CD is a Qgis plugin to build the change detection layer using the principal components method. Designed mainly with the goal of:

1. generate or load the principal components (PCA)
2. and build the change detection layer based on the dimensionality reduction properties.

## Documentation

Home page documentation: [https://smbyc.bitbucket.io/qgisplugins/pca4cd](https://smbyc.bitbucket.io/qgisplugins/pca4cd)

## Installation

The plugin can be installed using the QGIS Plugin Manager, go into Qgis to `Plugins` menu and `Manage and install plugins`, in `All` section search for `PCA4CD`.

The plugin will be available in the `Plugins` menu and `Plugins toolbar`.

### Additional Python packages

PCA4CD requires additional Python packages to function, that are generally not part of QGIS's Python. These are:

* Python-Dask
* PyQtGraph

The way for have that: First way (recommended and automatic) is that the plugin (when is installing or updating) will be installed into a separate folder specific to PCA4CD and will not influence any existing Python installation. Second, install it in your system python installation first before install the plugin, but depends of the operating system to work.

## Source code

The official version control system repository of the plugin:
[https://bitbucket.org/smbyc/qgisplugin-pca4cd](https://bitbucket.org/smbyc/qgisplugin-pca4cd)

The home plugin in plugins.qgis.org: [http://plugins.qgis.org/plugins/PCA4CD/](http://plugins.qgis.org/plugins/PCA4CD/)

## Issue Tracker

Issues, ideas and enhancements: [https://bitbucket.org/smbyc/qgisplugin-pca4cd/issues](https://bitbucket.org/smbyc/qgisplugin-pca4cd/issues)

## Get involved

The PCA4CD plugin is open source and you can help in different ways:

* help with developing and/or improve the docs cloning the repository and doing the push request ([howto](https://confluence.atlassian.com/bitbucket/fork-a-teammate-s-repository-774243391.html)).
* or just test it, report issues, ideas and enhancements in the issue tracker.

## About us

PCA4CD was developing, designed and implemented by the Group of Forest and Carbon Monitoring System (SMByC), operated by the Institute of Hydrology, Meteorology and Environmental Studies (IDEAM) - Colombia.

Author and developer: *Xavier Corredor Ll.*  
Support, tester and product verification: *Gustavo Galindo*

Acknowledge to all SMByC team.

### Contact

Xavier Corredor Ll.: *xcorredorl (a) ideam.gov.co*  
SMByC: *smbyc (a) ideam.gov.co*

General Public License - GPLv3
