/* SHA3 module
 *
 * This module provides an interface to the SHA3 algorithm
 *
 * See below for information about the original code this module was
 * based upon. Additional work performed by:
 *
 *  Andrew Kuchling (amk@amk.ca)
 *  Greg Stein (gstein@lyra.org)
 *  Trevor Perrin (trevp@trevp.net)
 *  Gregory P. Smith (greg@krypto.org)
 *
 * Copyright (C) 2012-2016  Christian Heimes (christian@python.org)
 * Licensed to PSF under a Contributor Agreement.
 *
 */

#include <Python.h>
#include <libbase64.h>

static PyObject* pybase64_encode(PyObject* self, PyObject* arg)
{
    Py_buffer buffer;
    size_t out_len;
    PyObject* out_object;

    if (PyObject_GetBuffer(arg, &buffer, PyBUF_SIMPLE) < 0) {
        return NULL;
    }

    if (buffer.len > (3 * (PY_SSIZE_T_MAX / 4))) {
        PyBuffer_Release(&buffer);
        return PyErr_NoMemory();
    }

    out_len = (size_t)(((buffer.len + 2) / 3) * 4);
    out_object = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)out_len);
    if (out_object == NULL) {
        PyBuffer_Release(&buffer);
        return NULL;
    }

    base64_encode(buffer.buf, buffer.len, PyBytes_AS_STRING(out_object), &out_len, 0);
    PyBuffer_Release(&buffer);

    return out_object;
}

static PyObject* pybase64_decode(PyObject* self, PyObject* arg)
{
    Py_buffer buffer;
    size_t out_len;
    PyObject* out_object;

    if (PyObject_GetBuffer(arg, &buffer, PyBUF_SIMPLE) < 0) {
        return NULL;
    }

    if (buffer.len > (PY_SSIZE_T_MAX - 3)) {
        PyBuffer_Release(&buffer);
        return PyErr_NoMemory();
    }

    out_len = (size_t)(((buffer.len + 3) / 4) * 3);
    out_object = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)out_len);
    if (out_object == NULL) {
        PyBuffer_Release(&buffer);
        return NULL;
    }


    if (base64_decode(buffer.buf, buffer.len, PyBytes_AS_STRING(out_object), &out_len, 0) <= 0) {
        PyBuffer_Release(&buffer);
        return PyErr_NoMemory();
    }
    PyBuffer_Release(&buffer);

    _PyBytes_Resize(&out_object, (Py_ssize_t)out_len);

    return out_object;
}

static PyMethodDef _pybase64_methods[] = {
    { "encode", (PyCFunction)pybase64_encode, METH_O, NULL },
    { "decode", (PyCFunction)pybase64_decode, METH_O, NULL },
    { NULL, NULL, 0, NULL }  /* Sentinel */
};

#if PY_MAJOR_VERSION >= 3
/* Initialize this module. */
static struct PyModuleDef _pybase64_module = {
        PyModuleDef_HEAD_INIT,
        "_pybase64",
        NULL,
        -1,
        _pybase64_methods,
        NULL,
        NULL,
        NULL,
        NULL
};

PyMODINIT_FUNC
PyInit__pybase64(void)
{
    PyObject *m = NULL;

    if ((m = PyModule_Create(&_pybase64_module)) == NULL) {
        return NULL;
    }
#else

void
init_pybase64(void)
{
    PyObject *m = NULL;
    if ((m = Py_InitModule3("_pybase64", _pybase64_methods, NULL)) == NULL) {
        return;
    }
#endif

#if PY_MAJOR_VERSION >= 3
    return m;
#else
    return;
#endif
}
