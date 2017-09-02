#include "_pybase64_get_simd_flags.h"
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <config.h>
#include <libbase64.h>
#include <string.h> /* memset */
#include <assert.h>

#ifdef __SSE2__
#include <emmintrin.h>
#endif


static PyObject* g_BinAsciiError = NULL;
static PyObject* g_fallbackDecode = NULL;
static int libbase64_simd_flag = 0;
static uint32_t active_simd_flag = 0U;
static uint32_t simd_flags;

/* returns 0 on success */
static int parse_alphabet(PyObject* alphabetObject, char* alphabet, int* useAlphabet)
{
    Py_buffer buffer;

    assert(useAlphabet != NULL);

    if ((alphabetObject == NULL) || (alphabetObject == Py_None)) {
        *useAlphabet = 0;
        return 0;
    }

    if (PyUnicode_Check(alphabetObject)) {
        alphabetObject = PyUnicode_AsASCIIString(alphabetObject);
        if (alphabetObject == NULL) {
            if (PyErr_ExceptionMatches(PyExc_UnicodeEncodeError)) {
                PyErr_SetString(PyExc_ValueError, "string argument should contain only ASCII characters");
            }
            return -1;
        }
    }
    else {
        Py_INCREF(alphabetObject);
    }

    if (PyObject_GetBuffer(alphabetObject, &buffer, PyBUF_SIMPLE) < 0) {
        Py_DECREF(alphabetObject);
        return -1;
    }

    if (buffer.len != 2) {
        PyBuffer_Release(&buffer);
        Py_DECREF(alphabetObject);
        PyErr_SetString(PyExc_AssertionError, "len(altchars) != 2");
        return -1;
    }

    *useAlphabet = 1;
    alphabet[0] = ((const char*)buffer.buf)[0];
    alphabet[1] = ((const char*)buffer.buf)[1];

    if ((alphabet[0] == '+') && (alphabet[1] == '/')) {
        *useAlphabet = 0;
    }

    PyBuffer_Release(&buffer);
    Py_DECREF(alphabetObject);

    return 0;
}

