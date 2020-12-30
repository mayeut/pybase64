Getting started
===============

``pybase64`` is a wrapper on `libbase64 <https://github.com/aklomp/base64>`_.

It aims to provide a fast base64 implementation for base64 encoding/decoding.

Installation
------------

.. code-block:: bash

    pip install pybase64

Usage
-----

``pybase64`` uses the same API as Python :mod:`base64` "modern interface" (introduced in Python 2.4) for an easy integration.

To get the fastest decoding, it is recommended to use the :func:`~pybase64.b64decode` and `validate=True` when possible.

.. code-block:: python

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


Check :doc:`api` for more details.

.. include:: ../README.rst
    :start-after: .. begin cli
    :end-before: .. end cli

Benchmark
---------
.. include:: ../README.rst
    :start-after: .. begin benchmark
    :end-before: .. end benchmark
