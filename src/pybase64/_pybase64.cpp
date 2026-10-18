#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <simdutf.cpp>

#include <array>
#include <cassert>
#include <string_view>

/* we still use an algorithm & tables derived from https://github.com/aklomp/base64 */
extern "C" {
#include <tables/tables.h>
}

#if defined(__SSE2__) || defined(SIMDUTF_IS_X86_64)
#define PYBASE64_HAS_SSE2 1
#include <emmintrin.h>
#elif defined(SIMDUTF_IS_ARM64)
#include <arm_neon.h>
#endif

#if (defined(Py_TARGET_ABI3T) || !defined(Py_GIL_DISABLED))
#define PYBASE64_HAS_GIL 1
#else
#define PYBASE64_HAS_GIL 0
#endif

#if 0 && PY_VERSION_HEX >= 0x030f0000
#define PYBASE64_USE_PYBYTES_WRITER 1
#else
#define PYBASE64_USE_PYBYTES_WRITER 0
#endif

#if defined(__x86_64__) || defined(__i386__) || defined(_M_IX86) || defined(_M_X64) || defined(SIMDUTF_IS_ARM64)
#define HAVE_FAST_UNALIGNED_ACCESS 1
#else
#define HAVE_FAST_UNALIGNED_ACCESS 0
#endif

#define PYBASE64_DECODE_SLOW_SUCCESS 0
#define PYBASE64_DECODE_SLOW_EXCESS_DATA 2
#define PYBASE64_DECODE_SLOW_LEADING_PADDING 3
#define PYBASE64_DECODE_SLOW_DISCONTINUOUS_PADDING 4
#define PYBASE64_DECODE_SLOW_EXCESS_PADDING 5
#define PYBASE64_DECODE_SLOW_INCORRECT_PADDING 6
#define PYBASE64_DECODE_SLOW_INVALID_LEN 7
#define PYBASE64_DECODE_SLOW_INVALID_DATA 8
#define PYBASE64_DECODE_SLOW_PADDING_NOT_ALLOWED 9
#define PYBASE64_DECODE_SLOW_PADDING_BITS_NOT_ALLOWED 10

#define PYBASE64_NO_COPY_OR_MOVE(CLASS_)         \
    CLASS_(CLASS_ const &) = delete;             \
    CLASS_ & operator=(CLASS_ const &) = delete; \
    CLASS_(CLASS_ &&) = delete;                  \
    CLASS_ & operator=(CLASS_ &&) = delete

namespace {

static auto const& implementations = simdutf::get_available_implementations();
static simdutf::implementation const* const best_implementation = implementations.detect_best_supported();
static const char url_alphabet[] = { '-', '_' };

struct State {
    PyObject *binAsciiError;
    PyObject *emptyBytes;
    PyObject *emptyStr;
    PyObject *ignoreCharsValidateFalse;
    simdutf::implementation const* active_implementation;
};
static inline State* GetState(PyObject* module) noexcept {
    return  static_cast<State*>(PyModule_GetState(module));
}

struct AllowThreads {
#if PYBASE64_HAS_GIL
    PyThreadState* _state = nullptr;
#endif
    PYBASE64_NO_COPY_OR_MOVE(AllowThreads);
    AllowThreads() = delete;

    template<typename SizeType>
    AllowThreads(SizeType input_size) noexcept {
#if PYBASE64_HAS_GIL
        if (input_size >= (64 * 1024)) {
            _state = PyEval_SaveThread();
        }
#endif
    }
    ~AllowThreads() noexcept {
#if PYBASE64_HAS_GIL
        if (_state != nullptr) {
            PyEval_RestoreThread(_state);
        }
#endif
    }
};

struct ByteArrayWriter
{
    PyObject* _object = nullptr;
    Py_ssize_t _size;
    char* data;
    PYBASE64_NO_COPY_OR_MOVE(ByteArrayWriter);
    ByteArrayWriter() = default;
    ~ByteArrayWriter() noexcept {
        Py_XDECREF(_object);
    }
    bool create(Py_ssize_t size) noexcept {
        _object = PyByteArray_FromStringAndSize(nullptr, size);
        if (_object == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
            return false; /* GCOVR_EXCL_LINE */
        }
        _size = size;
        data = PyByteArray_AS_STRING(_object);
        return true;
    }
    inline PyObject* finish(Py_ssize_t size) noexcept {
        if (size != _size) {
            if (PyByteArray_Resize(_object, size) == -1) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
                return nullptr; /* GCOVR_EXCL_LINE */
            }
        }
        PyObject* result = _object;
        _object = nullptr;
        return result;
    }
    static inline PyObject* empty(State* state) noexcept {
        return PyByteArray_FromStringAndSize(nullptr, 0);
    }
};

struct BytesWriter
{
#if PYBASE64_USE_PYBYTES_WRITER
    PyBytesWriter* _object = nullptr;
#else
    PyObject* _object = nullptr;
    Py_ssize_t _size;
#endif
    char* data;
    PYBASE64_NO_COPY_OR_MOVE(BytesWriter);
    BytesWriter() = default;
    ~BytesWriter() noexcept {
        if (_object != nullptr) {
#if PYBASE64_USE_PYBYTES_WRITER
            PyBytesWriter_Discard(_object);
#else
            Py_DECREF(_object);
#endif
        }
    }
    bool create(Py_ssize_t size) noexcept {
#if PYBASE64_USE_PYBYTES_WRITER
        _object = PyBytesWriter_Create(size);
        if (_object == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
            return false; /* GCOVR_EXCL_LINE */
        }
        data = static_cast<char*>(PyBytesWriter_GetData(_object));
#else
        _object = PyBytes_FromStringAndSize(nullptr, size);
        if (_object == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
            return false; /* GCOVR_EXCL_LINE */
        }
        _size = size;
        data = PyBytes_AS_STRING(_object);
#endif
        return true;
    }
    inline PyObject* finish() noexcept {
#if PYBASE64_USE_PYBYTES_WRITER
        auto result = PyBytesWriter_Finish(_object);
#else
        auto result = _object;
#endif
        _object = nullptr;
        return result;
    }
    inline PyObject* finish(Py_ssize_t size) noexcept {
#if PYBASE64_USE_PYBYTES_WRITER
        auto result = PyBytesWriter_FinishWithSize(_object, size);
#else
        auto result = _object;
        if (size != _size) {
            _PyBytes_Resize(&result, size);
        }
#endif
        _object = nullptr;
        return result;
    }
    static inline PyObject* empty(State* state) noexcept {
        Py_INCREF(state->emptyBytes);
        return state->emptyBytes;
    }
};

struct StringWriter
{
    PyObject* _object = nullptr;
    char* data;
    PYBASE64_NO_COPY_OR_MOVE(StringWriter);
    StringWriter() = default;
    ~StringWriter() noexcept {
        Py_XDECREF(_object);
    }
    bool create(Py_ssize_t size) noexcept {
        _object = PyUnicode_New(size, 127);
        if (_object == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
            return false; /* GCOVR_EXCL_LINE */
        }
        if (PyUnicode_KIND(_object) != PyUnicode_1BYTE_KIND) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
            /* GCOVR_EXCL_START */
            Py_DECREF(_object);
            PyErr_SetString(PyExc_RuntimeError, "Not a PyUnicode_1BYTE_KIND object");
            return false;
            /* GCOVR_EXCL_STOP */
        }
        data = static_cast<char*>(PyUnicode_DATA(_object));
        return true;
    }
    inline PyObject* finish() noexcept {
        auto result = _object;
        _object = nullptr;
        return result;
    }
    static inline PyObject* empty(State* state) noexcept {
        Py_INCREF(state->emptyStr);
        return state->emptyStr;
    }
};