static void translate_inplace(char* pSrcDst, size_t len, const char* alphabet)
{
    size_t i = 0U;
    const char c0 = alphabet[0];
    const char c1 = alphabet[1];

#ifdef __SSE2__
    if (len >= 16U) {
        const __m128i plus  = _mm_set1_epi8('+');
        const __m128i slash = _mm_set1_epi8('/');
        const __m128i c0_ = _mm_set1_epi8(c0);
        const __m128i c1_ = _mm_set1_epi8(c1);

        for (; i < (len & ~(size_t)15U); i += 16) {
            __m128i srcDst = _mm_loadu_si128((const __m128i*)(pSrcDst + i));
            __m128i m0     = _mm_cmpeq_epi8(srcDst, plus);
            __m128i m1     = _mm_cmpeq_epi8(srcDst, slash);

            srcDst = _mm_or_si128(_mm_andnot_si128(m0, srcDst), _mm_and_si128(m0, c0_));
            srcDst = _mm_or_si128(_mm_andnot_si128(m1, srcDst), _mm_and_si128(m1, c1_));

            _mm_storeu_si128((__m128i*)(pSrcDst + i), srcDst);
        }
    }
#endif

    for (; i < len; ++i) {
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
    size_t i = 0U;
    const char c0 = alphabet[0];
    const char c1 = alphabet[1];

#ifdef __SSE2__
    if (len >= 16U) {
        const __m128i plus  = _mm_set1_epi8('+');
        const __m128i slash = _mm_set1_epi8('/');
        const __m128i c0_ = _mm_set1_epi8(c0);
        const __m128i c1_ = _mm_set1_epi8(c1);

        for (; i < (len & ~(size_t)15U); i += 16) {
            __m128i srcDst = _mm_loadu_si128((const __m128i*)(pSrc + i));
            __m128i m0     = _mm_cmpeq_epi8(srcDst, c0_);
            __m128i m1     = _mm_cmpeq_epi8(srcDst, c1_);

            srcDst = _mm_or_si128(_mm_andnot_si128(m0, srcDst), _mm_and_si128(m0, plus));
            srcDst = _mm_or_si128(_mm_andnot_si128(m1, srcDst), _mm_and_si128(m1, slash));

            _mm_storeu_si128((__m128i*)(pDst + i), srcDst);
        }
    }
#endif

    for (; i < len; ++i) {
        const char cs = pSrc[i];
        char cd;

        if (cs == c0) {
            cd = '+';
        }
        else if (cs == c1) {
            cd = '/';
        }
#if 0 /* TODO, python does not do this, add option */
        else if (cs == '+') {
            cd = c0;
        }
        else if (cs == '/') {
            cd = c1;
        }
#endif
        else {
            cd = cs;
        }
        pDst[i] = cd;
    }
}

static PyObject* pybase64_encode(PyObject* self, PyObject* args, PyObject *kwds)
{
    static const char *kwlist[] = { "", "altchars", NULL };

    int use_alphabet = 0;
    char alphabet[2];
    Py_buffer buffer;
    size_t out_len;
    PyObject* out_object;
    PyObject* in_object;
    PyObject* in_alphabet = NULL;

    /* Parse the input tuple */
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|O", kwlist, &in_object, &in_alphabet)) {
        return NULL;
    }

    if (parse_alphabet(in_alphabet, alphabet, & use_alphabet) != 0) {
        return NULL;
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

    if (use_alphabet) {
        /* TODO, make this more efficient */
        const size_t dst_slice = 16U * 1024U;
        const Py_ssize_t src_slice = (Py_ssize_t)((dst_slice / 4U) * 3U);
        Py_ssize_t len = buffer.len;
        const char* src = (const char*)buffer.buf;
        char* dst = PyBytes_AS_STRING(out_object);
        size_t remainder;

        while (out_len > dst_slice) {
            size_t dst_len = dst_slice;

            base64_encode(src, src_slice, dst, &dst_len, libbase64_simd_flag);
            translate_inplace(dst, dst_slice, alphabet);

            len -= src_slice;
            src += src_slice;
            out_len -= dst_slice;
            dst += dst_slice;
        }
        remainder = out_len;
        base64_encode(src, len, dst, &out_len, libbase64_simd_flag);
        translate_inplace(dst, remainder, alphabet);
    }
    else {
        base64_encode(buffer.buf, buffer.len, PyBytes_AS_STRING(out_object), &out_len, libbase64_simd_flag);
    }
    PyBuffer_Release(&buffer);

    return out_object;
}

static PyObject* pybase64_decode(PyObject* self, PyObject* args, PyObject *kwds)
{
    static const char *kwlist[] = { "", "altchars", "validate", NULL };

    int use_alphabet = 0;
    char alphabet[2];
    char validation = 0;
    Py_buffer buffer;
    size_t out_len;
    PyObject* in_alphabet = NULL;
    PyObject* in_object;
    PyObject* out_object = NULL;

    /* Parse the input tuple */
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|Ob", kwlist, &in_object, &in_alphabet, &validation)) {
        return NULL;
    }

    if (parse_alphabet(in_alphabet, alphabet, &use_alphabet) != 0) {
        return NULL;
    }

    if (PyUnicode_Check(in_object)) {
        in_object = PyUnicode_AsASCIIString(in_object);
        if (in_object == NULL) {
            if (PyErr_ExceptionMatches(PyExc_UnicodeEncodeError)) {
                PyErr_SetString(PyExc_ValueError, "string argument should contain only ASCII characters");
            }
            return NULL;
        }
    }
    else {
        Py_INCREF(in_object);
    }

    if (PyObject_GetBuffer(in_object, &buffer, PyBUF_SIMPLE) < 0) {
        Py_DECREF(in_object);
        return NULL;
    }

/* TRY: */
    if (!validation) {
        PyObject* translate_object = NULL;

        if (use_alphabet) {
            translate_object = PyBytes_FromStringAndSize(NULL, buffer.len);
            if (translate_object == NULL) {
                goto EXCEPT;
            }
            translate(buffer.buf, PyBytes_AS_STRING(translate_object), buffer.len, alphabet);
        }
        PyBuffer_Release(&buffer);
        if (translate_object != NULL) {
            Py_DECREF(in_object);
            in_object = translate_object;
        }
        out_object = PyObject_CallFunctionObjArgs(g_fallbackDecode, in_object, NULL);
        Py_DECREF(in_object);
        return out_object;
    }

    /* No overflow check needed, exact out_len recomputed at the end */
    /* out_len is ceildiv(len / 4) * 3  when len % 4 != 0*/
    /* else out_len is (ceildiv(len / 4) + 1) * 3 */
    out_len = (size_t)((buffer.len / 4) * 3) + 3U;
    out_object = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)out_len);
    if (out_object == NULL) {
        goto EXCEPT;
    }

    if (use_alphabet) {
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
            if (base64_decode(cache, src_slice, dst, &dst_len, libbase64_simd_flag) <= 0) {
                PyErr_SetString(g_BinAsciiError, "Non-base64 digit found");
                goto EXCEPT;
            }

            len -= src_slice;
            src += src_slice;
            out_len -= dst_slice;
            dst += dst_slice;
        }
        translate(src, cache, len, alphabet);
        if (base64_decode(cache, len, dst, &out_len, libbase64_simd_flag) <= 0) {
            PyErr_SetString(g_BinAsciiError, "Non-base64 digit found");
            goto EXCEPT;
        }
        out_len += (dst - PyBytes_AS_STRING(out_object));
    }
    else {
        if (base64_decode(buffer.buf, buffer.len, PyBytes_AS_STRING(out_object), &out_len, libbase64_simd_flag) <= 0) {
            PyErr_SetString(g_BinAsciiError, "Non-base64 digit found");
            goto EXCEPT;
        }
    }
    _PyBytes_Resize(&out_object, (Py_ssize_t)out_len);
    goto FINALLY;
