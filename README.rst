.. SETUP VARIABLES
.. |license-status| image:: https://img.shields.io/badge/license-BSD%202--Clause-blue.svg
  :target: https://github.com/mayeut/pybase64/blob/master/LICENSE
.. |pypi-status| image:: https://img.shields.io/pypi/v/pybase64.svg
  :target: https://pypi.python.org/pypi/pybase64
.. |rtd-status| image:: https://readthedocs.org/projects/pybase64/badge/?version=stable
  :target: http://pybase64.readthedocs.io/en/stable/?badge=stable
  :alt: Documentation Status
.. |travis-status| image:: https://travis-ci.org/mayeut/pybase64.svg?branch=master
  :target: https://travis-ci.org/mayeut/pybase64
.. |appveyor-status| image:: https://ci.appveyor.com/api/projects/status/kj3l1f3ys2teg9ha/branch/master?svg=true
  :target: https://ci.appveyor.com/project/mayeut/pybase64/branch/master
.. |codecov-status| image:: https://codecov.io/gh/mayeut/pybase64/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/mayeut/pybase64/branch/master
.. END OF SETUP

Fast Base64 implementation
==========================

|license-status| |pypi-status| |rtd-status| |travis-status| |appveyor-status| |codecov-status|

This project is a wrapper on `libbase64 <https://github.com/aklomp/base64>`_.

It aims to provide a fast base64 implementation for base64 encoding/decoding.

Installation
============

.. code::

    pip install pybase64

Usage
=====

``pybase64`` uses the same API as Python base64 "modern interface" (introduced in Python 2.4) for an easy integration.

To get the fastest decoding, it is recommended to use the ``pybase64.b64decode`` and ``validate=True`` when possible.

.. code:: python

    import pybase64

    print(pybase64.b64encode(b'>>>foo???', altchars='_:'))
    # b'Pj4_Zm9vPz8:'
    print(pybase64.b64decode(b'Pj4_Zm9vPz8:', altchars='_:', validate=True))
    # b'>>>foo???'

    # Standard encoding helpers
    print(pybase64.standard_b64encode(b'>>>foo???'))
    # b'Pj4+Zm9vPz8/'
    print(pybase64.standard_b64decode(b'Pj4+Zm9vPz8/'))
    # b'>>>foo???'

    # URL safe encoding helpers
    print(pybase64.urlsafe_b64encode(b'>>>foo???'))
    # b'Pj4-Zm9vPz8_'
    print(pybase64.urlsafe_b64decode(b'Pj4-Zm9vPz8_'))
    # b'>>>foo???'


A command-line tool is also provided. It has encode, decode and benchmark subcommands.

.. code::

    usage: pybase64 [-h] [-V] {benchmark,encode,decode} ...

    pybase64 command-line tool.

    positional arguments:
      {benchmark,encode,decode}
                            tool help
        benchmark           -h for usage
        encode              -h for usage
        decode              -h for usage

    optional arguments:
      -h, --help            show this help message and exit
      -V, --version         show program's version number and exit

Full documentation on `Read the Docs <http://pybase64.readthedocs.io/en/stable/?badge=stable>`_.

Benchmark
=========

Running Python 3.6.0, Apple LLVM version 8.1.0 (clang-802.0.42), Mac OS X 10.12.6 on an Intel Core i7-4870HQ @ 2.50GHz

.. code::

    pybase64 0.2.0 (C extension active - AVX2)
    bench: altchars=None, validate=False
    pybase64._pybase64.b64encode:     2941.397 MB/s (13,271,472 bytes -> 17,695,296 bytes)
    pybase64._pybase64.b64decode:      328.250 MB/s (17,695,296 bytes -> 13,271,472 bytes)
    base64.b64encode:                  565.744 MB/s (13,271,472 bytes -> 17,695,296 bytes)
    base64.b64decode:                  327.075 MB/s (17,695,296 bytes -> 13,271,472 bytes)
    bench: altchars=None, validate=True
    pybase64._pybase64.b64encode:     2995.909 MB/s (13,271,472 bytes -> 17,695,296 bytes)
    pybase64._pybase64.b64decode:     3996.267 MB/s (17,695,296 bytes -> 13,271,472 bytes)
    base64.b64encode:                  577.565 MB/s (13,271,472 bytes -> 17,695,296 bytes)
    base64.b64decode:                  104.835 MB/s (17,695,296 bytes -> 13,271,472 bytes)
    bench: altchars=b'-_', validate=False
    pybase64._pybase64.b64encode:     2237.740 MB/s (13,271,472 bytes -> 17,695,296 bytes)
    pybase64._pybase64.b64decode:      262.021 MB/s (17,695,296 bytes -> 13,271,472 bytes)
    base64.b64encode:                  313.977 MB/s (13,271,472 bytes -> 17,695,296 bytes)
    base64.b64decode:                  219.487 MB/s (17,695,296 bytes -> 13,271,472 bytes)
    bench: altchars=b'-_', validate=True
    pybase64._pybase64.b64encode:     2349.481 MB/s (13,271,472 bytes -> 17,695,296 bytes)
    pybase64._pybase64.b64decode:     2790.047 MB/s (17,695,296 bytes -> 13,271,472 bytes)
    base64.b64encode:                  314.182 MB/s (13,271,472 bytes -> 17,695,296 bytes)
    base64.b64decode:                   89.855 MB/s (17,695,296 bytes -> 13,271,472 bytes)
