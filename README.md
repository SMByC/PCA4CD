# PCA4CD - PCA for change detection

![](icons/pca4cd.svg)

PCA4CD is a QGIS plugin that computes Principal Component Analysis (PCA) and can create a change detection layer using PCA's dimensionality reduction properties. Designed mainly with the goal of:

1. Generate (or load) the principal components (PCA) of the input layers
2. (optional) Build the change detection layer based on the dimensionality reduction properties of PCA.

![](docs/img/overview.png)

Read more in: [https://smbyc.github.io/PCA4CD](https://smbyc.github.io/PCA4CD)

## Installation

PCA4CD requires additional Python packages, that are generally not part of QGIS's Python, however the plugin has all the libs and dependencies inside, it must work on a 64bit system. The libraries are:

* Python-Dask
* PyQtGraph

> *Warning:* 
    This plugin only works in Qgis version >= 3.18

If you have issues with this try with the alternative installation below.

#### Using Conda

If you have problems with the dependencies, the best options to solve it is use [conda](https://docs.conda.io/en/latest/miniconda.html) and install Arosics and Qgis (from the conda shell):

```bash
conda install -c conda-forge dask pyqtgraph qgis
```

After that open Qgis from the shell with `qgis` command. Then install the plugin.

## Source code

Source code, issue tracker, QA and ideas: [https://github.com/SMByC/PCA4CD](https://github.com/SMByC/PCA4CD)
The home plugin in plugins.qgis.org: [https://plugins.qgis.org/plugins/pca4cd/](https://plugins.qgis.org/plugins/pca4cd/)

## About us

PCA4CD was developing, designed and implemented by the Group of Forest and Carbon Monitoring System (SMByC), operated by the Institute of Hydrology, Meteorology and Environmental Studies (IDEAM) - Colombia.

Author and developer: *Xavier C. Llano* *<xavier.corredor.llano@gmail.com>*  
Theoretical support, tester and product verification: SMByC-PDI group

## License

PCA4CD is a free/libre software and is licensed under the GNU General Public License.
