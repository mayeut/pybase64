#include <Python.h>
#include <libbase64.h>

static void translate_inplace(char* pSrcDst, size_t len, const char* alphabet)
{
    size_t i;
    const char c0 = alphabet[0];
    const char c1 = alphabet[1];

    for (i = 0U; i < len; ++i) {
        char c = pSrcDst[i];

        if (c == '+') {
            pSrcDst[i] = c0;
        }
        else if (c == '/') {
            pSrcDst[i] = c1;
        }
    }
}

static void translate(const char* pSrc, char* pDst, size_t len, const char* alphabet)
{
    size_t i;
    const char c0 = alphabet[0];
    const char c1 = alphabet[1];

    for (i = 0U; i < len; ++i) {
        char c = pSrc[i];

        if (c == c0) {
            c = '+';
        }
        else if (c == c1) {
            c = '/';
        }
        pDst[i] = c;
    }
}

static PyObject* pybase64_encode(PyObject* self, PyObject* args)
{
    char alphabet[2];
    Py_buffer buffer;
    size_t out_len;
    PyObject* out_object;
    PyObject* in_object;
    PyObject* in_alphabet;

    /* Parse the input tuple */
    if (!PyArg_ParseTuple(args, "OO", &in_object, &in_alphabet)) {
        return NULL;
    }

    if (in_alphabet != Py_None) {
        Py_buffer buffer_alphabet;
        if (PyObject_GetBuffer(in_alphabet, &buffer_alphabet, PyBUF_SIMPLE) < 0) {
            return NULL;
        }
        alphabet[0] = ((const char*)buffer_alphabet.buf)[0];
        alphabet[1] = ((const char*)buffer_alphabet.buf)[1];
        PyBuffer_Release(&buffer_alphabet);
    }

    if (PyObject_GetBuffer(in_object, &buffer, PyBUF_SIMPLE) < 0) {
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

    if (in_alphabet != Py_None) {
        /* TODO, make this more efficient */
        const size_t dst_slice = 16U * 1024U;
        const Py_ssize_t src_slice = (Py_ssize_t)((dst_slice / 4U) * 3U);
        Py_ssize_t len = buffer.len;
        const char* src = (const char*)buffer.buf;
        char* dst = PyBytes_AS_STRING(out_object);
        size_t remainder;

        while (out_len > dst_slice) {
            size_t dst_len = dst_slice;

            base64_encode(src, src_slice, dst, &dst_len, 0);
            translate_inplace(dst, dst_slice, alphabet);

            len -= src_slice;
            src += src_slice;
            out_len -= dst_slice;
            dst += dst_slice;
        }
        remainder = out_len;
        base64_encode(src, len, dst, &out_len, 0);
        translate_inplace(dst, remainder, alphabet);
    }
    else {
        base64_encode(buffer.buf, buffer.len, PyBytes_AS_STRING(out_object), &out_len, 0);
    }
    PyBuffer_Release(&buffer);

    return out_object;
}

static PyObject* pybase64_decode(PyObject* self, PyObject* args)
{
    char alphabet[2];
    char validation = 1;
    Py_buffer buffer;
    size_t out_len;
    PyObject* out_object;
    PyObject* in_object;
    PyObject* in_alphabet;

    /* Parse the input tuple */
    if (!PyArg_ParseTuple(args, "OOb", &in_object, &in_alphabet, &validation)) {
        return NULL;
    }

    if (in_alphabet != Py_None) {
        Py_buffer buffer_alphabet;
        if (PyObject_GetBuffer(in_alphabet, &buffer_alphabet, PyBUF_SIMPLE) < 0) {
            return NULL;
        }
        alphabet[0] = ((const char*)buffer_alphabet.buf)[0];
        alphabet[1] = ((const char*)buffer_alphabet.buf)[1];
        PyBuffer_Release(&buffer_alphabet);
    }

    if (PyObject_GetBuffer(in_object, &buffer, PyBUF_SIMPLE) < 0) {
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

    if (in_alphabet != Py_None) {
        /* TODO, make this more efficient */
        const Py_ssize_t src_slice = 16 * 1024;
        const size_t dst_slice = (src_slice / 4) * 3;
        char cache[16 * 1024];
        Py_ssize_t len = buffer.len;
        const char* src = (const char*)buffer.buf;
        char* dst = PyBytes_AS_STRING(out_object);

        while (len > src_slice) {
            size_t dst_len = dst_slice;

            translate(src, cache, src_slice, alphabet);
            if (base64_decode(cache, src_slice, dst, &dst_len, 0) <= 0) {
                PyBuffer_Release(&buffer);
                printf("toto\n");
                PyErr_SetString(PyExc_LookupError, "Non-base64 digit found");
                return NULL;
            }

            len -= src_slice;
            src += src_slice;
            out_len -= dst_slice;
            dst += dst_slice;
        }
        translate(src, cache, len, alphabet);
        if (base64_decode(cache, len, dst, &out_len, 0) <= 0) {
            PyBuffer_Release(&buffer);
            printf("tutu\n");
            PyErr_SetString(PyExc_LookupError, "Non-base64 digit found");
            return NULL;
        }
        out_len += (dst - PyBytes_AS_STRING(out_object));
    }
    else {
        if (base64_decode(buffer.buf, buffer.len, PyBytes_AS_STRING(out_object), &out_len, 0) <= 0) {
            PyBuffer_Release(&buffer);
            PyErr_SetString(PyExc_LookupError, "Non-base64 digit found");
            return NULL;
        }
    }
    PyBuffer_Release(&buffer);

    _PyBytes_Resize(&out_object, (Py_ssize_t)out_len);

    return out_object;
}

static PyMethodDef _pybase64_methods[] = {
    { "encode", (PyCFunction)pybase64_encode, METH_VARARGS, NULL },
    { "decode", (PyCFunction)pybase64_decode, METH_VARARGS, NULL },
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
