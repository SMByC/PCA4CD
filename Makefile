#/***************************************************************************
# PCA4CD
#
# Principal components analysis for change detection
#                             -------------------
#        copyright            : (C) 2018-2026 by Xavier Corredor Llano, SMByC
#        email                : xavier.corredor.llano@gmail.com
# ***************************************************************************/
#
#/***************************************************************************
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU General Public License as published by  *
# *   the Free Software Foundation; either version 2 of the License, or     *
# *   (at your option) any later version.                                   *
# *                                                                         *
# ***************************************************************************/

#################################################
# Edit the following to match your sources lists
#################################################


#Add iso code for any locales you want to support here (space separated)
# default is no locales
# LOCALES = af
LOCALES =

# If locales are enabled, set the name of the lrelease binary on your system. If
# you have trouble compiling the translations, you may have to specify the full path to
# lrelease
#LRELEASE = lrelease
#LRELEASE = lrelease-qt4


# translation
SOURCES = \
    __init__.py \
    pca4cd.py

PLUGINNAME = pca4cd

PY_FILES = \
    __init__.py \
    pca4cd.py

UI_FILES =

EXTRAS = metadata.txt LICENSE

EXTRA_DIRS = core utils gui libs ui icons

COMPILED_RESOURCE_FILES = resources.py

PEP8EXCLUDE=pydev,resources.py,conf.py,third_party,ui


#################################################
# Normally you would not need to edit below here
#################################################

PLUGIN_UPLOAD = python3 plugin_upload.py -u xaviercll

RESOURCE_SRC=$(shell grep '^ *<file' resources.qrc | sed 's@</file>@@g;s/.*>//g' | tr '\n' ' ')

default: compile

compile: $(COMPILED_RESOURCE_FILES)

# Resource compiler: prefer pyrcc6 (Qt6) when available, fall back to pyrcc5 (Qt5).
PYRCC := $(shell command -v pyrcc6 2>/dev/null || command -v pyrcc5 2>/dev/null)

%.py : %.qrc $(RESOURCES_SRC)
	$(PYRCC) -o $*.py  $<

%.qm : %.ts
	$(LRELEASE) $<

test: compile transcompile
	@echo
	@echo "----------------------"
	@echo "Regression Test Suite"
	@echo "----------------------"

	@# Preceding dash means that make will continue in case of errors
	@-export PYTHONPATH=`pwd`:$(PYTHONPATH); \
		export QGIS_DEBUG=0; \
		export QGIS_LOG_FILE=/dev/null; \
		nosetests -v --with-id --with-coverage --cover-package=. \
		3>&1 1>&2 2>&3 3>&- || true
	@echo "----------------------"
	@echo "If you get a 'no module named qgis.core error, try sourcing"
	@echo "the helper script we have provided first then run make test."
	@echo "e.g. source run-env-linux.sh <path to qgis install>; make test"
	@echo "----------------------"

extlibs:
	@echo
	@echo "---------------------------"
	@echo "Building extlibs.zip"
	@echo "---------------------------"
	rm -rf extlibs extlibs.zip
	pip install --target=extlibs --no-deps -r requirements.txt
	find extlibs -type d \( -name "__pycache__" -o -name "*.egg-info" -o -name "tests" -o -name "test" -o -name "bin" -o -name "examples" \) -prune -exec rm -rf {} +
	find extlibs -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.so" -o -name "*.dll" -o -name "*.dylib" \) -delete
	cd extlibs && zip -9r ../extlibs.zip .
	rm -rf extlibs
	@echo "Created package: extlibs.zip"

zip: compile
	@echo
	@echo "---------------------------"
	@echo "Creating plugin zip bundle."
	@echo "---------------------------"
	rm -f $(PLUGINNAME).zip
	mkdir -p .pkg_tmp/$(PLUGINNAME)
	cp -f $(PY_FILES) $(COMPILED_RESOURCE_FILES) $(EXTRAS) .pkg_tmp/$(PLUGINNAME)/
	@for d in $(EXTRA_DIRS); do \
		if [ -d "$$d" ]; then cp -rf $$d .pkg_tmp/$(PLUGINNAME)/; fi; \
	done
	find .pkg_tmp -type d \( -name "__pycache__" -o -name "*.dist-info" -o -name "*.egg-info" \) -prune -exec rm -rf {} \;
	find .pkg_tmp -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.sh" -o -name "*.db" \) -delete
	cd .pkg_tmp && zip -9r ../$(PLUGINNAME).zip $(PLUGINNAME)
	rm -rf .pkg_tmp
	@echo "Created package: $(PLUGINNAME).zip"

upload: zip
	@echo
	@echo "-------------------------------------"
	@echo "Uploading plugin to QGIS Plugin repo."
	@echo "-------------------------------------"
	$(PLUGIN_UPLOAD) $(PLUGINNAME).zip

transup:
	@echo
	@echo "------------------------------------------------"
	@echo "Updating translation files with any new strings."
	@echo "------------------------------------------------"
	@chmod +x scripts/update-strings.sh
	@scripts/update-strings.sh $(LOCALES)

transcompile:
	@echo
	@echo "----------------------------------------"
	@echo "Compiled translation files to .qm files."
	@echo "----------------------------------------"
	#@chmod +x scripts/compile-strings.sh
	#@scripts/compile-strings.sh $(LRELEASE) $(LOCALES)

transclean:
	@echo
	@echo "------------------------------------"
	@echo "Removing compiled translation files."
	@echo "------------------------------------"
	rm -f i18n/*.qm

clean:
	@echo
	@echo "------------------------------------"
	@echo "Removing uic and rcc generated files"
	@echo "------------------------------------"
	rm $(COMPILED_UI_FILES) $(COMPILED_RESOURCE_FILES)

doc:
	@echo
	@echo "------------------------------------"
	@echo "Building documentation using sphinx."
	@echo "------------------------------------"
	# cd help; make html

flake8:
	@echo
	@echo "-------------------"
	@echo "Flake8 code quality"
	@echo "-------------------"
	@uv run flake8 .
	@echo "-------------------"
	@echo "No issues found."
