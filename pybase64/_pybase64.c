#include "_pybase64_get_simd_flags.h"
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <config.h>
#include <libbase64.h>
#include <codecs.h>
#include <tables/tables.h>
#include <string.h> /* memset */
#include <assert.h>

#ifdef __SSE2__
#include <emmintrin.h>
#endif


static PyObject* g_BinAsciiError = NULL;
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


static int next_valid_padding(const uint8_t *src, size_t srclen)
{
    int ret = 255;

    while (srclen && (ret == 255))
    {
        ret = base64_table_dec_8bit[*src++];
        srclen--;
    }

    return ret;
}

static int decode_novalidate(const uint8_t *src, size_t srclen, uint8_t *out, size_t*outlen)
{
    uint8_t* out_start = out;
    uint8_t carry;

    while (srclen > 0U)
    {
        /* case bytes == 0 */
        while (srclen > 4U)
        {
            union {
                uint32_t asint;
                uint8_t  aschar[4];
            } x;

            x.asint = base64_table_dec_32bit_d0[src[0]]
                    | base64_table_dec_32bit_d1[src[1]]
                    | base64_table_dec_32bit_d2[src[2]]
                    | base64_table_dec_32bit_d3[src[3]];
#if BASE64_LITTLE_ENDIAN
            /* LUTs for little-endian set Most Significant Bit
               in case of invalid character */
            if (x.asint & 0x80000000U) break;
#else
            /* LUTs for big-endian set Least Significant Bit
               in case of invalid character */
            if (x.asint & 1U) break;
#endif

#if HAVE_FAST_UNALIGNED_ACCESS
            /* This might segfault or be too slow on
               some architectures, do this only if specified
               with HAVE_FAST_UNALIGNED_ACCESS macro
               We write one byte more than needed */
            *(uint32_t*)out = x.asint;
#else
            /* Fallback, write bytes one by one */
            out[0] = x.aschar[0];
            out[1] = x.aschar[1];
            out[2] = x.aschar[2];
#endif
            src += 4;
            out += 3;
            srclen -= 4;
        }
        /* case bytes == 0, remainder */
        {
            uint8_t c = *src++; srclen--;
            uint8_t q;
            if ((q = base64_table_dec_8bit[c]) >= 254) {
                continue;
            }
            carry = q << 2;
        }
        /* case bytes == 1 */
        for(;;)
        {
            if (srclen-- == 0) {
                return 1;
            }
            uint8_t c = *src++;
            uint8_t q;
            if ((q = base64_table_dec_8bit[c]) >= 254) {
                continue;
            }
            *out++ = carry | (q >> 4);
            carry = q << 4;
            break;
        }
        /* case bytes == 2 */
        for(;;)
        {
            if (srclen-- == 0) {
                return 1;
            }
            uint8_t c = *src++;
            uint8_t q;
            if ((q = base64_table_dec_8bit[c]) >= 254) {
                if (q == 254) {
                    /* if the next valid byte is '=' => end */
                    if (next_valid_padding(src, srclen) == 254) {
                        goto END;
                    }
                }
                continue;
            }
            *out++ = carry | (q >> 2);
            carry = q << 6;
            break;
        }
        /* case bytes == 3 */
        for(;;)
        {
            if (srclen-- == 0) {
                return 1;
            }
            uint8_t c = *src++;
            uint8_t q;
            if ((q = base64_table_dec_8bit[c]) >= 254) {
                if (q == 254) {
                    srclen = 0U;
                    break;
                }
                continue;
            }
            *out++ = carry | q;
            break;
        }
    }
END:
    *outlen = out - out_start;
    return 0;
}

static PyObject* pybase64_encode_impl(PyObject* self, PyObject* args, PyObject *kwds, int return_string)
{
    static const char *kwlist[] = { "", "altchars", NULL };

    int use_alphabet = 0;
    char alphabet[2];
    Py_buffer buffer;
    size_t out_len;
    PyObject* out_object;
    PyObject* in_object;
    PyObject* in_alphabet = NULL;
    char* dst;

    /* Parse the input tuple */
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|O", kwlist, &in_object, &in_alphabet)) {
        return NULL;
    }

    if (parse_alphabet(in_alphabet, alphabet, &use_alphabet) != 0) {
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
    if (return_string) {
        out_object = PyUnicode_New((Py_ssize_t)out_len, 127);
    }
    else {
        out_object = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)out_len);
    }
    if (out_object == NULL) {
        PyBuffer_Release(&buffer);
        return NULL;
    }
    if (return_string) {
        dst = (char*)PyUnicode_1BYTE_DATA(out_object);
    }
    else {
        dst = PyBytes_AS_STRING(out_object);
    }

    if (use_alphabet) {
        /* TODO, make this more efficient */
        const size_t dst_slice = 16U * 1024U;
        const Py_ssize_t src_slice = (Py_ssize_t)((dst_slice / 4U) * 3U);
        Py_ssize_t len = buffer.len;
        const char* src = (const char*)buffer.buf;
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
        base64_encode(buffer.buf, buffer.len, dst, &out_len, libbase64_simd_flag);
    }
    PyBuffer_Release(&buffer);

    return out_object;
}

