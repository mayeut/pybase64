#include "_pybase64_get_simd_flags.h"
#define PY_SSIZE_T_CLEAN
#define PY_CXX_CONST const
#include <Python.h>
#include <config.h>
#include <libbase64.h>
#include <codecs.h>
#include <tables/tables.h>
#include <string.h> /* memset */
#include <assert.h>

#ifdef __SSE2__
#include <emmintrin.h>
#elif BASE64_WITH_NEON64
#include <arm_neon.h>
#endif

#if defined(__x86_64__) || defined(__i386__) || defined(_M_IX86) || defined(_M_X64)
#define HAVE_FAST_UNALIGNED_ACCESS 1
#else
#define HAVE_FAST_UNALIGNED_ACCESS 0
#endif

#define PYBASE64_FLAGS_ENCODE_AS_STRING (1U << 0)
#define PYBASE64_FLAGS_APPEND_NEW_LINE  (1U << 1)

typedef struct pybase64_state {
    PyObject *binAsciiError;
    uint32_t active_simd_flag;
    uint32_t simd_flags;
    int libbase64_simd_flag;
} pybase64_state;

#if defined(PY_VERSION_HEX) && PY_VERSION_HEX >= 0x030d0000
#define KW_CONST_CAST
#else
#define KW_CONST_CAST (char**)
#endif