struct BufferInput {
    Py_buffer _buffer{};
    bool _has_buffer = false;
    char const* data;
    size_t size;
    PYBASE64_NO_COPY_OR_MOVE(BufferInput);
    BufferInput() = default;
    ~BufferInput() noexcept {
        if (_has_buffer) {
            PyBuffer_Release(&_buffer);
        }
    }

    template<bool bytes_like>
    bool from_buffer(PyObject* object) noexcept {
        assert(!_has_buffer);
        if (PyBytes_Check(object)) {
            data = PyBytes_AS_STRING(object);
            size = PyBytes_GET_SIZE(object);
            return true;
        }
        if (PyObject_GetBuffer(object, &_buffer, PyBUF_RECORDS_RO | PyBUF_C_CONTIGUOUS) != 0) {
            return false;
        }
        _has_buffer = true;
#if defined(PYPY_VERSION)
        /* PyPy does not respect PyBUF_C_CONTIGUOUS */
        if (!PyBuffer_IsContiguous(&_buffer, 'C')) {
            PyErr_Format(PyExc_BufferError, "%R: underlying buffer is not C-contiguous", Py_TYPE(object));
            return false;
        }
#endif
        if constexpr (bytes_like) {
            if (_buffer.format == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
                /* GCOVR_EXCL_START */
                PyErr_Format(PyExc_TypeError, "expected single byte elements, not unknown format from %R", Py_TYPE(object));
                return false;
                /* GCOVR_EXCL_STOP */
            }
            if (((_buffer.format[0] != 'c') & (_buffer.format[0] != 'b') & (_buffer.format[0] != 'B')) || _buffer.format[1] != '\0' ) {
                PyErr_Format(PyExc_TypeError, "expected single byte elements, not '%s' from %R", _buffer.format, Py_TYPE(object));
                return false;
            }
            if (_buffer.ndim != 1) {
                PyErr_Format(PyExc_TypeError, "expected 1-D data, not %d-D data from %R", _buffer.ndim, Py_TYPE(object));
                return false;
            }
        }
        data = static_cast<const char *>(_buffer.buf);
        size = size_t(_buffer.len);
        return true;
    }
};

struct BufferOrStrInput : BufferInput {
    BufferOrStrInput() = default;
    ~BufferOrStrInput() = default;

    template<bool bytes_like>
    bool from_buffer_or_str(PyObject* object) noexcept {
        PyObject* temp = nullptr;
        if (PyUnicode_Check(object)) {
#if PY_VERSION_HEX < 0x030c0000
            if (PyUnicode_READY(object) != 0) {
                return false; /* GCOVR_EXCL_LINE */
            }
#endif
            if (PyUnicode_IS_ASCII(object) && (PyUnicode_KIND(object) == PyUnicode_1BYTE_KIND)) {
                data = static_cast<char const*>(PyUnicode_DATA(object));
                size = size_t(PyUnicode_GET_LENGTH(object));
                return true;
            }

            object = temp = PyUnicode_AsASCIIString(object);
            if (temp == nullptr) {
                if (PyErr_ExceptionMatches(PyExc_UnicodeEncodeError)) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
                    PyErr_SetString(PyExc_ValueError, "string argument should contain only ASCII characters");
                }
                return false;
            }
        }
        auto result = from_buffer<bytes_like>(object);
        Py_XDECREF(temp);
        return result;
    }
};

struct IgnoreChars {
    char const* const _ignorechars_data;
    size_t const _ignorechars_size;
    mutable std::array<uint32_t, 8> _cache{};
    PYBASE64_NO_COPY_OR_MOVE(IgnoreChars);
    IgnoreChars() = delete;
    ~IgnoreChars() = default;
    IgnoreChars(BufferInput const& ignorechars) noexcept :
        _ignorechars_data{ ignorechars.data }, _ignorechars_size{ ignorechars.size } {}

    bool ignore(uint8_t c) const noexcept
    {
        if (_cache[c >> 5] & (1U << (c & 31U))) {
            return true;
        }
        if (memchr(_ignorechars_data, c, _ignorechars_size)) {
            _cache[c >> 5] |= 1U << (c & 31U);
            return true;
        }
        return false;
    }
};

