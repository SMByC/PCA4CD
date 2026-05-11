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
import csv

import numpy as np
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QGuiApplication
from qgis.PyQt.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox,
                                 QFileDialog, QHBoxLayout, QHeaderView, QLabel,
                                 QPushButton, QTableWidget, QTableWidgetItem,
                                 QVBoxLayout)


class PCAInfoDialog(QDialog):
    """Read-only dialog showing eigenvalues, cumulative variance and the
    eigenvector matrix produced by `core.pca_dask_gdal.pca`.
    """

    def __init__(self, pca_stats, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PCA Information — Eigenvalues & Eigenvectors")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinimizeButtonHint |
                            Qt.WindowType.WindowMaximizeButtonHint)

        self._pca_stats = pca_stats

        eigenvals = np.asarray(pca_stats["eigenvals"])
        eigenvals_pct = np.asarray(pca_stats["eigenvals_%"])
        eigenvectors = np.asarray(pca_stats["eigenvectors"])
        estimator = pca_stats.get("estimator", "")
        band_labels = pca_stats.get("band_labels") or [
            "B{}".format(i + 1) for i in range(eigenvectors.shape[0])
        ]

        n_bands, n_pc = eigenvectors.shape
        cumulative_pct = np.cumsum(eigenvals_pct)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QLabel(
            "<b>Estimator:</b> {estimator} &nbsp;&nbsp; "
            "<b>Bands:</b> {n_bands} &nbsp;&nbsp; "
            "<b>Components computed:</b> {n_pc}".format(
                estimator=estimator or "—", n_bands=n_bands, n_pc=n_pc
            )
        )
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        eig_label = QLabel("<b>Eigenvalues</b>")
        eig_label.setToolTip("Variance captured by each principal component.")
        layout.addWidget(eig_label)
        self.eigenvalues_table = self._build_eigenvalues_table(
            eigenvals, eigenvals_pct, cumulative_pct
        )
        layout.addWidget(self.eigenvalues_table)
        self._fit_table_to_contents(self.eigenvalues_table)

        vec_label = QLabel("<b>Eigenvectors</b>")
        vec_label.setToolTip("Each column is one principal component expressed as a "
                             "unit-length linear combination of the input bands.")
        layout.addWidget(vec_label)
        self.eigenvectors_table = self._build_eigenvectors_table(
            eigenvectors, band_labels, n_pc
        )
        layout.addWidget(self.eigenvectors_table)
        self._fit_table_to_contents(self.eigenvectors_table)

        layout.addStretch(1)

        button_row = QHBoxLayout()
        copy_btn = QPushButton("Copy to clipboard")
        copy_btn.setToolTip("Copy both tables as TSV (paste-ready in spreadsheets).")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        save_btn = QPushButton("Save as CSV…")
        save_btn.setToolTip("Save eigenvalues and eigenvectors to a single CSV file.")
        save_btn.clicked.connect(self._save_csv)
        button_row.addWidget(copy_btn)
        button_row.addWidget(save_btn)
        button_row.addStretch(1)
        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)
        button_row.addWidget(close_box)
        layout.addLayout(button_row)

        # let the dialog open at the exact height required by the (already
        # content-sized) tables; keep a sensible default width
        self.adjustSize()
        self.resize(720, self.sizeHint().height())

    # ---------- table builders ----------

    @staticmethod
    def _make_table(rows, cols, h_headers, v_headers):
        table = QTableWidget(rows, cols)
        table.setHorizontalHeaderLabels(h_headers)
        table.setVerticalHeaderLabels(v_headers)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        return table

    @staticmethod
    def _fit_table_to_contents(table, max_visible_rows=20):
        """Size the table's height to exactly fit its rows (header + body),
        capped at `max_visible_rows` so wide datasets don't blow up the dialog
        (the table will scroll vertically beyond that).
        """
        table.resizeRowsToContents()
        visible = min(table.rowCount(), max_visible_rows)
        # use sizeHint() — the widget hasn't been shown yet so .height() may be 0
        h = table.horizontalHeader().sizeHint().height() + 2 * table.frameWidth()
        for i in range(visible):
            h += table.rowHeight(i)
        if table.rowCount() > max_visible_rows:
            h += table.horizontalScrollBar().sizeHint().height()
        table.setMinimumHeight(h)
        table.setMaximumHeight(h)

    def _build_eigenvalues_table(self, eigenvals, eigenvals_pct, cumulative_pct):
        rows = len(eigenvals)
        v_headers = ["PC{}".format(i + 1) for i in range(rows)]
        table = self._make_table(rows, 3, ["Eigenvalue", "Variance (%)", "Cumulative (%)"], v_headers)
        for i in range(rows):
            for j, val in enumerate((eigenvals[i], eigenvals_pct[i], cumulative_pct[i])):
                item = QTableWidgetItem("{:.6g}".format(float(val)))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(i, j, item)
        return table

    def _build_eigenvectors_table(self, eigenvectors, band_labels, n_pc):
        n_bands = eigenvectors.shape[0]
        h_headers = ["PC{}".format(i + 1) for i in range(n_pc)]
        table = self._make_table(n_bands, n_pc, h_headers, list(band_labels))
        for i in range(n_bands):
            for j in range(n_pc):
                item = QTableWidgetItem("{:.6g}".format(float(eigenvectors[i, j])))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(i, j, item)
        return table

    # ---------- export actions ----------

    def _as_text_blocks(self, sep):
        eigenvals = np.asarray(self._pca_stats["eigenvals"])
        eigenvals_pct = np.asarray(self._pca_stats["eigenvals_%"])
        eigenvectors = np.asarray(self._pca_stats["eigenvectors"])
        cumulative_pct = np.cumsum(eigenvals_pct)
        band_labels = self._pca_stats.get("band_labels") or [
            "B{}".format(i + 1) for i in range(eigenvectors.shape[0])
        ]
        n_pc = eigenvectors.shape[1]

        lines = []
        lines.append(sep.join(["Eigenvalues"]))
        lines.append(sep.join(["Component", "Eigenvalue", "Variance (%)", "Cumulative (%)"]))
        for i in range(len(eigenvals)):
            lines.append(sep.join([
                "PC{}".format(i + 1),
                "{:.10g}".format(float(eigenvals[i])),
                "{:.10g}".format(float(eigenvals_pct[i])),
                "{:.10g}".format(float(cumulative_pct[i])),
            ]))
        lines.append("")
        lines.append(sep.join(["Eigenvectors"]))
        lines.append(sep.join(["Band"] + ["PC{}".format(i + 1) for i in range(n_pc)]))
        for i, label in enumerate(band_labels):
            row = [label] + ["{:.10g}".format(float(eigenvectors[i, j])) for j in range(n_pc)]
            lines.append(sep.join(row))
        return "\n".join(lines)

    def _copy_to_clipboard(self):
        QGuiApplication.clipboard().setText(self._as_text_blocks("\t"))

    def _save_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PCA statistics as CSV", "pca_stats.csv",
            "CSV files (*.csv);;All files (*.*)"
        )
        if not path:
            return
        eigenvals = np.asarray(self._pca_stats["eigenvals"])
        eigenvals_pct = np.asarray(self._pca_stats["eigenvals_%"])
        eigenvectors = np.asarray(self._pca_stats["eigenvectors"])
        cumulative_pct = np.cumsum(eigenvals_pct)
        band_labels = self._pca_stats.get("band_labels") or [
            "B{}".format(i + 1) for i in range(eigenvectors.shape[0])
        ]
        n_pc = eigenvectors.shape[1]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["Estimator", self._pca_stats.get("estimator", "")])
            writer.writerow([])
            writer.writerow(["Eigenvalues"])
            writer.writerow(["Component", "Eigenvalue", "Variance (%)", "Cumulative (%)"])
            for i in range(len(eigenvals)):
                writer.writerow([
                    "PC{}".format(i + 1),
                    float(eigenvals[i]),
                    float(eigenvals_pct[i]),
                    float(cumulative_pct[i]),
                ])
            writer.writerow([])
            writer.writerow(["Eigenvectors"])
            writer.writerow(["Band"] + ["PC{}".format(i + 1) for i in range(n_pc)])
            for i, label in enumerate(band_labels):
                writer.writerow([label] + [float(eigenvectors[i, j]) for j in range(n_pc)])