/* returns 0 on success */
static int get_buffer(PyObject* object, Py_buffer* buffer, int bytes_like)
{
    if (PyObject_GetBuffer(object, buffer, PyBUF_RECORDS_RO | PyBUF_C_CONTIGUOUS) != 0) {
        return -1;
    }
#if defined(PYPY_VERSION)
    /* PyPy does not respect PyBUF_C_CONTIGUOUS */
    if (!PyBuffer_IsContiguous(buffer, 'C')) {
        PyBuffer_Release(buffer);
        PyErr_Format(PyExc_BufferError, "%R: underlying buffer is not C-contiguous", Py_TYPE(object));
        return -1;
    }
#endif
    if (bytes_like) {
        if (((buffer->format[0] != 'c') && (buffer->format[0] != 'b') && (buffer->format[0] != 'B')) || buffer->format[1] != '\0' ) {
            PyBuffer_Release(buffer);
            PyErr_Format(PyExc_TypeError, "expected single byte elements, not '%s' from %R", buffer->format, Py_TYPE(object));
            return -1;
        }
        if (buffer->ndim != 1) {
            PyBuffer_Release(buffer);
            PyErr_Format(PyExc_TypeError, "expected 1-D data, not %d-D data from %R", buffer->ndim, Py_TYPE(object));
            return -1;
        }
    }
    return 0;
}


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

    if (get_buffer(alphabetObject, &buffer, 1) != 0) {
        Py_DECREF(alphabetObject);
        return -1;
    }

    if (buffer.len != 2) {
        PyBuffer_Release(&buffer);
        Py_DECREF(alphabetObject);
        PyErr_SetString(PyExc_ValueError, "len(altchars) != 2");
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
#elif BASE64_WITH_NEON64
    if (len >= 16U) {
        const uint8x16_t plus  = vdupq_n_u8('+');
        const uint8x16_t slash = vdupq_n_u8('/');
        const uint8x16_t c0_ = vdupq_n_u8(c0);
        const uint8x16_t c1_ = vdupq_n_u8(c1);

        for (; i < (len & ~(size_t)15U); i += 16) {
            uint8x16_t srcDst = vld1q_u8((uint8_t const*)pSrcDst + i);
            uint8x16_t m0     = vceqq_u8(srcDst, plus);
            uint8x16_t m1     = vceqq_u8(srcDst, slash);

            srcDst = vbslq_u8(m0, c0_, srcDst);
            srcDst = vbslq_u8(m1, c1_, srcDst);

            vst1q_u8((uint8_t*)pSrcDst + i, srcDst);
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

static void translate(const char* pSrc, char* pDst, size_t len, const char* alphabet, int* has_bad_char)
{
    size_t i = 0U;
    const char c0 = alphabet[0];
    const char c1 = alphabet[1];
    const char replace_plus = ((c0 != '/') && (c0 != '+')) ? c0 : c1;
    const char replace_slash = ((c1 != '/') && (c1 != '+')) ? c1 : c0;

    (void)has_bad_char;

#if 0 // def __SSE2__
    if (len >= 16U) {
        const __m128i plus  = _mm_set1_epi8('+');
        const __m128i slash = _mm_set1_epi8('/');
        const __m128i c0_ = _mm_set1_epi8(c0);
        const __m128i c1_ = _mm_set1_epi8(c1);
        __m128i input_has_plus_ = _mm_setzero_si128();
        __m128i input_has_slash_ = _mm_setzero_si128();

        for (; i < (len & ~(size_t)15U); i += 16) {
            __m128i srcDst = _mm_loadu_si128((const __m128i*)(pSrc + i));
            __m128i m0     = _mm_cmpeq_epi8(srcDst, c0_);
            __m128i m1     = _mm_cmpeq_epi8(srcDst, c1_);

            input_has_plus_ = _mm_or_si128(input_has_plus_, _mm_cmpeq_epi8(srcDst, plus));
            input_has_slash_ = _mm_or_si128(input_has_slash_, _mm_cmpeq_epi8(srcDst, slash));

            srcDst = _mm_or_si128(_mm_andnot_si128(m0, srcDst), _mm_and_si128(m0, plus));
            srcDst = _mm_or_si128(_mm_andnot_si128(m1, srcDst), _mm_and_si128(m1, slash));

            _mm_storeu_si128((__m128i*)(pDst + i), srcDst);
        }

        if (_mm_movemask_epi8(input_has_plus_)) {
            input_has_plus = (c0 != '+') && (c1 != '+');
        }
        if (_mm_movemask_epi8(input_has_slash_)) {
            input_has_slash = (c0 != '/') && (c1 != '/');
        }
    }
#elif BASE64_WITH_NEON64
    if (len >= 16U) {
        const uint8x16_t plus  = vdupq_n_u8('+');
        const uint8x16_t slash = vdupq_n_u8('/');
        const uint8x16_t c0_ = vdupq_n_u8(c0);
        const uint8x16_t c1_ = vdupq_n_u8(c1);
        const char replace_plus__ = ((c0 == '+') || (c1 == '+')) ? '+' : replace_plus;
        const uint8x16_t replace_plus_ = vdupq_n_u8(replace_plus__);
        const char replace_slash__ = ((c0 == '/') || (c1 == '/')) ? '/' : replace_slash;
        const uint8x16_t replace_slash_ = vdupq_n_u8(replace_slash__);

        for (; i < (len & ~(size_t)15U); i += 16) {
            uint8x16_t srcDst = vld1q_u8((const uint8_t*)pSrc + i);
            uint8x16_t m0     = vceqq_u8(srcDst, plus);
            uint8x16_t m1     = vceqq_u8(srcDst, slash);
            uint8x16_t m2     = vceqq_u8(srcDst, c0_);
            uint8x16_t m3     = vceqq_u8(srcDst, c1_);

            srcDst = vbslq_u8(m0, replace_plus_, srcDst);
            srcDst = vbslq_u8(m1, replace_slash_, srcDst);
            srcDst = vbslq_u8(m2, plus, srcDst);
            srcDst = vbslq_u8(m3, slash, srcDst);

            vst1q_u8((uint8_t*)pDst + i, srcDst);
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
        else if (cs == '+') {
            cd = replace_plus;
        }
        else if (cs == '/') {
            cd = replace_slash;
        }
        else {
            cd = cs;
        }
        pDst[i] = cd;
    }
}

static void translate_deprecated(const char* pSrc, char* pDst, size_t len, const char* alphabet, int* has_bad_char)
{
    size_t i = 0U;
    const char c0 = alphabet[0];
    const char c1 = alphabet[1];
    int input_has_plus = 0;
    int input_has_slash = 0;

#ifdef __SSE2__
    if (len >= 16U) {
        const __m128i plus  = _mm_set1_epi8('+');
        const __m128i slash = _mm_set1_epi8('/');
        const __m128i c0_ = _mm_set1_epi8(c0);
        const __m128i c1_ = _mm_set1_epi8(c1);
        __m128i input_has_plus_ = _mm_setzero_si128();
        __m128i input_has_slash_ = _mm_setzero_si128();

        for (; i < (len & ~(size_t)15U); i += 16) {
            __m128i srcDst = _mm_loadu_si128((const __m128i*)(pSrc + i));
            __m128i m0     = _mm_cmpeq_epi8(srcDst, c0_);
            __m128i m1     = _mm_cmpeq_epi8(srcDst, c1_);

            input_has_plus_ = _mm_or_si128(input_has_plus_, _mm_cmpeq_epi8(srcDst, plus));
            input_has_slash_ = _mm_or_si128(input_has_slash_, _mm_cmpeq_epi8(srcDst, slash));

            srcDst = _mm_or_si128(_mm_andnot_si128(m0, srcDst), _mm_and_si128(m0, plus));
            srcDst = _mm_or_si128(_mm_andnot_si128(m1, srcDst), _mm_and_si128(m1, slash));

            _mm_storeu_si128((__m128i*)(pDst + i), srcDst);
        }

        if (_mm_movemask_epi8(input_has_plus_)) {
            input_has_plus = (c0 != '+') && (c1 != '+');
        }
        if (_mm_movemask_epi8(input_has_slash_)) {
            input_has_slash = (c0 != '/') && (c1 != '/');
        }
    }
#elif BASE64_WITH_NEON64
    if (len >= 16U) {
        const uint8x16_t plus  = vdupq_n_u8('+');
        const uint8x16_t slash = vdupq_n_u8('/');
        const uint8x16_t c0_ = vdupq_n_u8(c0);
        const uint8x16_t c1_ = vdupq_n_u8(c1);
        uint8x16_t input_has_plus_ = vdupq_n_u8(0);
        uint8x16_t input_has_slash_ = vdupq_n_u8(0);

        for (; i < (len & ~(size_t)15U); i += 16) {
            uint8x16_t srcDst = vld1q_u8((uint8_t const*)pSrc + i);
            uint8x16_t m0     = vceqq_u8(srcDst, c0_);
            uint8x16_t m1     = vceqq_u8(srcDst, c1_);

            input_has_plus_ = vorrq_u8(input_has_plus_, vceqq_u8(srcDst, plus));
            input_has_slash_ = vorrq_u8(input_has_slash_, vceqq_u8(srcDst, slash));

            srcDst = vbslq_u8(m0, plus, srcDst);
            srcDst = vbslq_u8(m1, slash, srcDst);

            vst1q_u8((uint8_t*)pDst + i, srcDst);
        }

        if (vmaxvq_u32(vreinterpretq_u32_u8(input_has_plus_))) {
            input_has_plus = (c0 != '+') && (c1 != '+');
        }
        if (vmaxvq_u32(vreinterpretq_u32_u8(input_has_slash_))) {
            input_has_slash = (c0 != '/') && (c1 != '/');
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
        else if (cs == '+') {
            input_has_plus = 1;
            cd = cs;
        }
        else if (cs == '/') {
            input_has_slash = 1;
            cd = cs;
        }
        else {
            cd = cs;
        }
        pDst[i] = cd;
    }
    *has_bad_char |= input_has_slash | input_has_plus;
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

static int check_ignore(uint8_t c, Py_buffer const* ignorechars, uint32_t* ignorecache)
{
    if (ignorecache[c >> 5] & (1U << (c & 31U))) {
        return 1;
    }
    if ((ignorechars->buf == NULL) || memchr(ignorechars->buf, c, ignorechars->len)) {
        ignorecache[c >> 5] |= 1U << (c & 31U);
        return 1;
    }
    return 0;
}

static int decode_novalidate(const uint8_t *src, size_t srclen, uint8_t* out, size_t* outlen, Py_buffer const* ignorechars)
{
    uint8_t* out_start = out;
    uint8_t carry;
    uint32_t ignorecache[8];

    memset(ignorecache, 0, sizeof(ignorecache));

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
                if (check_ignore(c, ignorechars, ignorecache)) {
                    continue;
                }
                return 1;
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
                if (check_ignore(c, ignorechars, ignorecache)) {
                    continue;
                }
                return 1;
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
                if (check_ignore(c, ignorechars, ignorecache)) {
                    continue;
                }
                return 1;
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
                if (check_ignore(c, ignorechars, ignorecache)) {
                    continue;
                }
                return 1;
            }
            *out++ = carry | q;
            break;
        }
    }
END:
    *outlen = out - out_start;
    return 0;
}

static PyObject* pybase64_encode_impl_core(PyObject* self, Py_buffer const* buffer, char const* alphabet, Py_ssize_t wrapcol, unsigned int flags)
{
    size_t out_len;
    PyObject* out_object;
#if PY_VERSION_HEX >= 0x030f0000
    PyBytesWriter* writer;
#endif
    char* dst;
    pybase64_state *state = (pybase64_state*)PyModule_GetState(self);
    if (state == NULL) {
        return NULL;
    }

    if (wrapcol < 0) {
        PyErr_SetString(PyExc_ValueError, "wrapcol must be >= 0");
        return NULL;
    }
    if (wrapcol > 0) {
        /* round down except for low value which are rounded up */
        wrapcol = (wrapcol < 4) ? 4U : (((size_t)wrapcol / 4U) * 4U);
    }

    if (buffer->len > (3 * (PY_SSIZE_T_MAX / 4))) {
        return PyErr_NoMemory();
    }

    out_len = (size_t)(((buffer->len + 2) / 3) * 4);
    if (wrapcol > 0 && out_len > 0) {
        size_t newlines = (out_len - 1U) / (size_t)wrapcol;
        if (newlines > ((size_t)PY_SSIZE_T_MAX - out_len)) {
            return PyErr_NoMemory();
        }
        out_len += newlines;
        if (newlines == 0) {
            wrapcol = 0;
        }
    }
    if (out_len == 0U) {
        flags &= ~PYBASE64_FLAGS_APPEND_NEW_LINE;
    }
    if (flags & PYBASE64_FLAGS_APPEND_NEW_LINE) {
        if (out_len > ((size_t)PY_SSIZE_T_MAX - 1U)) {
            return PyErr_NoMemory();
        }
        out_len++;
    }

    if (flags & PYBASE64_FLAGS_ENCODE_AS_STRING) {
        out_object = PyUnicode_New((Py_ssize_t)out_len, 127);
        if (out_object == NULL) {
            return NULL;
        }
        dst = (char*)PyUnicode_1BYTE_DATA(out_object);
    }
    else {
#if PY_VERSION_HEX >= 0x030f0000
        writer = PyBytesWriter_Create((Py_ssize_t)out_len);
        if (writer == NULL) {
            return NULL;
        }
        dst = PyBytesWriter_GetData(writer);
#else
        out_object = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)out_len);
        if (out_object == NULL) {
            return NULL;
        }
        dst = PyBytes_AS_STRING(out_object);
#endif
    }

    /* not interacting with Python objects from here, release the GIL */
    Py_BEGIN_ALLOW_THREADS

    int const libbase64_simd_flag = state->libbase64_simd_flag;

    if (flags & PYBASE64_FLAGS_APPEND_NEW_LINE) {
        out_len--; /* only consider len without new line terminator */
    }

    if (wrapcol) {
        const size_t dst_slice = (size_t)wrapcol + 1U;
        const Py_ssize_t src_slice = (Py_ssize_t)((dst_slice / 4U) * 3U);
        Py_ssize_t len = buffer->len;
        const char* src = (const char*)buffer->buf;
        size_t remainder;

        if (alphabet) {
            while (out_len > dst_slice) {
                size_t dst_len = (size_t)wrapcol;

                base64_encode(src, src_slice, dst, &dst_len, libbase64_simd_flag);
                translate_inplace(dst, dst_len, alphabet);
                dst[dst_len] = '\n';

                len -= src_slice;
                src += src_slice;
                out_len -= dst_slice;
                dst += dst_slice;
            }
            remainder = out_len;
            base64_encode(src, len, dst, &remainder, libbase64_simd_flag);
            translate_inplace(dst, remainder, alphabet);
            dst += remainder;
        }
        else {
            while (out_len > dst_slice) {
                size_t dst_len = (size_t)wrapcol;
                base64_encode(src, src_slice, dst, &dst_len, libbase64_simd_flag);
                dst[dst_len] = '\n';

                len -= src_slice;
                src += src_slice;
                out_len -= dst_slice;
                dst += dst_slice;
            }
            remainder = out_len;
            base64_encode(src, len, dst, &remainder, libbase64_simd_flag);
            dst += remainder;
        }
    }
    else if (alphabet) {
        /* TODO, make this more efficient */
        const size_t dst_slice = 16U * 1024U;
        const Py_ssize_t src_slice = (Py_ssize_t)((dst_slice / 4U) * 3U);
        Py_ssize_t len = buffer->len;
        const char* src = (const char*)buffer->buf;
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
        dst += remainder;
    }
    else {
        base64_encode(buffer->buf, buffer->len, dst, &out_len, libbase64_simd_flag);
        dst += out_len;
    }
    if (flags & PYBASE64_FLAGS_APPEND_NEW_LINE) {
        *dst = '\n';
    }

    /* restore the GIL */
    Py_END_ALLOW_THREADS

#if PY_VERSION_HEX >= 0x030f0000
    if (!(flags & PYBASE64_FLAGS_ENCODE_AS_STRING)) {
        out_object = PyBytesWriter_Finish(writer);
    }
#endif

    return out_object;
}

static PyObject* pybase64_encode_impl(PyObject* self, PyObject* args, PyObject *kwds, unsigned int flags)
{
    static const char *kwlist[] = { "", "altchars", "wrapcol", NULL };

    int use_alphabet = 0;
    char alphabet[2];
    Py_buffer buffer;
    PyObject* out_object;
    PyObject* in_object;
    PyObject* in_alphabet = NULL;
    Py_ssize_t wrapcol = 0;

    /* Parse the input tuple */
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|O$n", KW_CONST_CAST kwlist, &in_object, &in_alphabet, &wrapcol)) {
        return NULL;
    }

    if (parse_alphabet(in_alphabet, alphabet, &use_alphabet) != 0) {
        return NULL;
    }

    if (get_buffer(in_object, &buffer, 0) != 0) {
        return NULL;
    }

    out_object = pybase64_encode_impl_core(self, &buffer, use_alphabet ? alphabet : NULL, wrapcol, flags);

    PyBuffer_Release(&buffer);

    return out_object;
}

