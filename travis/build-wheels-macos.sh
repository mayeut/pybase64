#!/bin/bash
set -e -x

PYPATH=/Library/Frameworks/Python.framework/Versions

mkdir todeploy

# Compile wheels
for py_version in 2.7 3.4 3.5 3.6; do

	${PYPATH}/${py_version}/bin/virtualenv pybase64-build-${py_version}
	source pybase64-build-${py_version}/bin/activate

	# Install requirements
	pip install -r requirements.txt

	# Build package
	python setup.py build bdist_wheel

	# Install packages and test
	pip install pybase64 --no-index -f dist
	(cd "$HOME"; nosetests -v pybase64)

	# Save package
	mv dist/*.whl todeploy/

	# Destroy environment
	deactivate
	rm -rf pybase64-build-${py_version}
done