template<Py_ssize_t required_pos_args, Py_ssize_t max_pos_args, Py_ssize_t arg_count>
static bool fastcall_parse_args(
    /* fastcall fn args */
    PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
    /* mapping */
    std::string_view const* arg_names, PyObject** parsed_args
)
{
    if (nargs > max_pos_args) {
        PyErr_Format(PyExc_TypeError, "takes %zd positional argument but %zd were given", max_pos_args, nargs);
        return false;
    }
    for (Py_ssize_t i = 0; i < nargs; ++i) {
        parsed_args[i] = args[i];
    }
    for (Py_ssize_t i = nargs; i < arg_count; ++i) {
        parsed_args[i] = nullptr;
    }
    if (kwnames != nullptr) {
        Py_ssize_t kw_count = PyTuple_GET_SIZE(kwnames);
        for (Py_ssize_t k = 0; k < kw_count; k++) {
            PyObject* arg_name = PyTuple_GET_ITEM(kwnames, k);
            Py_ssize_t index = -1;
            for (Py_ssize_t i = 0; i < arg_count; i++) {
#if PY_VERSION_HEX >= 0x030d0000
                if (PyUnicode_EqualToUTF8AndSize(arg_name, arg_names[i].data(), arg_names[i].size())) {
#else
                if (PyUnicode_CompareWithASCIIString(arg_name, arg_names[i].data()) == 0) {
#endif
                  index = i;
                  break;
                }
            }
            if (index < 0) {
                PyErr_Format(PyExc_TypeError, "got an unexpected keyword argument %R", arg_name);
                return false;
            }
            if (parsed_args[index] != nullptr) {
                PyErr_Format(PyExc_TypeError, "got multiple values for argument %R", arg_name);
                return false;
            }
            parsed_args[index] = args[nargs + k];
        }
    }
    for (Py_ssize_t i = 0; i < required_pos_args; ++i) {
        if (parsed_args[i] == nullptr) {
            PyErr_Format(PyExc_TypeError, "missing required positional argument: '%s'", arg_names[i].data());
            return false;
        }
    }
    return true;
}

static bool parse_alphabet(PyObject* alphabetObject, char* alphabet_storage, char const*& alphabet)
{
    if ((alphabetObject == nullptr) | (alphabetObject == Py_None)) {
        alphabet = nullptr;
        return true;
    }

    BufferOrStrInput in;
    if (!in.from_buffer_or_str<true>(alphabetObject)) {
        return false;
    }

    if (in.size != 2) {
        PyErr_SetString(PyExc_ValueError, "len(altchars) != 2");
        return false;
    }

    if ((in.data[0] == '+') & (in.data[1] == '/')) {
        alphabet = nullptr;
    }
    else if ((in.data[0] == '-') & (in.data[1] == '_')) {
        alphabet = url_alphabet;
    }
    else {
        alphabet_storage[0] = in.data[0];
        alphabet_storage[1] = in.data[1];
        alphabet = alphabet_storage;
    }

    return true;
}

static void translate_inplace(char* pSrcDst, size_t len, const char* alphabet)
{
    size_t i = 0U;
    const char c0 = alphabet[0];
    const char c1 = alphabet[1];

#if defined(PYBASE64_HAS_SSE2)
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
#elif defined(SIMDUTF_IS_ARM64)
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

#if defined(PYBASE64_HAS_SSE2)
    if (len >= 16U) {
        const __m128i plus  = _mm_set1_epi8('+');
        const __m128i slash = _mm_set1_epi8('/');
        const __m128i c0_ = _mm_set1_epi8(c0);
        const __m128i c1_ = _mm_set1_epi8(c1);
        const char replace_plus__ = ((c0 == '+') || (c1 == '+')) ? '+' : replace_plus;
        const __m128i replace_plus_ = _mm_set1_epi8(replace_plus__);
        const char replace_slash__ = ((c0 == '/') || (c1 == '/')) ? '/' : replace_slash;
        const __m128i replace_slash_ = _mm_set1_epi8(replace_slash__);

        for (; i < (len & ~(size_t)15U); i += 16) {
            __m128i srcDst = _mm_loadu_si128((const __m128i*)(pSrc + i));
            __m128i m0     = _mm_cmpeq_epi8(srcDst, plus);
            __m128i m1     = _mm_cmpeq_epi8(srcDst, slash);
            __m128i m2     = _mm_cmpeq_epi8(srcDst, c0_);
            __m128i m3     = _mm_cmpeq_epi8(srcDst, c1_);

            srcDst = _mm_or_si128(_mm_andnot_si128(m0, srcDst), _mm_and_si128(m0, replace_plus_));
            srcDst = _mm_or_si128(_mm_andnot_si128(m1, srcDst), _mm_and_si128(m1, replace_slash_));
            srcDst = _mm_or_si128(_mm_andnot_si128(m2, srcDst), _mm_and_si128(m2, plus));
            srcDst = _mm_or_si128(_mm_andnot_si128(m3, srcDst), _mm_and_si128(m3, slash));

            _mm_storeu_si128((__m128i*)(pDst + i), srcDst);
        }
    }
#elif defined(SIMDUTF_IS_ARM64)
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

#if defined(PYBASE64_HAS_SSE2)
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
#elif defined(SIMDUTF_IS_ARM64)
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

static bool check_excess_data(const uint8_t** pSrc, size_t* pSrclen, IgnoreChars const& ignorechars)
{
    uint8_t const* src = *pSrc;
    size_t srclen = *pSrclen;
    while (srclen && ignorechars.ignore(*src)) {
        src++;
        srclen--;
    }
    *pSrc = src;
    *pSrclen = srclen;
    return srclen > 0;
}

static int next_valid_padding(uint8_t const** pSrc, size_t* pSrclen, IgnoreChars const& ignorechars)
{
    int ret = 255;
    uint8_t const* src = *pSrc;
    size_t srclen = *pSrclen;
    while (srclen && (*src != '=') && ignorechars.ignore(*src)) {
        src++;
        srclen--;
    }
    if (srclen > 0) {
        ret = base64_table_dec_8bit[*src++];
        srclen--;
    }
    *pSrc = src;
    *pSrclen = srclen;
    return ret;
}

static int decode_slow(const char* src_, size_t srclen, char* out_, size_t& outlen, BufferInput const& ignorechars_, bool padded, bool canonical)
{
    const uint8_t *src = reinterpret_cast<const uint8_t*>(src_);
    uint8_t* out = reinterpret_cast<uint8_t*>(out_);
    uint8_t* out_start = out;
    uint8_t carry = 0U;
    IgnoreChars const ignorechars{ ignorechars_ };

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
                if (ignorechars.ignore(c)) {
                    continue;
                }
                if (q == 254) {
                    if((out - out_start) == 0) {
                        return PYBASE64_DECODE_SLOW_LEADING_PADDING;
                    }
                    return PYBASE64_DECODE_SLOW_EXCESS_PADDING;
                }
                return PYBASE64_DECODE_SLOW_INVALID_DATA;
            }
            carry = q << 2;
        }
        /* case bytes == 1 */
        for(;;)
        {
            if (srclen-- == 0) {
                return PYBASE64_DECODE_SLOW_INVALID_LEN;
            }
            uint8_t c = *src++;
            uint8_t q;
            if ((q = base64_table_dec_8bit[c]) >= 254) {
                if (ignorechars.ignore(c)) {
                    continue;
                }
                return PYBASE64_DECODE_SLOW_INVALID_DATA;
            }
            *out++ = carry | (q >> 4);
            carry = q << 4;
            break;
        }
        /* case bytes == 2 */
        for(;;)
        {
            if (srclen-- == 0) {
                if (!padded) {
                    goto END;
                }
                return PYBASE64_DECODE_SLOW_INCORRECT_PADDING;
            }
            uint8_t c = *src++;
            uint8_t q;
            if ((q = base64_table_dec_8bit[c]) >= 254) {
                if (q == 254) {  /* padding */
                    /* if the next valid byte is '=' => end or skip depending on '=' being in ignorechars */
                    uint8_t const* src_next = src;
                    size_t srclen_next = srclen;
                    if (!padded && !ignorechars.ignore(c)) {
                        return PYBASE64_DECODE_SLOW_PADDING_NOT_ALLOWED;
                    }
                    if (srclen == 0) {
                        if (!padded) {
                            goto END;
                        }
                        return PYBASE64_DECODE_SLOW_INCORRECT_PADDING;
                    }
                    if (next_valid_padding(&src_next, &srclen_next, ignorechars) == 254) {
                        if (check_excess_data(&src_next, &srclen_next, ignorechars)) {
                            if (ignorechars.ignore('=')) {
                                /* restart at excess data */
                                src = src_next;
                                srclen = srclen_next;
                                continue;
                            }
                            if (*src_next == '=') {
                                return PYBASE64_DECODE_SLOW_EXCESS_PADDING;
                            }
                            return PYBASE64_DECODE_SLOW_EXCESS_DATA;
                        }
                        goto END;
                    }
                    else if (!ignorechars.ignore('=')) {
                        return PYBASE64_DECODE_SLOW_DISCONTINUOUS_PADDING;
                    }
                }
                if (ignorechars.ignore(c)) {
                    continue;
                }
                return PYBASE64_DECODE_SLOW_INVALID_DATA;
            }
            *out++ = carry | (q >> 2);
            carry = q << 6;
            break;
        }
        /* case bytes == 3 */
        for(;;)
        {
            if (srclen-- == 0) {
                if (!padded) {
                    goto END;
                }
                return PYBASE64_DECODE_SLOW_INCORRECT_PADDING;
            }
            uint8_t c = *src++;
            uint8_t q;
            if ((q = base64_table_dec_8bit[c]) >= 254) {
                if (q == 254) {  /* padding */
                    if (!padded && !ignorechars.ignore('=')) {
                        return PYBASE64_DECODE_SLOW_PADDING_NOT_ALLOWED;
                    }
                    if (check_excess_data(&src, &srclen, ignorechars)) {
                        if (ignorechars.ignore('=')) {
                            continue;
                        }
                        if (*src == '=') {
                            return PYBASE64_DECODE_SLOW_EXCESS_PADDING;
                        }
                        return PYBASE64_DECODE_SLOW_EXCESS_DATA;
                    }
                    srclen = 0U;
                    break;
                }
                if (ignorechars.ignore(c)) {
                    continue;
                }
                return PYBASE64_DECODE_SLOW_INVALID_DATA;
            }
            *out++ = carry | q;
            carry = 0U;
            break;
        }
    }
