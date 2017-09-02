# coding: utf-8

import base64
import unittest
from binascii import Error as BinAsciiError
from sys import version_info

import pybase64
from parameterized import parameterized
from six import binary_type, text_type


try:
    from pybase64._pybase64 import _get_simd_path
    from pybase64._pybase64 import _set_simd_path
    from pybase64._pybase64 import _get_simd_flags_compile
    from pybase64._pybase64 import _get_simd_flags_runtime
    _has_extension = True
except ImportError:
    _has_extension = False

if version_info < (3, 0):
    from string import maketrans

STD = 0
URL = 1
ALT1 = 2
ALT2 = 3
ALT3 = 4
name_lut = [
    'standard', 'urlsafe', 'alternative', 'alternative2', 'alternative3'
]
altchars_lut = [b'+/', b'-_', b'@&', b'+,', b';/']
enc_helper_lut = [
    pybase64.standard_b64encode,
    pybase64.urlsafe_b64encode,
    None,
    None,
    None
]
ref_enc_helper_lut = [
    pybase64.standard_b64encode,
    pybase64.urlsafe_b64encode,
    None,
    None,
    None
]
dec_helper_lut = [
    pybase64.standard_b64decode,
    pybase64.urlsafe_b64decode,
    None,
    None,
    None
]
ref_dec_helper_lut = [
    base64.standard_b64decode,
    base64.urlsafe_b64decode,
    None,
    None,
    None
]

std = b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/A'
std = std * (32 * 16)

test_vectors_b64_list = [
    # rfc4648 test vectors
    b'',
    b'Zg==',
    b'Zm8=',
    b'Zm9v',
    b'Zm9vYg==',
    b'Zm9vYmE=',
    b'Zm9vYmFy',
    # custom test vectors
    std[len(std) - 12:],
    std
]

test_vectors_b64 = []
for altchars in altchars_lut:
    if version_info < (3, 0):
        trans = maketrans(b'+/', altchars)
    else:
        trans = binary_type.maketrans(b'+/', altchars)
    test_vectors_b64.append(
        [vector.translate(trans)
            for vector in test_vectors_b64_list])

test_vectors_bin = []
for altchars in altchars_lut:
    test_vectors_bin.append(
        [base64.b64decode(vector, altchars)
            for vector in test_vectors_b64_list])

compile_flags = [0]
runtime_flags = 0
if _has_extension:
    runtime_flags = _get_simd_flags_runtime()
    flags = _get_simd_flags_compile()
    for i in range(31):
        if flags & (1 << i):
            compile_flags += [(1 << i)]

params_helper = [
    [which, i, s]
    for s in range(len(compile_flags))
    for i in range(len(test_vectors_bin[0]))
    for which in [STD, URL]
]
params_novalidate = [
    [which, i, False, ualtchars, s]
    for s in range(len(compile_flags))
    for ualtchars in [False, True]
    for validate in [False]
    for i in range(len(test_vectors_bin[0]))
    for which in [STD, URL, ALT1, ALT2, ALT3]
]
params_validate = [
    [which, i, validate, ualtchars, s]
    for s in range(len(compile_flags))
    for ualtchars in [False, True]
    for validate in [False, True]
    for i in range(len(test_vectors_bin[0]))
    for which in [STD, URL, ALT1, ALT2, ALT3]
]
params_invalid_data = [
    [idx, s] + p
    for s in range(len(compile_flags))
    for idx, p in enumerate([
        [b'A@@@@FG', None, BinAsciiError],
        [u'ABC€', None, ValueError],
        [3.0, None, TypeError],
    ])
]
params_invalid_data_validate = [
    [idx, s] + p
    for s in range(len(compile_flags))
    for idx, p in enumerate([
        [b'\x00\x00\x00\x00', None, BinAsciiError],
        [b'A@@@@FGHIJKLMNOPQRSTUVWXYZabcdef', b'-_', BinAsciiError],
        [b'A@@@@FGH' * 10000, b'-_', BinAsciiError],
        # [std, b'-_', BinAsciiError],  TODO does no fail with base64 module
    ])
]
params_invalid_altchars = [
    [idx, s] + p
    for s in range(len(compile_flags))
    for idx, p in enumerate([
        [b'', AssertionError],
        [b'-', AssertionError],
        [b'-__', AssertionError],
        [3.0, TypeError],
        [u'-€', ValueError],
    ])
]


def get_simd_name(simd_id):
    simd_name = None
    if _has_extension:
        simd_flag = compile_flags[simd_id]
        if simd_flag == 0:
            simd_name = 'c'
        elif simd_flag == 4:
            simd_name = 'ssse3'
        elif simd_flag == 8:
            simd_name = 'sse41'
        elif simd_flag == 16:
            simd_name = 'sse42'
        elif simd_flag == 32:
            simd_name = 'avx'
        elif simd_flag == 64:
            simd_name = 'avx2'
        else:  # pragma: no branch
            simd_name = 'unk'  # pragma: no cover
    else:
        simd_name = 'py'
    return simd_name


