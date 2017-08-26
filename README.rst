.. SETUP VARIABLES
.. |pypi-status| image:: https://img.shields.io/pypi/v/pybase64.svg
  :target: https://pypi.python.org/pypi/pybase64
.. |travis-status| image:: https://travis-ci.org/mayeut/pybase64.svg?branch=master
  :target: https://travis-ci.org/mayeut/pybase64
.. |appveyor-status| image:: https://ci.appveyor.com/api/projects/status/kj3l1f3ys2teg9ha?svg=true
  :target: https://ci.appveyor.com/project/mayeut/pybase64
.. |codecov-status| image:: https://codecov.io/gh/mayeut/pybase64/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/mayeut/pybase64
.. END OF SETUP

Fast Base64 implementation
==========================

This project is a wrapper on `libbase64 <https://github.com/aklomp/base64>`_.

It aims to provide a fast base64 implementation for standard base64 encoding/decoding.

Current status
==============

|pypi-status| |travis-status| |appveyor-status| |codecov-status|

Benchmark
=========

Running Python 3.6.0, Apple LLVM version 8.1.0 (clang-802.0.42), Mac OS X 10.12.6 on an Intel Core i7-4870HQ @ 2.50GHz

.. code::

    0.1.2 (C extension active)
    bench: altchars=None, validate=False
    pybase64._pybase64.b64encode:     3203.816 MB/s (13,271,472 bytes)
    pybase64._pybase64.b64decode:      322.261 MB/s (13,271,472 bytes)
    base64.b64encode:                  539.713 MB/s (13,271,472 bytes)
    base64.b64decode:                  321.367 MB/s (13,271,472 bytes)
    bench: altchars=None, validate=True
    pybase64._pybase64.b64encode:     3119.150 MB/s (13,271,472 bytes)
    pybase64._pybase64.b64decode:     4389.709 MB/s (13,271,472 bytes)
    base64.b64encode:                  585.207 MB/s (13,271,472 bytes)
    base64.b64decode:                  101.803 MB/s (13,271,472 bytes)
    bench: altchars=b'-_', validate=False
    pybase64._pybase64.b64encode:     2298.564 MB/s (13,271,472 bytes)
    pybase64._pybase64.b64decode:      276.244 MB/s (13,271,472 bytes)
    base64.b64encode:                  313.476 MB/s (13,271,472 bytes)
    base64.b64decode:                  229.085 MB/s (13,271,472 bytes)
    bench: altchars=b'-_', validate=True
    pybase64._pybase64.b64encode:     2379.698 MB/s (13,271,472 bytes)
    pybase64._pybase64.b64decode:     2862.796 MB/s (13,271,472 bytes)
    base64.b64encode:                  315.344 MB/s (13,271,472 bytes)
    base64.b64decode:                   91.621 MB/s (13,271,472 bytes)