END:
    if (canonical & (carry != 0U)) {
        return PYBASE64_DECODE_SLOW_PADDING_BITS_NOT_ALLOWED;
    }
    outlen = out - out_start;
    return PYBASE64_DECODE_SLOW_SUCCESS;
}

template<class Writer>
inline static PyObject* encode_impl_core(PyObject* self, BufferInput& in, char const* alphabet, Py_ssize_t wrapcol, simdutf::base64_options options)
{
    /* if alphabet is non null, we must use simdutf standard alphabet */
    assert((alphabet == nullptr) || (options == simdutf::base64_default) || (options == simdutf::base64_default_no_padding));
    if (wrapcol < 0) {
        PyErr_SetString(PyExc_ValueError, "wrapcol must be >= 0");
        return nullptr;
    }

    State *state = GetState(self);
    if (state == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 2/4 */
        return nullptr; /* GCOVR_EXCL_LINE */
    }

    if (in.size == 0) {
        return Writer::empty(state);
    }

    if (wrapcol > 0) {
        /* round down except for low value which are rounded up */
        wrapcol = (wrapcol < 4) ? 4U : (((size_t)wrapcol / 4U) * 4U);
    }

    auto const implementation = state->active_implementation;

    size_t out_len = (wrapcol > 0) ?
        simdutf::base64_length_from_binary_with_lines(in.size, options, wrapcol) :
        implementation->base64_length_from_binary(in.size, options);

    /* overflow check signed vs unisgned */
    if (out_len > size_t(PY_SSIZE_T_MAX)) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 2/4 */
        return PyErr_NoMemory(); /* GCOVR_EXCL_LINE */
    }

    Writer writer;
    if (!writer.create(Py_ssize_t(out_len))) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 2/4 */
        return nullptr; /* GCOVR_EXCL_LINE */
    }

    {
        /* not interacting with Python objects from here, release the GIL */
        AllowThreads _{in.size};

        if (wrapcol) {
            if (alphabet) {
                /* TODO, make this more efficient */
                const size_t dst_slice = (size_t)wrapcol + 1U;
                const size_t src_slice = (dst_slice / 4U) * 3U;
                size_t len = in.size;
                const char* src = in.data;
                char* dst = writer.data;

                while (out_len > dst_slice) {
                    size_t dst_len = (size_t)wrapcol;

                    implementation->binary_to_base64(src, src_slice, dst, options);
                    translate_inplace(dst, dst_len, alphabet);
                    dst[dst_len] = '\n';

                    len -= src_slice;
                    src += src_slice;
                    out_len -= dst_slice;
                    dst += dst_slice;
                }
                implementation->binary_to_base64(src, len, dst, options);
                translate_inplace(dst, out_len, alphabet);
            }
            else {
                implementation->binary_to_base64_with_lines(in.data, in.size, writer.data, wrapcol, options);
            }
        }
        else if (alphabet) {
            /* TODO, make this more efficient */
            const size_t dst_slice = 16U * 1024U;
            const size_t src_slice = (dst_slice / 4U) * 3U;
            size_t len = in.size;
            const char* src = in.data;
            char* dst = writer.data;

            while (out_len > dst_slice) {
                implementation->binary_to_base64(src, src_slice, dst, options);
                translate_inplace(dst, dst_slice, alphabet);

                len -= src_slice;
                src += src_slice;
                out_len -= dst_slice;
                dst += dst_slice;
            }
            implementation->binary_to_base64(src, len, dst, options);
            translate_inplace(dst, out_len, alphabet);
        }
        else {
            implementation->binary_to_base64(in.data, in.size, writer.data, options);
        }
    }

    return writer.finish();
}

template<class Writer>
static PyObject* encode_impl(PyObject* self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    static constexpr std::string_view arg_names[] = { "s", "altchars", "padded", "wrapcol" };
    PyObject* parsed_args[4];
    if (!fastcall_parse_args<1, 2, 4>(args, nargs, kwnames, arg_names, parsed_args)) {
        return nullptr;
    }
    BufferInput in;
    if (!in.from_buffer<false>(parsed_args[0])) {
        return nullptr;
    }
    char alphabet_[2];
    char const* alphabet;
    if (!parse_alphabet(parsed_args[1], alphabet_, alphabet)) {
        return nullptr;
    }

    int padded = 1;
    if (parsed_args[2]) {
        padded = PyObject_IsTrue(parsed_args[2]);
        if (padded < 0) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 2/4 */
            return nullptr; /* GCOVR_EXCL_LINE */
        }
    }

    simdutf::base64_options options = padded ? simdutf::base64_default : simdutf::base64_default_no_padding;
    if (alphabet == url_alphabet) {
        alphabet = nullptr;
        options = padded ? simdutf::base64_url_with_padding : simdutf::base64_url;
    }

    Py_ssize_t wrapcol = 0;
    if (parsed_args[3]) {
        wrapcol = PyLong_AsSsize_t(parsed_args[3]);
        if (PyErr_Occurred()) {
            return nullptr;
        }
    }

    return encode_impl_core<Writer>(self, in, alphabet, wrapcol, options);
}

static PyObject* b64encode(PyObject* self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return encode_impl<BytesWriter>(self, args, nargs, kwnames);
}

static PyObject* b64encode_as_string(PyObject* self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return encode_impl<StringWriter>(self, args, nargs, kwnames);
}

static PyObject* standard_b64encode(PyObject* self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    static constexpr std::string_view arg_names[] = { "s" };
    PyObject* parsed_args[1];
    if (!fastcall_parse_args<1, 1, 1>(args, nargs, kwnames, arg_names, parsed_args)) {
        return nullptr;
    }
    BufferInput in;
    if (!in.from_buffer<false>(parsed_args[0])) {
        return nullptr;
    }
    return encode_impl_core<BytesWriter>(self, in, nullptr, 0, simdutf::base64_default);
}

static PyObject* urlsafe_b64encode(PyObject* self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    static constexpr std::string_view arg_names[] = { "s", "padded" };
    PyObject* parsed_args[2];
    if (!fastcall_parse_args<1, 1, 2>(args, nargs, kwnames, arg_names, parsed_args)) {
        return nullptr;
    }
    BufferInput in;
    if (!in.from_buffer<false>(parsed_args[0])) {
        return nullptr;
    }
    int padded = 1;
    if (parsed_args[1]) {
        padded = PyObject_IsTrue(parsed_args[1]);
        if (padded < 0) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
            return nullptr; /* GCOVR_EXCL_LINE */
        }
    }
    simdutf::base64_options options = padded ? simdutf::base64_url_with_padding : simdutf::base64_url;
    return encode_impl_core<BytesWriter>(self, in, nullptr, 0, options);
}

static PyObject* encodebytes(PyObject* self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    static constexpr std::string_view arg_names[] = { "s" };
    PyObject* parsed_args[1];
    if (!fastcall_parse_args<1, 1, 1>(args, nargs, kwnames, arg_names, parsed_args)) {
        return nullptr;
    }
    BufferInput in;
    if (!in.from_buffer<true>(parsed_args[0])) {
        return nullptr;
    }
    State* state = GetState(self);
    if (state == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        return nullptr; /* GCOVR_EXCL_LINE */
    }
    if (in.size == 0) {
        return BytesWriter::empty(state);
    }

    constexpr size_t wrapcol = 76;
    constexpr auto options = simdutf::base64_default;
    size_t out_len = simdutf::base64_length_from_binary_with_lines(in.size, options, wrapcol);
    if (out_len > ((size_t)PY_SSIZE_T_MAX - 1U)) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        return PyErr_NoMemory(); /* GCOVR_EXCL_LINE */
    }

    BytesWriter writer;
    if (!writer.create(Py_ssize_t(out_len + 1U))) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        return nullptr; /* GCOVR_EXCL_LINE */
    }

    {
        /* not interacting with Python objects from here, release the GIL */
        AllowThreads _{in.size};
        state->active_implementation->binary_to_base64_with_lines(in.data, in.size, writer.data, wrapcol, options);
        writer.data[out_len] = '\n';
    }

    return writer.finish();
}