EXCEPT:
    if (out_object != NULL) {
        Py_DECREF(out_object);
        out_object = NULL;
    }
FINALLY:
    PyBuffer_Release(&buffer);
    Py_DECREF(in_object);
    return out_object;
}

static PyObject* pybase64_get_simd_path(PyObject* self, PyObject* arg)
{
    return PyLong_FromUnsignedLong(active_simd_flag);
}

static PyObject* pybase64_get_simd_flags_runtime(PyObject* self, PyObject* arg)
{
    return PyLong_FromUnsignedLong(simd_flags);
}

static PyObject* pybase64_get_simd_flags_compile(PyObject* self, PyObject* arg)
{
    uint32_t result = 0U;
#if HAVE_AVX2
    result |= PYBASE64_AVX2;
#endif
#if HAVE_AVX
    result |= PYBASE64_AVX;
#endif
#if HAVE_SSE42
    result |= PYBASE64_SSE42;
#endif
#if HAVE_SSE41
    result |= PYBASE64_SSE41;
#endif
#if HAVE_SSSE3
    result |= PYBASE64_SSSE3;
#endif
    return PyLong_FromUnsignedLong(result);
}

static void set_simd_path(uint32_t flag)
{
    flag &= simd_flags; /* clean-up with allowed flags */

    if (0) {
    }
#if HAVE_AVX2
    else if (flag & PYBASE64_AVX2) {
        active_simd_flag = PYBASE64_AVX2;
        libbase64_simd_flag = BASE64_FORCE_AVX2;
    }
#endif
#if HAVE_AVX
    else if (flag & PYBASE64_AVX) {
        active_simd_flag = PYBASE64_AVX;
        libbase64_simd_flag = BASE64_FORCE_AVX;
    }
#endif
#if HAVE_SSE42
    else if (flag & PYBASE64_SSE42) {
        active_simd_flag = PYBASE64_SSE42;
        libbase64_simd_flag = BASE64_FORCE_SSE42;
    }
#endif
#if HAVE_SSE41
    else if (flag & PYBASE64_SSE41) {
        active_simd_flag = PYBASE64_SSE41;
        libbase64_simd_flag = BASE64_FORCE_SSE41;
    }
#endif
#if HAVE_SSSE3
    else if (flag & PYBASE64_SSSE3) {
        active_simd_flag = PYBASE64_SSSE3;
        libbase64_simd_flag = BASE64_FORCE_SSSE3;
    }
#endif
    else {
        active_simd_flag = PYBASE64_NONE;
        libbase64_simd_flag = BASE64_FORCE_PLAIN;
    }
}