static PyObject* pybase64_encode(PyObject* self, PyObject* args, PyObject *kwds)
{
    return pybase64_encode_impl(self, args, kwds, 0U);
}

static PyObject* pybase64_encode_as_string(PyObject* self, PyObject* args, PyObject *kwds)
{
    return pybase64_encode_impl(self, args, kwds, PYBASE64_FLAGS_ENCODE_AS_STRING);
}

static PyObject* get_ignorechars_buffer(PyObject* object, Py_buffer* buffer, char const* alphabet)
{
    if (get_buffer(object, buffer, 1) != 0) {
        return NULL;
    }
    if ((buffer->len == 0) || (alphabet == NULL)) {
        Py_INCREF(object);
        return object;
    }

    PyObject* result = NULL;
    PyObject* tmp_result = NULL;
    void* translate_dst;
    Py_buffer in_buffer = *buffer;
#if PY_VERSION_HEX >= 0x030f0000
    PyBytesWriter* writer = PyBytesWriter_Create(in_buffer.len);
    if (writer == NULL) {
        goto END;
    }
    translate_dst = PyBytesWriter_GetData(writer);
#else
    tmp_result = PyBytes_FromStringAndSize(NULL, in_buffer.len);
    if (tmp_result == NULL) {
        goto END;
    }
    translate_dst = PyBytes_AS_STRING(tmp_result);
#endif

    translate(in_buffer.buf, translate_dst, in_buffer.len, alphabet, NULL);

#if PY_VERSION_HEX >= 0x030f0000
    tmp_result = PyBytesWriter_Finish(writer);
    writer = NULL;
    if (tmp_result == NULL) {
        goto END;
    }
#endif
    if (get_buffer(tmp_result, buffer, 0) != 0) {
       goto END;
    }
    result = tmp_result;
    tmp_result = NULL;
END:
    Py_XDECREF(tmp_result);
#if PY_VERSION_HEX >= 0x030f0000
    PyBytesWriter_Discard(writer);
#endif
    PyBuffer_Release(&in_buffer);
    return result;
}