template<class T>
static bool swap_input(T& buffer, PyObject* bytes_stolen_ref)
{
    if (bytes_stolen_ref == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 2/4 */
        return false; /* GCOVR_EXCL_LINE */
    }
    /* swap input, always use a buffer to decref translate_object */
    if (buffer._has_buffer) {
        PyBuffer_Release(&buffer._buffer);
        buffer._has_buffer = false;
    }
    if (PyObject_GetBuffer(bytes_stolen_ref, &buffer._buffer, PyBUF_SIMPLE) != 0) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 2/4 */
        return false; /* GCOVR_EXCL_LINE */
    }
    Py_DECREF(bytes_stolen_ref);
    buffer._has_buffer = true;
    buffer.data = static_cast<char const*>(buffer._buffer.buf);
    return true;
}

static bool get_ignorechars_buffer(PyObject* object, BufferInput& buffer, char const* alphabet)
{
    if (!buffer.from_buffer<true>(object) != 0) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        return false; /* GCOVR_EXCL_LINE */
    }
    if ((buffer.size == 0) || (alphabet == nullptr)) {
        return true;
    }
    BytesWriter writer;
    if (!writer.create(Py_ssize_t(buffer.size))) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        return false; /* GCOVR_EXCL_LINE */
    }
    translate(buffer.data, writer.data, buffer.size, alphabet, nullptr);
    return swap_input(buffer, writer.finish());
}

static void validate_result(simdutf::result& result, char const* in, size_t in_length, bool padded)
{
    assert(in_length > 0); /* size 0 uses a fast path */
    if (result.is_err()) {
        return;
    }
    /* check no characters skipped */
    size_t remainder = in_length % 4;
    if (padded) {
        if (remainder) {
            result.error = simdutf::error_code::INVALID_BASE64_CHARACTER;
            return;
        }
        size_t padding = 0;
        while (in[in_length - 1 - padding] == '=') {
            padding++;
            assert(padding < in_length); /* simdutf doesn't accept an input full of '=' */
        }
        if ((result.count + padding) != ((in_length / 4) * 3)) {
            result.error = simdutf::error_code::INVALID_BASE64_CHARACTER;
        }
        return;
    }
    /* unpadded */
    if (in[in_length - 1] == '=') {
        result.error = simdutf::error_code::INVALID_BASE64_CHARACTER;
        return;
    }
    size_t expected_len = SIZE_MAX;
    switch (remainder)
    {
    case 0:
        expected_len = (in_length / 4) * 3;
        break;
    case 2:
        expected_len = (in_length / 4) * 3 + 1;
        break;
    case 3:
        expected_len = (in_length / 4) * 3 + 2;
        break;
    }
    if (result.count != expected_len) {
        result.error = simdutf::error_code::INVALID_BASE64_CHARACTER;
    }
}

