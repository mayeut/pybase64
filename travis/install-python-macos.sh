#!/bin/bash
set -e -x

DNLD_DIR=${HOME}/PyDownloads
PYURL=https://www.python.org/ftp/python
PYPATH=/Library/Frameworks/Python.framework/Versions

mkdir ${DNLD_DIR}

for py_version in 2.7.13 3.4.4 3.5.3 3.6.0; do
	PKG_PATH=${DNLD_DIR}/python-${py_version}-macosx10.6.pkg

	curl ${PYURL}/${py_version}/python-${py_version}-macosx10.6.pkg > ${PKG_PATH}
	sudo installer -pkg $PKG_PATH -target /
done

for py_version in 2.7 3.4 3.5 3.6; do
	if [ -f ${PYPATH}/${py_version}/bin/pip ]; then
		${PYPATH}/${py_version}/bin/pip install --upgrade pip
		${PYPATH}/${py_version}/bin/pip install virtualenv
	elif [ -f ${PYPATH}/${py_version}/bin/pip3 ]; then
		${PYPATH}/${py_version}/bin/pip3 install --upgrade pip
		${PYPATH}/${py_version}/bin/pip3 install virtualenv
	else
		exit 1
	fi
done