static PyObject* pybase64_encode(PyObject* self, PyObject* args, PyObject *kwds)
{
    return pybase64_encode_impl(self, args, kwds, 0);
}

static PyObject* pybase64_encode_as_string(PyObject* self, PyObject* args, PyObject *kwds)
{
    return pybase64_encode_impl(self, args, kwds, 1);
}

static PyObject* pybase64_decode_impl(PyObject* self, PyObject* args, PyObject *kwds, int return_bytearray)
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
    const void* source = NULL;
    Py_ssize_t source_len;
    int source_use_buffer = 0;
    void* dest;

    /* Parse the input tuple */
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|Ob", kwlist, &in_object, &in_alphabet, &validation)) {
        return NULL;
    }

    if (parse_alphabet(in_alphabet, alphabet, &use_alphabet) != 0) {
        return NULL;
    }

    if (PyUnicode_Check(in_object)) {
        if ((PyUnicode_READY(in_object) == 0) && (PyUnicode_KIND(in_object) == PyUnicode_1BYTE_KIND)) {
            source = PyUnicode_1BYTE_DATA(in_object);
            source_len = PyUnicode_GET_LENGTH(in_object);
        }
        else {
            in_object = PyUnicode_AsASCIIString(in_object);
            if (in_object == NULL) {
                if (PyErr_ExceptionMatches(PyExc_UnicodeEncodeError)) {
                    PyErr_SetString(PyExc_ValueError, "string argument should contain only ASCII characters");
                }
                return NULL;
            }
        }
    }
    else {
        Py_INCREF(in_object);
    }
    if (source == NULL) {
        if (PyObject_GetBuffer(in_object, &buffer, PyBUF_SIMPLE) < 0) {
            Py_DECREF(in_object);
            return NULL;
        }
        source = buffer.buf;
        source_len = buffer.len;
        source_use_buffer = 1;
    }

/* TRY: */
    if (!validation && use_alphabet) {
        PyObject* translate_object;

        translate_object = PyBytes_FromStringAndSize(NULL, source_len);
        if (translate_object == NULL) {
            goto EXCEPT;
        }
        translate(source, PyBytes_AS_STRING(translate_object), source_len, alphabet);

        if (source_use_buffer) {
            PyBuffer_Release(&buffer);
            Py_DECREF(in_object);
        }
        in_object = translate_object;
        if (PyObject_GetBuffer(in_object, &buffer, PyBUF_SIMPLE) < 0) {
            Py_DECREF(in_object);
            return NULL;
        }
        source = buffer.buf;
        source_len = buffer.len;
        source_use_buffer = 1;
    }

    /* No overflow check needed, exact out_len recomputed at the end */
    /* out_len is ceildiv(len / 4) * 3  when len % 4 != 0*/
    /* else out_len is (ceildiv(len / 4) + 1) * 3 */
    out_len = (size_t)((source_len / 4) * 3) + 3U;
    if (return_bytearray) {
        out_object = PyByteArray_FromStringAndSize(NULL, (Py_ssize_t)out_len);
    }
    else {
        out_object = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)out_len);
    }
    if (out_object == NULL) {
        goto EXCEPT;
    }
    if (return_bytearray) {
        dest = PyByteArray_AS_STRING(out_object);
    }
    else {
        dest = PyBytes_AS_STRING(out_object);
    }

    if (!validation) {
        if (decode_novalidate(source, source_len, dest, &out_len) != 0) {
            PyErr_SetString(g_BinAsciiError, "Incorrect padding");
            goto EXCEPT;
        }
    }
    else if (use_alphabet) {
        /* TODO, make this more efficient */
        const Py_ssize_t src_slice = 16 * 1024;
        const size_t dst_slice = (src_slice / 4) * 3;
        char cache[16 * 1024];
        Py_ssize_t len = source_len;
        const char* src = source;
        char* dst = dest;

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
        out_len += (dst - (char*)dest);
    }
    else {
        if (base64_decode(source, source_len, dest, &out_len, libbase64_simd_flag) <= 0) {
            PyErr_SetString(g_BinAsciiError, "Non-base64 digit found");
            goto EXCEPT;
        }
    }
    if (return_bytearray) {
        PyByteArray_Resize(out_object, (Py_ssize_t)out_len);
    }
    else {
        _PyBytes_Resize(&out_object, (Py_ssize_t)out_len);
    }
    goto FINALLY;
EXCEPT:
    if (out_object != NULL) {
        Py_DECREF(out_object);
        out_object = NULL;
    }
FINALLY:
    if (source_use_buffer) {
        PyBuffer_Release(&buffer);
        Py_DECREF(in_object);
    }
    return out_object;
}