static PyObject* pybase64_decode_impl(PyObject* self, PyObject* args, PyObject *kwds, int return_bytearray)
{
    static const char *kwlist[] = { "", "altchars", "validate", "ignorechars", NULL };

    int use_alphabet = 0;
    int has_bad_char = 0;
    char alphabet[2];
    int validation;
    Py_buffer buffer;
    Py_buffer ignorechars_buffer;
    size_t out_len;
    PyObject* in_alphabet = NULL;
    PyObject* in_object;
    PyObject* validation_object = NULL;
    PyObject* ignorechars_object = NULL;
    PyObject* out_object = NULL;
#if PY_VERSION_HEX >= 0x030f0000
    PyBytesWriter* writer = NULL;
#endif
    const void* source = NULL;
    Py_ssize_t source_len;
    int source_use_buffer = 0;
    void* dest;
    void (*translate_fn)(const char*, char*, size_t, const char*, int*) = &translate_deprecated;
    pybase64_state *state = (pybase64_state*)PyModule_GetState(self);
    if (state == NULL) {
        return NULL;
    }
    /* Parse the input tuple */
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|OO$O", KW_CONST_CAST kwlist, &in_object, &in_alphabet, &validation_object, &ignorechars_object)) {
        return NULL;
    }

    if (validation_object == NULL) {
        validation = (ignorechars_object != NULL);
    }
    else {
        validation = PyObject_IsTrue(validation_object);
        if (validation < 0) {
            return NULL;
        }
        if ((ignorechars_object != NULL) && !validation ) {
            PyErr_SetString(PyExc_ValueError, "validate must be True or unspecified when ignorechars is specified");
            return NULL;
        }
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
        if (get_buffer(in_object, &buffer, 0) != 0) {
            Py_DECREF(in_object);
            return NULL;
        }
        source = buffer.buf;
        source_len = buffer.len;
        source_use_buffer = 1;
    }

    memset(&ignorechars_buffer, 0, sizeof(ignorechars_buffer));