static PyObject* pybase64_set_simd_path(PyObject* self, PyObject* arg)
{
    set_simd_path((uint32_t)PyLong_AsUnsignedLong(arg));
    Py_RETURN_NONE;
}

static PyObject* pybase64_import(const char* from, const char* object)
{
    PyObject* subModules;
    PyObject* subModuleName;
    PyObject* imports;
    PyObject* importedObject;

    subModules = PyList_New(1);
    if (subModules == NULL) {
        return NULL;
    }
    subModuleName = PyUnicode_FromString(object);
    if (subModuleName == NULL) {
        Py_DECREF(subModules);
        return NULL;
    }
    Py_INCREF(subModuleName);
    PyList_SET_ITEM(subModules, 0, subModuleName);
    imports = PyImport_ImportModuleEx(from, NULL, NULL, subModules);
    Py_DECREF(subModules);
    if (imports == NULL) {
        Py_DECREF(subModuleName);
        return NULL;
    }
    importedObject = PyObject_GetAttr(imports, subModuleName);
    Py_DECREF(subModuleName);
    Py_DECREF(imports);
    return importedObject;
}

static PyObject* pybase64_import_BinAsciiError(PyObject* module)
{
    PyObject* binAsciiError;

    binAsciiError = pybase64_import("binascii", "Error");
    if (binAsciiError == NULL) {
        return NULL;
    }
    if (!PyObject_IsSubclass(binAsciiError, PyExc_Exception)) {
        Py_DECREF(binAsciiError);
        return NULL;
    }
    if (PyModule_AddObject(module, "_BinAsciiError", binAsciiError) != 0) {
        Py_DECREF(binAsciiError);
        return NULL;
    }
    return binAsciiError;
}

static PyObject* pybase64_import_fallbackDecode(PyObject* module)
{
    PyObject* fallbackDecode;

    fallbackDecode = pybase64_import("pybase64._fallback", "b64decode");
    if (fallbackDecode == NULL) {
        return NULL;
    }
    if (PyModule_AddObject(module, "_fallbackDecode", fallbackDecode) != 0) {
        Py_DECREF(fallbackDecode);
        return NULL;
    }
    return fallbackDecode;
}

static PyMethodDef _pybase64_methods[] = {
    { "b64encode", (PyCFunction)pybase64_encode, METH_VARARGS | METH_KEYWORDS, NULL },
    { "b64decode", (PyCFunction)pybase64_decode, METH_VARARGS | METH_KEYWORDS, NULL },
    { "_get_simd_path", (PyCFunction)pybase64_get_simd_path, METH_NOARGS, NULL },
    { "_set_simd_path", (PyCFunction)pybase64_set_simd_path, METH_O, NULL },
    { "_get_simd_flags_compile", (PyCFunction)pybase64_get_simd_flags_compile, METH_NOARGS, NULL },
    { "_get_simd_flags_runtime", (PyCFunction)pybase64_get_simd_flags_runtime, METH_NOARGS, NULL },
    { NULL, NULL, 0, NULL }  /* Sentinel */
};

#if PY_MAJOR_VERSION >= 3
/* Initialize this module. */
static struct PyModuleDef _pybase64_module = {
        PyModuleDef_HEAD_INIT,
        "pybase64._pybase64",
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
    if ((m = Py_InitModule3("pybase64._pybase64", _pybase64_methods, NULL)) == NULL) {
        return;
    }
#endif

    simd_flags = pybase64_get_simd_flags();
    set_simd_path(simd_flags);

    if ((m != NULL) && ((g_BinAsciiError = pybase64_import_BinAsciiError(m)) == NULL)) {
#if PY_MAJOR_VERSION >= 3
        Py_DECREF(m);
#endif
        m = NULL;
    }

    if ((m != NULL) && ((g_fallbackDecode = pybase64_import_fallbackDecode(m)) == NULL)) {
#if PY_MAJOR_VERSION >= 3
        Py_DECREF(m);
#endif
        m = NULL;
    }

#if PY_MAJOR_VERSION >= 3
    return m;
#else
    return;
#endif
}
