import os
import shutil
import sys
import tempfile
from contextlib import contextmanager
from distutils import log
from distutils.errors import CompileError, LinkError


__all__ = [
    'CCompilerCapabilities'
]


@contextmanager
def chdir(path):
    cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(cwd)


@contextmanager
def mkdtemp(suffix):
    path = tempfile.mkdtemp(suffix)
    try:
        with chdir(path):
            yield path
    finally:
        shutil.rmtree(path)


@contextmanager
def output(is_quiet):
    if is_quiet:  # pragma: no branch
        devnull = open(os.devnull, 'w')
        oldstderr = os.dup(sys.stderr.fileno())
        oldstdout = os.dup(sys.stdout.fileno())
        os.dup2(devnull.fileno(), sys.stderr.fileno())
        os.dup2(devnull.fileno(), sys.stdout.fileno())
    try:
        yield
    finally:
        if is_quiet:  # pragma: no branch
            os.dup2(oldstderr, sys.stderr.fileno())
            os.dup2(oldstdout, sys.stdout.fileno())
            devnull.close()


class CCompilerCapabilities:
    SIMD_SSSE3 = 0
    SIMD_SSE41 = 1
    SIMD_SSE42 = 2
    SIMD_AVX = 3
    SIMD_AVX2 = 4
    SIMD_NEON32 = 5
    SIMD_NEON64 = 6

    def __init__(self, compiler):
        self.__capabilities = dict()
        self.__get_capabilities(compiler)

    def __has_simd_support(self, compiler, flags, include, content):
        quiet = True

        with mkdtemp("pybase64simdtest") as dname:
            fname = os.path.join(dname, 'simd.c')
            with open(fname, 'w') as f:
                f.write("""#include <%s>\n""" % include)
                f.write("""\
int main (int argc, char **argv) {
    %s
}
""" % content)
            with output(quiet):
                for flag in flags:
                    lflags = []
                    if not len(flag) == 0:
                        lflags = [flag]
                    try:
                        objects = compiler.compile(['simd.c'],
                                                   output_dir=dname,
                                                   extra_postargs=lflags)
                    except CompileError:
                        continue
                    try:
                        compiler.link_shared_lib(objects,
                                                 'a.out',
                                                 output_dir=dname)
                    except (LinkError, TypeError):  # pragma: no cover
                        continue  # pragma: no cover
                    return {'support': True, 'flags': lflags}
                return {'support': False, 'flags': []}

    def __get_capabilities(self, compiler):
        log.info("getting compiler simd support")
        self.__capabilities[CCompilerCapabilities.SIMD_SSSE3] = \
            self.__has_simd_support(
                compiler,
                ['', '-mssse3'],
                'tmmintrin.h',
                '__m128i t = _mm_setzero_si128();'
                't = _mm_shuffle_epi8(t, t);'
                'return _mm_cvtsi128_si32(t);'
        )
        log.info(
            "SSSE3: %s" %
            str(self.__capabilities[
                CCompilerCapabilities.SIMD_SSSE3
            ]['support'])
        )
        self.__capabilities[CCompilerCapabilities.SIMD_SSE41] = \
            self.__has_simd_support(
                compiler,
                ['', '-msse4.1'],
                'smmintrin.h',
                '__m128i t = _mm_setzero_si128();'
                't = _mm_insert_epi32(t, 1, 1);'
                'return _mm_cvtsi128_si32(t);'
        )
        log.info(
            "SSE41: %s" %
            str(self.__capabilities[
                CCompilerCapabilities.SIMD_SSE41
            ]['support'])
        )
        self.__capabilities[CCompilerCapabilities.SIMD_SSE42] = \
            self.__has_simd_support(
                compiler,
                ['', '-msse4.2'],
                'nmmintrin.h',
                '__m128i t = _mm_setzero_si128();'
                'return _mm_cmpistra(t, t, 0);'
        )
        log.info(
            "SSE42: %s" %
            str(self.__capabilities[
                CCompilerCapabilities.SIMD_SSE42
            ]['support'])
        )
        self.__capabilities[CCompilerCapabilities.SIMD_AVX] = \
            self.__has_simd_support(
                compiler,
                ['', '-mavx'],
                'immintrin.h',
                '__m256i t = _mm256_setzero_si256();'
                'return _mm_cvtsi128_si32(_mm256_castsi256_si128(t));'
        )
        log.info(
            "AVX:   %s" %
            str(self.__capabilities[
                CCompilerCapabilities.SIMD_AVX
            ]['support'])
        )
        self.__capabilities[CCompilerCapabilities.SIMD_AVX2] = \
            self.__has_simd_support(
                compiler,
                ['', '-mavx2'],
                'immintrin.h',
                '__m256i t = _mm256_broadcastd_epi32(_mm_setzero_si128());'
                'return _mm_cvtsi128_si32(_mm256_castsi256_si128(t));'
        )
        log.info(
            "AVX2:  %s" %
            str(self.__capabilities[
                CCompilerCapabilities.SIMD_AVX2
            ]['support'])
        )
        self.__capabilities[CCompilerCapabilities.SIMD_NEON32] = \
            self.__has_simd_support(
                compiler,
                [''],
                'arm_neon.h',
                'uint8x16_t t = vdupq_n_u8(1);'
                'return vgetq_lane_s32(vreinterpretq_s32_u8(t));'
        )
        log.info(
            "NEON32:  %s" %
            str(self.__capabilities[
                CCompilerCapabilities.SIMD_NEON32
            ]['support'])
        )

    def has(self, what):
        if what not in self.__capabilities:
            return False
        return self.__capabilities[what]['support']

    def flags(self, what):
        if not self.has(what):  # pragma: no branch
            return self.__capabilities[666]['flags']  # pragma: no cover
        return self.__capabilities[what]['flags']