def tc_name(testcase_func, param_num, param):
    validate = False
    ualtchars = False
    if len(param.args) == 5:
        validate = param.args[2]
        ualtchars = param.args[3]
        simd_name = get_simd_name(param.args[4])
    else:
        simd_name = get_simd_name(param.args[2])
    if ualtchars:
        ualtchars = '_ualtchars'
    else:
        ualtchars = ''
    if not validate:
        return '%s%s_%s_%d_%s' % (testcase_func.__name__,
                                  ualtchars,
                                  name_lut[param.args[0]],
                                  param.args[1],
                                  simd_name)
    return '%s%s_%s_validate_%d_%s' % (testcase_func.__name__,
                                       ualtchars,
                                       name_lut[param.args[0]],
                                       param.args[1],
                                       simd_name)


def tc_idx(testcase_func, param_num, param):
    simd_name = get_simd_name(param.args[1])
    return '%s_%d_%s' % (testcase_func.__name__, param.args[0], simd_name)


class TestPyBase64(unittest.TestCase):

    def simd_setup(self, simd_id):
        if _has_extension:
            flag = compile_flags[simd_id]
            if flag != 0 and not flag & runtime_flags:  # pragma: no branch
                raise unittest.SkipTest(
                    'SIMD extension not available')  # pragma: no cover
            _set_simd_path(flag)
            self.assertEqual(_get_simd_path(), flag)
        else:
            self.assertEqual(0, simd_id)

    @parameterized.expand([
        [get_simd_name(s), s] for s in range(len(compile_flags))
    ])
    def test_version(self, _, simd_id):
        self.simd_setup(simd_id)
        self.assertTrue(
            pybase64.get_version().startswith(pybase64.__version__)
        )

    @parameterized.expand(params_helper, testcase_func_name=tc_name)
    def test_enc_helper(self, altchars_id, vector_id, simd_id):
        self.simd_setup(simd_id)
        vector = test_vectors_bin[altchars_id][vector_id]
        self.assertEqual(
            enc_helper_lut[altchars_id](vector),
            ref_enc_helper_lut[altchars_id](vector)
        )

    @parameterized.expand(params_helper, testcase_func_name=tc_name)
    def test_dec_helper(self, altchars_id, vector_id, simd_id):
        self.simd_setup(simd_id)
        vector = test_vectors_b64[altchars_id][vector_id]
        self.assertEqual(
            dec_helper_lut[altchars_id](vector),
            ref_dec_helper_lut[altchars_id](vector)
        )

    @parameterized.expand(params_helper, testcase_func_name=tc_name)
    def test_dec_helper_unicode(self, altchars_id, vector_id, simd_id):
        self.simd_setup(simd_id)
        if altchars_id == URL and version_info < (3, 0):
            raise unittest.SkipTest(
                'decoding urlsafe unicode strings is not supported in python '
                '2.x')
        vector = test_vectors_b64[altchars_id][vector_id]
        self.assertEqual(
            dec_helper_lut[altchars_id](text_type(vector, 'utf-8')),
            ref_dec_helper_lut[altchars_id](text_type(vector, 'utf-8'))
        )

    @parameterized.expand(params_helper, testcase_func_name=tc_name)
    def test_rnd_helper(self, altchars_id, vector_id, simd_id):
        self.simd_setup(simd_id)
        vector = test_vectors_b64[altchars_id][vector_id]
        self.assertEqual(
            enc_helper_lut[altchars_id](dec_helper_lut[altchars_id](vector)),
            vector
        )

    @parameterized.expand(params_helper, testcase_func_name=tc_name)
    def test_rnd_helper_unicode(self, altchars_id, vector_id, simd_id):
        self.simd_setup(simd_id)
        vector = test_vectors_b64[altchars_id][vector_id]
        self.assertEqual(
            enc_helper_lut[altchars_id](
                dec_helper_lut[altchars_id](text_type(vector, 'utf-8'))),
            vector
        )

    @parameterized.expand(params_novalidate, testcase_func_name=tc_name)
    def test_enc(self, altchars_id, vector_id, validate, ualtchars, simd_id):
        self.simd_setup(simd_id)
        vector = test_vectors_bin[altchars_id][vector_id]
        altchars = altchars_lut[altchars_id]
        self.assertEqual(
            pybase64.b64encode(vector, altchars),
            base64.b64encode(vector, altchars)
        )

    @parameterized.expand(params_validate, testcase_func_name=tc_name)
    def test_dec(self, altchars_id, vector_id, validate, ualtchars, simd_id):
        self.simd_setup(simd_id)
        vector = test_vectors_b64[altchars_id][vector_id]
        altchars = altchars_lut[altchars_id]
        if validate:
            if version_info < (3, 0):
                raise unittest.SkipTest(
                    'validate is not supported in python 2.x')
            self.assertEqual(
                pybase64.b64decode(vector, altchars, validate),
                base64.b64decode(vector, altchars, validate)
            )
        else:
            self.assertEqual(
                pybase64.b64decode(vector, altchars, validate),
                base64.b64decode(vector, altchars)
            )

    @parameterized.expand(params_validate, testcase_func_name=tc_name)
    def test_dec_unicode(self, altchars_id, vector_id,
                         validate, ualtchars, simd_id):
        self.simd_setup(simd_id)
        vector = test_vectors_b64[altchars_id][vector_id]
        altchars = altchars_lut[altchars_id]
        if altchars_id == STD:
            altchars = None
        if altchars_id != STD and version_info < (3, 0):
            raise unittest.SkipTest(
                'decoding non standard unicode strings is not supported in '
                'python 2.x')
        if validate:
            if version_info < (3, 0):
                raise unittest.SkipTest(
                    'validate is not supported in python 2.x')
            self.assertEqual(
                pybase64.b64decode(text_type(vector, 'utf-8'),
                                   altchars,
                                   validate),
                base64.b64decode(text_type(vector, 'utf-8'),
                                 altchars,
                                 validate)
            )
        else:
            self.assertEqual(
                pybase64.b64decode(text_type(vector, 'utf-8'),
                                   altchars,
                                   validate),
                base64.b64decode(text_type(vector, 'utf-8'), altchars)
            )

    @parameterized.expand(params_validate, testcase_func_name=tc_name)
    def test_rnd(self, altchars_id, vector_id, validate, ualtchars, simd_id):
        self.simd_setup(simd_id)
        vector = test_vectors_b64[altchars_id][vector_id]
        altchars = altchars_lut[altchars_id]
        self.assertEqual(
            pybase64.b64encode(
                pybase64.b64decode(vector, altchars, validate),
                altchars_lut[altchars_id]),
            vector
        )

    @parameterized.expand(params_validate, testcase_func_name=tc_name)
    def test_rnd_unicode(self, altchars_id, vector_id,
                         validate, ualtchars, simd_id):
        self.simd_setup(simd_id)
        vector = test_vectors_b64[altchars_id][vector_id]
        altchars = altchars_lut[altchars_id]
        self.assertEqual(
            pybase64.b64encode(
                pybase64.b64decode(text_type(vector, 'utf-8'),
                                   altchars,
                                   validate),
                altchars),
            vector
        )

    @parameterized.expand(params_invalid_altchars, testcase_func_name=tc_idx)
    def test_invalid_altchars_enc(self, _, simd_id, altchars, exception):
        self.simd_setup(simd_id)
        with self.assertRaises(exception):
            pybase64.b64encode(b'ABCD', altchars)

    @parameterized.expand(params_invalid_altchars, testcase_func_name=tc_idx)
    def test_invalid_altchars_dec(self, _, simd_id, altchars, exception):
        self.simd_setup(simd_id)
        with self.assertRaises(exception):
            pybase64.b64decode(b'ABCD', altchars)

    @parameterized.expand(params_invalid_altchars, testcase_func_name=tc_idx)
    def test_invalid_altchars_dec_validate(self, _, simd_id,
                                           altchars, exception):
        self.simd_setup(simd_id)
        with self.assertRaises(exception):
            pybase64.b64decode(b'ABCD', altchars, True)

    @parameterized.expand(params_invalid_data, testcase_func_name=tc_idx)
    def test_invalid_data_dec(self, _, simd_id, vector, altchars, exception):
        self.simd_setup(simd_id)
        with self.assertRaises(exception):
            pybase64.b64decode(vector, altchars)

    @parameterized.expand(params_invalid_data_validate,
                          testcase_func_name=tc_idx)
    def test_invalid_data_dec_skip(self, _, simd_id,
                                   vector, altchars, exception):
        self.simd_setup(simd_id)
        self.assertEqual(
            pybase64.b64decode(vector, altchars),
            base64.b64decode(vector, altchars)
        )

    @parameterized.expand(params_invalid_data + params_invalid_data_validate,
                          testcase_func_name=tc_idx)
    def test_invalid_data_dec_validate(self, _, simd_id,
                                       vector, altchars, exception):
        self.simd_setup(simd_id)
        with self.assertRaises(exception):
            pybase64.b64decode(vector, altchars, True)

    def test_invalid_data_enc_0(self):
        with self.assertRaises(TypeError):
            pybase64.b64encode(u'this is a test')

    def test_invalid_args_enc_0(self):
        with self.assertRaises(TypeError):
            pybase64.b64encode()

    def test_invalid_args_dec_0(self):
        with self.assertRaises(TypeError):
            pybase64.b64decode()
