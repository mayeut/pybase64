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

Running Python 3.6.0, Apple LLVM version 8.1.0 (clang-802.0.42), Mac OS X 10.12.5 on an Intel Core i7-4870HQ @ 2.50GHz

.. code::

    0.1.0 (C extension active)
    bench: altchars=None, validate=False
    pybase64._pybase64.b64encode:     2819.747 MB/s (13,271,472 bytes)
    pybase64._pybase64.b64decode:      304.039 MB/s (13,271,472 bytes)
    base64.b64encode:                  560.382 MB/s (13,271,472 bytes)
    base64.b64decode:                  311.487 MB/s (13,271,472 bytes)
    bench: altchars=None, validate=True
    pybase64._pybase64.b64encode:     2950.594 MB/s (13,271,472 bytes)
    pybase64._pybase64.b64decode:     2821.600 MB/s (13,271,472 bytes)
    base64.b64encode:                  522.495 MB/s (13,271,472 bytes)
    base64.b64decode:                   99.513 MB/s (13,271,472 bytes)
    bench: altchars=b'-_', validate=False
    pybase64._pybase64.b64encode:     2220.323 MB/s (13,271,472 bytes)
    pybase64._pybase64.b64decode:      213.228 MB/s (13,271,472 bytes)
    base64.b64encode:                  299.008 MB/s (13,271,472 bytes)
    base64.b64decode:                  210.878 MB/s (13,271,472 bytes)
    bench: altchars=b'-_', validate=True
    pybase64._pybase64.b64encode:     2184.876 MB/s (13,271,472 bytes)
    pybase64._pybase64.b64decode:     2095.342 MB/s (13,271,472 bytes)
    base64.b64encode:                  303.990 MB/s (13,271,472 bytes)
    base64.b64decode:                   85.267 MB/s (13,271,472 bytes)
