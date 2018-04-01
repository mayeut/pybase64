#!/bin/bash
set -e -x

# build source dist
python setup.py build sdist

# test from source dist
mkdir from_source
pushd from_source
tar -xf ../dist/pybase64*.tar.gz
pushd pybase64*
# make extension mandatory
export CIBUILDWHEEL=1
# build extension
python setup.py build_ext -i -f
# test
pytest
popd
popd
