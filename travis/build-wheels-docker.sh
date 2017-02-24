#!/bin/bash
set -e -x

function version_ok() {
	local VERSION=$("$1/python" --version 2>&1 | awk '{ print $2 }')
	local MAJOR=${VERSION%%.*}
	local MINOR=${VERSION%.*}
	MINOR=${MINOR#*.}

	if [ ${MAJOR} -eq 2 ]; then
		if [ ${MINOR} -lt 7 ]; then
			return 1
		fi
	elif [ ${MAJOR} -eq 3 ]; then
		if [ ${MINOR} -lt 4 ]; then
			return 1
		fi
	else
		return 1
	fi
	return 0
}

# check gcc version
gcc --version 2>&1

# Compile wheels
cd /io
for PYBIN in /opt/python/*/bin; do
	if version_ok "${PYBIN}"; then
		"${PYBIN}/pip" install -r requirements.txt
		"${PYBIN}/python" setup.py build bdist_wheel
	fi
done

# Bundle external shared libraries into the wheels
for whl in dist/*.whl; do
	auditwheel repair "$whl" -w /io/todeploy/
done

# Install packages and test
for PYBIN in /opt/python/*/bin/; do
	if version_ok "${PYBIN}"; then
		"${PYBIN}/pip" install pybase64 --no-index -f /io/todeploy
		(cd "$HOME"; "${PYBIN}/nosetests" -v pybase64)
	fi
done