template<class Writer>
static PyObject* decode_impl_core(PyObject* self, BufferOrStrInput& in, char const* alphabet, PyObject* validation_object, PyObject* ignorechars_object, bool padded, bool canonical)
{
    bool const user_ignorechars = (ignorechars_object != nullptr);

    bool validation;
    if (validation_object == nullptr) {
        validation = user_ignorechars;
    }
    else {
        int validation_ = PyObject_IsTrue(validation_object);
        if (validation_ < 0) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 2/4 */
            return nullptr; /* GCOVR_EXCL_LINE */
        }
        validation = validation_ != 0;
        if (user_ignorechars && !validation) {
            PyErr_SetString(PyExc_ValueError, "validate must be True or unspecified when ignorechars is specified");
            return nullptr;
        }
    }

    /* default to fast path when validation is true */
    bool fast_path = validation;

    State *state = GetState(self);
    if (state == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 2/4 */
        return nullptr; /* GCOVR_EXCL_LINE */
    }

    bool use_alphabet_for_ignore_chars = (alphabet !=  nullptr);
    if (!validation) {
        assert(ignorechars_object == nullptr);
        ignorechars_object = state->ignoreCharsValidateFalse;
        use_alphabet_for_ignore_chars = false;
    }

    BufferInput ignorechars;
    int has_bad_char = 0;
    void (*translate_fn)(const char*, char*, size_t, const char*, int*) = &translate_deprecated;
    simdutf::base64_options options = padded ? simdutf::base64_default : simdutf::base64_default_no_padding;
    if (ignorechars_object != nullptr) {
        if (!get_ignorechars_buffer(ignorechars_object, ignorechars, use_alphabet_for_ignore_chars ? alphabet : nullptr)) {
            return nullptr;
        }
        if (user_ignorechars) {
            translate_fn = &translate;
            if ((ignorechars.size == 0) & (alphabet == url_alphabet)) {
                options = padded ? simdutf::base64_url_with_padding : simdutf::base64_url;
                alphabet = nullptr;
            }
        }
        fast_path = (ignorechars.size == 0);
    }

    if (in.size == 0) {
        return Writer::empty(state);
    }

    auto const implementation = state->active_implementation;

    /* exact out_len recomputed at the end */
    size_t out_len = implementation->maximal_binary_length_from_base64(in.data, in.size);
    Writer writer;
    if (!writer.create(Py_ssize_t(out_len))) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 2/4 */
        return nullptr; /* GCOVR_EXCL_LINE */
    }

    auto const lcho = canonical ? simdutf::strict : simdutf::loose;
    if (fast_path) {
        simdutf::result result{};
        if (alphabet != nullptr) {
            /* not interacting with Python objects from here, release the GIL */
            AllowThreads _{in.size};
            /* TODO, make this more efficient */
            constexpr size_t src_slice = 16 * 1024;
            constexpr size_t dst_slice = (src_slice / 4) * 3;
            char cache[src_slice];
            size_t len = in.size;
            const char* src = in.data;
            char* dst = writer.data;
            while (len > src_slice) {
                translate_fn(src, cache, src_slice, alphabet, &has_bad_char);
                result = implementation->base64_to_binary(
                    cache, src_slice, dst, simdutf::base64_default_no_padding, simdutf::strict
                );
                if ((result.count != dst_slice) | result.is_err()) {
                    if (result.is_ok()) {
                        result.error = simdutf::error_code::INVALID_BASE64_CHARACTER;
                    }
                    break;
                }
                len -= src_slice;
                src += src_slice;
                dst += dst_slice;
            }
            if (result.is_ok()) {
                translate_fn(src, cache, len, alphabet, &has_bad_char);
                result = implementation->base64_to_binary(cache, len, dst, options, lcho);
                validate_result(result, cache, len, padded);
                out_len = result.count + (dst - writer.data);
            }
        }
        else {
            /* not interacting with Python objects from here, release the GIL */
            AllowThreads _{in.size};
            result = implementation->base64_to_binary(in.data, in.size, writer.data, options, lcho);
            validate_result(result, in.data, in.size, padded);
            out_len = result.count;
        }
        if (result.is_err()) {
            switch (result.error)
            {
            case simdutf::error_code::BASE64_EXTRA_BITS:
                PyErr_SetString(state->binAsciiError, "Non-zero padding bits");
                break;
            default:
                PyErr_SetString(state->binAsciiError, "Non-base64 digit found");
                break;
            }
            return nullptr;
        }
    }
    else {
        assert((user_ignorechars || !validation) && (ignorechars_object != nullptr));
        bool use_fallback = true;
        bool try_simdutf = false;
        if ((alphabet == nullptr) | (alphabet == url_alphabet)) {
            if (ignorechars_object == state->ignoreCharsValidateFalse) {
                try_simdutf = true;
            }
            else if ((in.size / 2) > ignorechars.size) {
                constexpr uint64_t one = 1;
                constexpr uint64_t skip_mask = one << ' ' | one << '\t' | one << '\f' | one << '\r' | one << '\n';
                uint64_t mask = 0;
                for (size_t i = 0; i < ignorechars.size; ++i) {
                    mask |= one << std::min(static_cast<int>(ignorechars.data[i]), 63);
                }
                try_simdutf = (mask & skip_mask) == skip_mask;
            }
        }
        if (try_simdutf) {
            /* try with simdutf in default mode */
            AllowThreads _{in.size};
            if (alphabet != nullptr) {
                options = padded ? simdutf::base64_url_with_padding : simdutf::base64_url;
            }
            auto result = implementation->base64_to_binary(in.data, in.size, writer.data, options, lcho);
            if (result.is_ok()) {
                bool padding_ok = true;
                if (padded && (lcho != simdutf::strict)) {
                    size_t end = in.size;
                    while ((end > 0) && simdutf::base64_ignorable(in.data[end - 1], simdutf::base64_options::base64_default)) {
                      end--;
                    }
                    size_t padding = 0;
                    while ((padding < end) && (in.data[end - 1 - padding] == '=')) {
                      padding++;
                    }
                    static const size_t expected_padding[3] = {0, 2, 1};
                    padding_ok = padding == expected_padding[result.count % 3];
                }
                if (padding_ok) {
                    use_fallback = false;
                    out_len = result.count;
                }
            }
        }
        if (use_fallback)  {
            if (alphabet != nullptr) {
                BytesWriter translate_writer;

                if (!translate_writer.create(Py_ssize_t(in.size))) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 2/4 */
                    return nullptr; /* GCOVR_EXCL_LINE */
                }

                {
                    /* not interacting with Python objects from here, release the GIL */
                    AllowThreads _{in.size};
                    translate_fn(in.data, translate_writer.data, in.size, alphabet, &has_bad_char);
                }

                if (!swap_input(in, translate_writer.finish())) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 2/4 */
                    return nullptr; /* GCOVR_EXCL_LINE */
                }
            }

            int result;
            {
                /* not interacting with Python objects from here, release the GIL */
                AllowThreads _{in.size};
                result = decode_slow(in.data, in.size, writer.data, out_len, ignorechars, padded, canonical);
            }

            if (result != PYBASE64_DECODE_SLOW_SUCCESS) {
                switch(result) /* GCOVR_EXCL_BR_WITHOUT_HIT: 2/20 */
                {
                case PYBASE64_DECODE_SLOW_INCORRECT_PADDING:
                    PyErr_SetString(state->binAsciiError, "Incorrect padding");
                    break;
                case PYBASE64_DECODE_SLOW_EXCESS_DATA:
                    PyErr_SetString(state->binAsciiError, "Excess data after padding");
                    break;
                case PYBASE64_DECODE_SLOW_LEADING_PADDING:
                    PyErr_SetString(state->binAsciiError, "Leading padding");
                    break;
                case PYBASE64_DECODE_SLOW_DISCONTINUOUS_PADDING:
                    PyErr_SetString(state->binAsciiError, "Discontinuous padding");
                    break;
                case PYBASE64_DECODE_SLOW_EXCESS_PADDING:
                    PyErr_SetString(state->binAsciiError, "Excess padding");
                    break;
                case PYBASE64_DECODE_SLOW_INVALID_LEN:
                    PyErr_SetString(state->binAsciiError, "Invalid number of data characters");
                    break;
                case PYBASE64_DECODE_SLOW_INVALID_DATA:
                    PyErr_SetString(state->binAsciiError, "Non-base64 digit found");
                    break;
                case PYBASE64_DECODE_SLOW_PADDING_NOT_ALLOWED:
                    PyErr_SetString(state->binAsciiError, "Padding not allowed");
                    break;
                case PYBASE64_DECODE_SLOW_PADDING_BITS_NOT_ALLOWED:
                    PyErr_SetString(state->binAsciiError, "Non-zero padding bits");
                    break;
                }
                return nullptr;
            }
        }
    }
    PyObject* out_object = writer.finish(out_len);
    if (has_bad_char & (out_object != nullptr)) {
        static const char format_validation[] = "invalid characters '+' or '/' in Base64 data with altchars='%c%c' and validate=True will be an error in future versions";
        static const char format_no_validation[] = "invalid characters '+' or '/' in Base64 data with altchars='%c%c' and validate=False will be discarded in future versions";
        char const* format = validation ? format_validation : format_no_validation;
        PyObject* category = validation ? PyExc_DeprecationWarning : PyExc_FutureWarning;
        if (PyErr_WarnFormat(category, 2, format, alphabet[0], alphabet[1]) < 0) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 2/4 */
            Py_XDECREF(out_object); /* GCOVR_EXCL_LINE */
            out_object = nullptr; /* GCOVR_EXCL_LINE */
        }
    }
    return out_object;
}

template<class Writer>
static PyObject* decode_impl(PyObject* self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    static constexpr std::string_view arg_names[] = { "s", "altchars", "validate", "padded", "ignorechars", "canonical" };
    PyObject* parsed_args[6];
    if (!fastcall_parse_args<1, 3, 6>(args, nargs, kwnames, arg_names, parsed_args)) {
        return nullptr;
    }
    BufferOrStrInput in;
    if (!in.from_buffer_or_str<false>(parsed_args[0])) {
        return nullptr;
    }
    char alphabet_[2];
    char const* alphabet;
    if (!parse_alphabet(parsed_args[1], alphabet_, alphabet)) {
        return nullptr;
    }
    PyObject* validation_object = parsed_args[2];
    bool padded = true;
    if (parsed_args[3]) {
        int padded_ = PyObject_IsTrue(parsed_args[3]);
        if (padded_ < 0) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 2/4 */
            return nullptr; /* GCOVR_EXCL_LINE */
        }
        padded = padded_ != 0;
    }
    PyObject* ignorechars_object = parsed_args[4];
    bool canonical = false;
    if (parsed_args[5]) {
        int canonical_ = PyObject_IsTrue(parsed_args[5]);
        if (canonical_ < 0) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 2/4 */
            return nullptr; /* GCOVR_EXCL_LINE */
        }
        canonical = canonical_ != 0;
    }
    return decode_impl_core<Writer>(self, in, alphabet, validation_object, ignorechars_object, padded, canonical);
}

static PyObject* b64decode(PyObject* self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return decode_impl<BytesWriter>(self, args, nargs, kwnames);
}

static PyObject* b64decode_as_bytearray(PyObject* self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return decode_impl<ByteArrayWriter>(self, args, nargs, kwnames);
}

static PyObject* standard_b64decode(PyObject* self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    static constexpr std::string_view arg_names[] = { "s" };
    PyObject* parsed_args[1];
    if (!fastcall_parse_args<1, 1, 1>(args, nargs, kwnames, arg_names, parsed_args)) {
        return nullptr;
    }
    BufferOrStrInput in;
    if (!in.from_buffer_or_str<false>(parsed_args[0])) {
        return nullptr;
    }
    return decode_impl_core<BytesWriter>(self, in, nullptr, nullptr, nullptr, true, false);
}