/* TRY: */
    if (ignorechars_object != NULL) {
        ignorechars_object = get_ignorechars_buffer(ignorechars_object, &ignorechars_buffer, use_alphabet ? alphabet : NULL);
        if (ignorechars_object == NULL) {
            goto EXCEPT;
        }
        if (ignorechars_buffer.len == 0) {
            PyBuffer_Release(&ignorechars_buffer);
            Py_DECREF(ignorechars_object);
            ignorechars_object = NULL;
            validation = 1;
        }
        else {
            validation = 0;
        }
        translate_fn = &translate;
    }

    if (!validation && use_alphabet) {
        PyObject* translate_object;
        char* translate_dst;

#if PY_VERSION_HEX >= 0x030f0000
        writer = PyBytesWriter_Create(source_len);
        if (writer == NULL) {
            goto EXCEPT;
        }
        translate_dst = PyBytesWriter_GetData(writer);
#else
        translate_object = PyBytes_FromStringAndSize(NULL, source_len);
        if (translate_object == NULL) {
            goto EXCEPT;
        }
        translate_dst = PyBytes_AS_STRING(translate_object);
#endif

        /* not interacting with Python objects from here, release the GIL */
        Py_BEGIN_ALLOW_THREADS

        translate_fn(source, translate_dst, source_len, alphabet, &has_bad_char);

        /* restore the GIL */
        Py_END_ALLOW_THREADS

#if PY_VERSION_HEX >= 0x030f0000
        translate_object = PyBytesWriter_Finish(writer);
        writer = NULL;
        if (translate_object == NULL) {
            goto EXCEPT;
        }
#endif

        if (source_use_buffer) {
            PyBuffer_Release(&buffer);
            Py_DECREF(in_object);
        }
        in_object = translate_object;
        if (get_buffer(in_object, &buffer, 0) != 0) {
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
        if (out_object == NULL) {
            goto EXCEPT;
        }
        dest = PyByteArray_AS_STRING(out_object);
    }
    else {
#if PY_VERSION_HEX >= 0x030f0000
        writer = PyBytesWriter_Create((Py_ssize_t)out_len);
        if (writer == NULL) {
            goto EXCEPT;
        }
        dest = PyBytesWriter_GetData(writer);
#else
        out_object = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)out_len);
        if (out_object == NULL) {
            goto EXCEPT;
        }
        dest = PyBytes_AS_STRING(out_object);
