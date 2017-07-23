#!/bin/bash
set -e -x

# build source dist
python setup.py build sdist

# test from source dist
mkdir from_source
pushd from_source
tar -xf ../dist/pybase64*.tar.gz
pushd pybase64*
python setup.py build_ext -i -f
nosetests
popd
popd

mkdir todeploy
mv dist/pybase64*.tar.gz todeploy/