static PyObject* urlsafe_b64decode(PyObject* self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    static constexpr std::string_view arg_names[] = { "s", "padded" };
    PyObject* parsed_args[2];
    if (!fastcall_parse_args<1, 1, 2>(args, nargs, kwnames, arg_names, parsed_args)) {
        return nullptr;
    }
    BufferOrStrInput in;
    if (!in.from_buffer_or_str<false>(parsed_args[0])) {
        return nullptr;
    }
    bool padded = false;
    if (parsed_args[1]) {
        int padded_ = PyObject_IsTrue(parsed_args[1]);
        if (padded_ < 0) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
            return nullptr; /* GCOVR_EXCL_LINE */
        }
        padded = padded_ != 0;
    }
    return decode_impl_core<BytesWriter>(self, in, url_alphabet, nullptr, nullptr, padded, false);
}

static PyObject* decodebytes(PyObject* self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    static constexpr std::string_view arg_names[] = { "s" };
    PyObject* parsed_args[1];
    if (!fastcall_parse_args<1, 1, 1>(args, nargs, kwnames, arg_names, parsed_args)) {
        return nullptr;
    }
    BufferOrStrInput in;
    if (!in.from_buffer<true>(parsed_args[0])) {
        return nullptr;
    }
    return decode_impl_core<BytesWriter>(self, in, nullptr, nullptr, nullptr, true, false);
}

static PyObject* _get_simd_path(PyObject* self, PyObject* arg)
{
    State *state = GetState(self);
    if (state == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        return nullptr; /* GCOVR_EXCL_LINE */
    }
    auto const& name = state->active_implementation->name();
    return PyUnicode_FromStringAndSize(name.data(), name.size());
}

static PyObject* _get_simd_paths_runtime(PyObject* self, PyObject* arg)
{
    PyObject* result = PyTuple_New(implementations.size());
    if (result == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        return nullptr; /* GCOVR_EXCL_LINE */
    }
    Py_ssize_t pos = 0;
    for (auto const& implementation: implementations) {
        if (!implementation->supported_by_runtime_system()) {
            continue;
        }
        auto const& name = implementation->name();
        PyObject* name_object = PyUnicode_FromStringAndSize(name.data(), name.size());
        if (name_object == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
            /* GCOVR_EXCL_START */
            Py_DECREF(result);
            return nullptr;
            /* GCOVR_EXCL_STOP */
        }
        if (PyTuple_SetItem(result, pos++, name_object) != 0) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
            /* GCOVR_EXCL_START */
            Py_DECREF(name_object);
            Py_DECREF(result);
            return nullptr;
            /* GCOVR_EXCL_STOP */
        }
    }
    PyObject* old_result = result;
    if (_PyTuple_Resize(&result, pos) != 0) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        /* GCOVR_EXCL_START */
        Py_DECREF(old_result);
        return nullptr;
        /* GCOVR_EXCL_STOP */
    }
    return result;
}

static PyObject* _get_simd_paths_compile(PyObject* self, PyObject* arg)
{
    PyObject* result = PyTuple_New(implementations.size());
    if (result == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        return result; /* GCOVR_EXCL_LINE */
    }
    Py_ssize_t pos = 0;
    for (auto const& implementation: implementations) {
        auto const& name = implementation->name();
        PyObject* name_object = PyUnicode_FromStringAndSize(name.data(), name.size());
        if (name_object == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
            /* GCOVR_EXCL_START */
            Py_DECREF(result);
            return nullptr;
            /* GCOVR_EXCL_STOP */
        }
        if (PyTuple_SetItem(result, pos++, name_object) != 0) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
            /* GCOVR_EXCL_START */
            Py_DECREF(name_object);
            Py_DECREF(result);
            return nullptr;
            /* GCOVR_EXCL_STOP */
        }
    }
    return result;
}

static PyObject* _get_version_metadata(PyObject* self, PyObject* arg)
{
    State *state = GetState(self);
    if (state == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        return nullptr; /* GCOVR_EXCL_LINE */
    }
    auto const& name = state->active_implementation->name();

    return PyUnicode_FromFormat("C extension active - simdutf " SIMDUTF_VERSION " - %s", name.data());
}

static PyObject* _set_simd_path(PyObject* self, PyObject* arg)
{
    State *state = GetState(self);
    if (state == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        return nullptr; /* GCOVR_EXCL_LINE */
    }
    Py_ssize_t size;
    char const* data = PyUnicode_AsUTF8AndSize(arg, &size);
    if (data == nullptr) {
        return nullptr;
    }
    std::string_view name{data, static_cast<size_t>(size)};
    simdutf::implementation const* const implementation = implementations[name];
    if (implementation == nullptr) {
        return PyErr_Format(PyExc_LookupError, "can't find implementation %R", arg);
    }
#if PY_VERSION_HEX >= 0x030d0000
    static PyMutex mutex = {0};
    PyMutex_Lock(&mutex);
#endif
    if (implementation != state->active_implementation) {
        state->active_implementation = implementation;
    }
#if PY_VERSION_HEX >= 0x030d0000
    PyMutex_Unlock(&mutex);
#endif
    Py_RETURN_NONE;
}

static PyObject* from_import(const char* from, const char* object)
{
    PyObject* subModules;
    PyObject* subModuleName;
    PyObject* moduleName;
    PyObject* imports;
    PyObject* importedObject;

    subModules = PyList_New(1);
    if (subModules == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        return nullptr; /* GCOVR_EXCL_LINE */
    }
    moduleName = PyUnicode_FromString(from);
    if (moduleName == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        Py_DECREF(subModules); /* GCOVR_EXCL_LINE */
        return nullptr; /* GCOVR_EXCL_LINE */
    }
    subModuleName = PyUnicode_FromString(object);
    if (subModuleName == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        Py_DECREF(moduleName); /* GCOVR_EXCL_LINE */
        Py_DECREF(subModules); /* GCOVR_EXCL_LINE */
        return nullptr; /* GCOVR_EXCL_LINE */
    }
    Py_INCREF(subModuleName);
    PyList_SET_ITEM(subModules, 0, subModuleName);
    imports = PyImport_ImportModuleLevelObject(moduleName, nullptr, nullptr, subModules, 0);
    Py_DECREF(moduleName);
    Py_DECREF(subModules);
    if (imports == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        Py_DECREF(subModuleName); /* GCOVR_EXCL_LINE */
        return nullptr; /* GCOVR_EXCL_LINE */
    }
    importedObject = PyObject_GetAttr(imports, subModuleName);
    Py_DECREF(subModuleName);
    Py_DECREF(imports);
    return importedObject;
}

static PyObject* import_BinAsciiError()
{
    PyObject* binAsciiError;
    int subclassResult;

    binAsciiError = from_import("binascii", "Error");
    if (binAsciiError == nullptr) {
        return nullptr;
    }
    subclassResult = PyObject_IsSubclass(binAsciiError, PyExc_Exception);
    if (subclassResult != 1) {
        Py_DECREF(binAsciiError);
        PyErr_SetString(PyExc_TypeError, "binascii.Error is not a subclass of Exception");
        return nullptr;
    }

    return binAsciiError;
}