#endif
    }

    if (!validation) {
        int result;

        /* not interacting with Python objects from here, release the GIL */
        Py_BEGIN_ALLOW_THREADS

        result = decode_novalidate(source, source_len, dest, &out_len, &ignorechars_buffer);

        /* restore the GIL */
        Py_END_ALLOW_THREADS

        if (result != 0) {
            PyErr_SetString(state->binAsciiError, "Incorrect padding");
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
        int result = 1;

        /* not interacting with Python objects from here, release the GIL */
        Py_BEGIN_ALLOW_THREADS

        int const libbase64_simd_flag = state->libbase64_simd_flag;
        while (len > src_slice) {
            size_t dst_len = dst_slice;

            translate_fn(src, cache, src_slice, alphabet, &has_bad_char);
            result = base64_decode(cache, src_slice, dst, &dst_len, libbase64_simd_flag);
            if (result <= 0) {
                break;
            }

            len -= src_slice;
            src += src_slice;
            out_len -= dst_slice;
            dst += dst_slice;
        }
        if (result > 0) {
            translate_fn(src, cache, len, alphabet, &has_bad_char);
            result = base64_decode(cache, len, dst, &out_len, libbase64_simd_flag);
        }

        /* restore the GIL */
        Py_END_ALLOW_THREADS

        if (result <= 0) {
            PyErr_SetString(state->binAsciiError, "Non-base64 digit found");
            goto EXCEPT;
        }
        out_len += (dst - (char*)dest);
    }
    else {
        int result;

        /* not interacting with Python objects from here, release the GIL */
        Py_BEGIN_ALLOW_THREADS

        result = base64_decode(source, source_len, dest, &out_len, state->libbase64_simd_flag);

        /* restore the GIL */
        Py_END_ALLOW_THREADS

        if (result <= 0) {
            PyErr_SetString(state->binAsciiError, "Non-base64 digit found");
            goto EXCEPT;
        }
    }
    if (return_bytearray) {
        PyByteArray_Resize(out_object, (Py_ssize_t)out_len);
    }
    else {
#if PY_VERSION_HEX >= 0x030f0000
        out_object = PyBytesWriter_FinishWithSize(writer, (Py_ssize_t)out_len);
        /* writer = NULL; */
#else
        _PyBytes_Resize(&out_object, (Py_ssize_t)out_len);
#endif
    }
    goto FINALLY;
EXCEPT:
#if PY_VERSION_HEX >= 0x030f0000
    PyBytesWriter_Discard(writer);
#endif
    Py_XDECREF(out_object);
    out_object = NULL;
FINALLY:
    if (ignorechars_object) {
        PyBuffer_Release(&ignorechars_buffer);
        Py_DECREF(ignorechars_object);
    }
    if (source_use_buffer) {
        PyBuffer_Release(&buffer);
        Py_DECREF(in_object);
    }
    if (has_bad_char && (out_object != NULL)) {
        static const char format_validation[] = "invalid characters '+' or '/' in Base64 data with altchars=%R and validate=True will be an error in future versions";
        static const char format_no_validation[] = "invalid characters '+' or '/' in Base64 data with altchars=%R and validate=False will be discarded in future versions";
        char const* format = validation ? format_validation : format_no_validation;
        PyObject* category = validation ? PyExc_DeprecationWarning : PyExc_FutureWarning;
        if (PyErr_WarnFormat(category, 2, format, in_alphabet) < 0) {
            Py_XDECREF(out_object);
            out_object = NULL;
        }
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
    PyObject* out_object;

    if (get_buffer(in_object, &buffer, 1) != 0) {
        return NULL;
    }

    out_object = pybase64_encode_impl_core(self, &buffer, NULL, 76, PYBASE64_FLAGS_APPEND_NEW_LINE);

    PyBuffer_Release(&buffer);

    return out_object;
}

static PyObject* pybase64_get_simd_path(PyObject* self, PyObject* arg)
{
    pybase64_state *state = (pybase64_state*)PyModule_GetState(self);
    if (state == NULL) {
        return NULL;
    }
    return PyLong_FromUnsignedLong(state->active_simd_flag);
}

static PyObject* pybase64_get_simd_flags_runtime(PyObject* self, PyObject* arg)
{
    pybase64_state *state = (pybase64_state*)PyModule_GetState(self);
    if (state == NULL) {
        return NULL;
    }
    return PyLong_FromUnsignedLong(state->simd_flags);
}

static PyObject* pybase64_get_simd_flags_compile(PyObject* self, PyObject* arg)
{
    uint32_t result = 0U;

#if BASE64_WITH_NEON64 || BASE64_WITH_NEON32
    result |= PYBASE64_NEON;
#endif

#if BASE64_WITH_AVX512
    result |= PYBASE64_AVX512VBMI;
#endif
#if BASE64_WITH_AVX2
    result |= PYBASE64_AVX2;
#endif
#if BASE64_WITH_AVX
    result |= PYBASE64_AVX;
#endif
#if BASE64_WITH_SSE42
    result |= PYBASE64_SSE42;
#endif
#if BASE64_WITH_SSE41
    result |= PYBASE64_SSE41;
#endif
#if BASE64_WITH_SSSE3
    result |= PYBASE64_SSSE3;
#endif
    return PyLong_FromUnsignedLong(result);
}

static void set_simd_path(pybase64_state* state, uint32_t flag)
{
    flag &= state->simd_flags; /* clean-up with allowed flags */

    if (0) {
    }
#if BASE64_WITH_NEON64
    else if (flag & PYBASE64_NEON) {
        state->active_simd_flag = PYBASE64_NEON;
        state->libbase64_simd_flag = BASE64_FORCE_NEON64;
    }
#endif
#if BASE64_WITH_NEON32
    else if (flag & PYBASE64_NEON) {
        state->active_simd_flag = PYBASE64_NEON;
        state->libbase64_simd_flag = BASE64_FORCE_NEON32;
    }
#endif

#if BASE64_WITH_AVX512
    else if (flag & PYBASE64_AVX512VBMI) {
        state->active_simd_flag = PYBASE64_AVX512VBMI;
        state->libbase64_simd_flag = BASE64_FORCE_AVX512;
    }
#endif
#if BASE64_WITH_AVX2
    else if (flag & PYBASE64_AVX2) {
        state->active_simd_flag = PYBASE64_AVX2;
        state->libbase64_simd_flag = BASE64_FORCE_AVX2;
    }
#endif
#if BASE64_WITH_AVX
    else if (flag & PYBASE64_AVX) {
        state->active_simd_flag = PYBASE64_AVX;
        state->libbase64_simd_flag = BASE64_FORCE_AVX;
    }
#endif
#if BASE64_WITH_SSE42
    else if (flag & PYBASE64_SSE42) {
        state->active_simd_flag = PYBASE64_SSE42;
        state->libbase64_simd_flag = BASE64_FORCE_SSE42;
    }
#endif
#if BASE64_WITH_SSE41
    else if (flag & PYBASE64_SSE41) {
        state->active_simd_flag = PYBASE64_SSE41;
        state->libbase64_simd_flag = BASE64_FORCE_SSE41;
    }
#endif
#if BASE64_WITH_SSSE3
    else if (flag & PYBASE64_SSSE3) {
        state->active_simd_flag = PYBASE64_SSSE3;
        state->libbase64_simd_flag = BASE64_FORCE_SSSE3;
    }
#endif
    else {
        state->active_simd_flag = PYBASE64_NONE;
        state->libbase64_simd_flag = BASE64_FORCE_PLAIN;
    }
}

static PyObject* pybase64_set_simd_path(PyObject* self, PyObject* arg)
{
    pybase64_state *state = (pybase64_state*)PyModule_GetState(self);
    if (state == NULL) {
        return NULL;
    }
    set_simd_path(state, (uint32_t)PyLong_AsUnsignedLong(arg));
    Py_RETURN_NONE;
}

static PyObject* pybase64_get_simd_name(PyObject* self, PyObject* arg)
{
    uint32_t flags = (uint32_t)PyLong_AsUnsignedLong(arg);

    if (flags & PYBASE64_NEON) {
        return PyUnicode_FromString("NEON");
    }

    if (flags & PYBASE64_AVX512VBMI) {
        return PyUnicode_FromString("AVX512VBMI");
    }
    if (flags & PYBASE64_AVX2) {
        return PyUnicode_FromString("AVX2");
    }
    if (flags & PYBASE64_AVX) {
        return PyUnicode_FromString("AVX");
    }
    if (flags & PYBASE64_SSE42) {
        return PyUnicode_FromString("SSE42");
    }
    if (flags & PYBASE64_SSE41) {
        return PyUnicode_FromString("SSE41");
    }
    if (flags & PYBASE64_SSSE3) {
        return PyUnicode_FromString("SSSE3");
    }
    if (flags & PYBASE64_SSE3) {
        return PyUnicode_FromString("SSE3");
    }
    if (flags & PYBASE64_SSE2) {
        return PyUnicode_FromString("SSE2");
    }

    if (flags != 0) {
        return PyUnicode_FromString("unknown");
    }

    return PyUnicode_FromString("No SIMD");
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

static PyObject* pybase64_import_BinAsciiError()
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

    return binAsciiError;
}

static int _pybase64_exec(PyObject *m)
{
    pybase64_state *state = (pybase64_state*)PyModule_GetState(m);
    if (state == NULL) {
        return -1;
    }

    state->binAsciiError = pybase64_import_BinAsciiError();
    if (state->binAsciiError == NULL) {
        return -1;
    }

    Py_INCREF(state->binAsciiError); /* PyModule_AddObject steals a reference */
    if (PyModule_AddObject(m, "_BinAsciiError", state->binAsciiError) != 0) {
        Py_DECREF(state->binAsciiError);
        return -1;
    }

    state->simd_flags = pybase64_get_simd_flags();
    set_simd_path(state, state->simd_flags);

    return 0;
}

static int _pybase64_traverse(PyObject *m, visitproc visit, void *arg)
{
    pybase64_state *state = (pybase64_state*)PyModule_GetState(m);
    if (state) {
        Py_VISIT(state->binAsciiError);
    }
    return 0;
}

static int _pybase64_clear(PyObject *m)
{
    pybase64_state *state = (pybase64_state*)PyModule_GetState(m);
    if (state) {
        Py_CLEAR(state->binAsciiError);
    }
    return 0;
}

static void _pybase64_free(void *m)
{
    _pybase64_clear((PyObject *)m);
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
    { "_get_simd_name", (PyCFunction)pybase64_get_simd_name, METH_O, NULL },
    { NULL, NULL, 0, NULL }  /* Sentinel */
};

static PyModuleDef_Slot _pybase64_slots[] = {
#if PY_VERSION_HEX >= 0x030f0000
    {Py_mod_name, "pybase64._pybase64"},
    {Py_mod_state_size, (void*)sizeof(pybase64_state)},
    {Py_mod_methods, _pybase64_methods},
    {Py_mod_state_traverse, _pybase64_traverse},
    {Py_mod_state_clear, _pybase64_clear},
    {Py_mod_state_free, _pybase64_free},
#endif
    {Py_mod_exec, _pybase64_exec},
#ifdef Py_mod_multiple_interpreters
    {Py_mod_multiple_interpreters, Py_MOD_PER_INTERPRETER_GIL_SUPPORTED},
#endif
#ifdef Py_mod_gil
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, NULL}
};

/* Initialize this module. */
#if PY_VERSION_HEX >= 0x030f0000
PyMODEXPORT_FUNC
PyModExport__pybase64() {
    return _pybase64_slots;
}
#else
static struct PyModuleDef _pybase64_module = {
        PyModuleDef_HEAD_INIT,
        "pybase64._pybase64",
        NULL,
        sizeof(pybase64_state),
        _pybase64_methods,
        _pybase64_slots,
        _pybase64_traverse,
        _pybase64_clear,
        _pybase64_free
};

PyMODINIT_FUNC
PyInit__pybase64(void)
{
    return PyModuleDef_Init(&_pybase64_module);
}
#endif