static PyObject* pybase64_decode(PyObject* self, PyObject* args, PyObject *kwds)
{
    return pybase64_decode_impl(self, args, kwds, 0);
}

static PyObject* pybase64_decode_as_bytearray(PyObject* self, PyObject* args, PyObject *kwds)
{
    return pybase64_decode_impl(self, args, kwds, 1);
}

static PyObject* pybase64_encodebytes(PyObject* self, PyObject* in_object)
{
    Py_buffer buffer;
    size_t out_len;
    PyObject* out_object;

    if (PyObject_GetBuffer(in_object, &buffer, PyBUF_SIMPLE) < 0) {
        return NULL;
    }

    if (buffer.len > (3 * (PY_SSIZE_T_MAX / 4))) {
        PyBuffer_Release(&buffer);
        return PyErr_NoMemory();
    }

    out_len = (size_t)(((buffer.len + 2) / 3) * 4);
    if (out_len != 0U) {
        if ((((out_len - 1U) / 76U) + 1U) > (PY_SSIZE_T_MAX - out_len)) {
            PyBuffer_Release(&buffer);
            return PyErr_NoMemory();
        }
        out_len += ((out_len - 1U) / 76U) + 1U;
    }

    out_object = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)out_len);
    if (out_object == NULL) {
        PyBuffer_Release(&buffer);
        return NULL;
    }

    if (out_len > 0)
    {
        const size_t dst_slice = 77U;
        const Py_ssize_t src_slice = (Py_ssize_t)((dst_slice / 4U) * 3U);
        Py_ssize_t len = buffer.len;
        const char* src = (const char*)buffer.buf;
        char* dst = PyBytes_AS_STRING(out_object);
        size_t remainder;

        while (out_len > dst_slice) {
            size_t dst_len = dst_slice - 1U;

            base64_encode(src, src_slice, dst, &dst_len, libbase64_simd_flag);
            dst[dst_slice - 1U] = '\n';

            len -= src_slice;
            src += src_slice;
            out_len -= dst_slice;
            dst += dst_slice;
        }
        remainder = out_len - 1;
        base64_encode(src, len, dst, &remainder, libbase64_simd_flag);
        dst[out_len - 1] = '\n';
    }

    PyBuffer_Release(&buffer);

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
#if HAVE_NEON64
        libbase64_simd_flag = BASE64_FORCE_NEON64;
#elif HAVE_NEON32
        libbase64_simd_flag = BASE64_FORCE_NEON32;
#else
        libbase64_simd_flag = BASE64_FORCE_PLAIN;
#endif
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
    PyObject* moduleName;
    PyObject* imports;
    PyObject* importedObject;

    subModules = PyList_New(1);
    if (subModules == NULL) {
        return NULL;
    }
    moduleName = PyUnicode_FromString(from);
    if (moduleName == NULL) {
        Py_DECREF(subModules);
        return NULL;
    }
    subModuleName = PyUnicode_FromString(object);
    if (subModuleName == NULL) {
        Py_DECREF(moduleName);
        Py_DECREF(subModules);
        return NULL;
    }
    Py_INCREF(subModuleName);
    PyList_SET_ITEM(subModules, 0, subModuleName);
    imports = PyImport_ImportModuleLevelObject(moduleName, NULL, NULL, subModules, 0);
    Py_DECREF(moduleName);
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

static PyMethodDef _pybase64_methods[] = {
    { "b64encode", (PyCFunction)pybase64_encode, METH_VARARGS | METH_KEYWORDS, NULL },
    { "b64encode_as_string", (PyCFunction)pybase64_encode_as_string, METH_VARARGS | METH_KEYWORDS, NULL },
    { "b64decode", (PyCFunction)pybase64_decode, METH_VARARGS | METH_KEYWORDS, NULL },
    { "b64decode_as_bytearray", (PyCFunction)pybase64_decode_as_bytearray, METH_VARARGS | METH_KEYWORDS, NULL },
    { "encodebytes", (PyCFunction)pybase64_encodebytes, METH_O, NULL },
    { "_get_simd_path", (PyCFunction)pybase64_get_simd_path, METH_NOARGS, NULL },
    { "_set_simd_path", (PyCFunction)pybase64_set_simd_path, METH_O, NULL },
    { "_get_simd_flags_compile", (PyCFunction)pybase64_get_simd_flags_compile, METH_NOARGS, NULL },
    { "_get_simd_flags_runtime", (PyCFunction)pybase64_get_simd_flags_runtime, METH_NOARGS, NULL },
    { NULL, NULL, 0, NULL }  /* Sentinel */
};

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

    simd_flags = pybase64_get_simd_flags();
    set_simd_path(simd_flags);

    if ((m != NULL) && ((g_BinAsciiError = pybase64_import_BinAsciiError(m)) == NULL)) {
        Py_DECREF(m);
        m = NULL;
    }

    return m;
}