static int mod_exec(PyObject *m)
{
    static uint8_t const ignoreCharsValidateFalse[] = {
          0,   1,   2,   3,   4,   5,   6,   7,   8,   9,  10,  11,  12,  13,  14,  15,
         16,  17,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,  28,  29,  30,  31,
         32,  33,  34,  35,  36,  37,  38,  39,  40,  41,  42,       44,  45,  46,      /* 43: '+', 47: '/' */
         /* 48: '0' -> 57: '9' */                          58,  59,  60,  61,  62,  63,
         64, /* 65: 'A' -> 90: 'Z' */
                                                                91,  92,  93,  94,  95,
         96, /* 97: 'a' -> 122: 'z' */
                                                               123, 124, 125, 126, 127,
        128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143,
        144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159,
        160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175,
        176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191,
        192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207,
        208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223,
        224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239,
        240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255,
    };
    State *state = GetState(m);
    if (state == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        return -1; /* GCOVR_EXCL_LINE */
    }

    state->active_implementation = best_implementation;

    assert(sizeof(ignoreCharsValidateFalse) == (256 - 64));
    state->ignoreCharsValidateFalse = PyBytes_FromStringAndSize((const char*)ignoreCharsValidateFalse, sizeof(ignoreCharsValidateFalse));
    if (state->ignoreCharsValidateFalse == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        return -1; /* GCOVR_EXCL_LINE */
    }

#if PY_VERSION_HEX >= 0x030d0000
    state->emptyBytes = Py_GetConstant(Py_CONSTANT_EMPTY_BYTES);
#else
    state->emptyBytes = PyBytes_FromStringAndSize(nullptr, 0);
#endif
    if (state->emptyBytes == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        return -1; /* GCOVR_EXCL_LINE */
    }

#if PY_VERSION_HEX >= 0x030d0000
    state->emptyStr = Py_GetConstant(Py_CONSTANT_EMPTY_STR);
#else
    state->emptyStr = PyUnicode_FromStringAndSize(nullptr, 0);
#endif
    if (state->emptyStr == nullptr) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        return -1; /* GCOVR_EXCL_LINE */
    }

    state->binAsciiError = import_BinAsciiError();
    if (state->binAsciiError == nullptr) {
        return -1;
    }

    Py_INCREF(state->binAsciiError); /* PyModule_AddObject steals a reference */
    if (PyModule_AddObject(m, "_BinAsciiError", state->binAsciiError) != 0) { /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        Py_DECREF(state->binAsciiError); /* GCOVR_EXCL_LINE */
        return -1; /* GCOVR_EXCL_LINE */
    }

    return 0;
}

static int mod_state_traverse(PyObject *m, visitproc visit, void *arg)
{
    State *state = GetState(m);
    if (state) {  /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        Py_VISIT(state->binAsciiError);
        Py_VISIT(state->emptyBytes);
        Py_VISIT(state->emptyStr);
        Py_VISIT(state->ignoreCharsValidateFalse);
    }
    return 0;
}

static int mod_state_clear(PyObject *m)
{
    State *state = GetState(m);
    if (state) {  /* GCOVR_EXCL_BR_WITHOUT_HIT: 1/2 */
        Py_CLEAR(state->binAsciiError);
        Py_CLEAR(state->emptyBytes);
        Py_CLEAR(state->emptyStr);
        Py_CLEAR(state->ignoreCharsValidateFalse);
    }
    return 0;
}

static void mod_state_free(void *m)
{
    mod_state_clear((PyObject *)m);
}

static PyMethodDef mod_methods[] = {
    { "b64encode", (PyCFunction)b64encode, METH_FASTCALL | METH_KEYWORDS, nullptr },
    { "b64encode_as_string", (PyCFunction)b64encode_as_string, METH_FASTCALL | METH_KEYWORDS, nullptr },
    { "b64decode", (PyCFunction)b64decode, METH_FASTCALL | METH_KEYWORDS, nullptr },
    { "b64decode_as_bytearray", (PyCFunction)b64decode_as_bytearray, METH_FASTCALL | METH_KEYWORDS, nullptr },
    { "decodebytes", (PyCFunction)decodebytes, METH_FASTCALL | METH_KEYWORDS, nullptr },
    { "encodebytes", (PyCFunction)encodebytes, METH_FASTCALL | METH_KEYWORDS, nullptr },
    { "standard_b64decode", (PyCFunction)standard_b64decode, METH_FASTCALL | METH_KEYWORDS, nullptr },
    { "standard_b64encode", (PyCFunction)standard_b64encode, METH_FASTCALL | METH_KEYWORDS, nullptr },
    { "urlsafe_b64decode", (PyCFunction)urlsafe_b64decode, METH_FASTCALL | METH_KEYWORDS, nullptr },
    { "urlsafe_b64encode", (PyCFunction)urlsafe_b64encode, METH_FASTCALL | METH_KEYWORDS, nullptr },
    { "_get_simd_path", (PyCFunction)_get_simd_path, METH_NOARGS, nullptr },
    { "_get_simd_paths_compile", (PyCFunction)_get_simd_paths_compile, METH_NOARGS, nullptr },
    { "_get_simd_paths_runtime", (PyCFunction)_get_simd_paths_runtime, METH_NOARGS, nullptr },
    { "_get_version_metadata", (PyCFunction)_get_version_metadata, METH_NOARGS, nullptr },
    { "_set_simd_path", (PyCFunction)_set_simd_path, METH_O, nullptr },
    { nullptr, nullptr, 0, nullptr }  /* Sentinel */
};

/* Initialize this module. */
static char const mod_name[] = "_pybase64";
#if PY_VERSION_HEX >= 0x030f0000
PyABIInfo_VAR(abi_info);
static PySlot _pybase64_slots[] = {
    PySlot_STATIC_DATA(Py_mod_abi, &abi_info),
    PySlot_STATIC_DATA(Py_mod_name, const_cast<char*>(mod_name)),
    PySlot_STATIC_DATA(Py_mod_methods, mod_methods),
    PySlot_FUNC(Py_mod_state_traverse, mod_state_traverse),
    PySlot_FUNC(Py_mod_state_clear, mod_state_clear),
    PySlot_FUNC(Py_mod_state_free, mod_state_free),
    PySlot_FUNC(Py_mod_exec, mod_exec),
    PySlot_SIZE(Py_mod_state_size, sizeof(State)),
    PySlot_UINT64(Py_mod_multiple_interpreters, Py_MOD_PER_INTERPRETER_GIL_SUPPORTED),
    PySlot_UINT64(Py_mod_gil, Py_MOD_GIL_NOT_USED),
    PySlot_END
};
#else
static PyModuleDef_Slot mod_slots[] = {
    {Py_mod_exec, reinterpret_cast<void*>(&mod_exec)},
#ifdef Py_mod_multiple_interpreters
    {Py_mod_multiple_interpreters, Py_MOD_PER_INTERPRETER_GIL_SUPPORTED},
#endif
#ifdef Py_mod_gil
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, nullptr}
};
static struct PyModuleDef _pybase64_module = {
        PyModuleDef_HEAD_INIT,
        mod_name,
        nullptr,
        sizeof(State),
        mod_methods,
        mod_slots,
        mod_state_traverse,
        mod_state_clear,
        mod_state_free
};
#endif

}

#if PY_VERSION_HEX >= 0x030f0000
PyMODEXPORT_FUNC
PyModExport__pybase64() {
    return _pybase64_slots;
}
#else
PyMODINIT_FUNC
PyInit__pybase64(void) {
    return PyModuleDef_Init(&_pybase64_module);
}
#endif
