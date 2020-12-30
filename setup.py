import builtins
import glob
import os
import runpy
import sys
from codecs import open
from distutils import log
from distutils.cmd import Command
from distutils.command.build_ext import build_ext
from distutils.dep_util import newer_group
from distutils.errors import DistutilsSetupError
from os import environ, path

from setuptools import Extension, find_packages, setup

# Not to try loading things from the main module during setup
builtins.__PYBASE64_SETUP__ = True

from pybase64.distutils.ccompilercapabilities import CCompilerCapabilities  # noqa: E402

if sys.version_info[:2] < (3, 5):
    raise RuntimeError("Python version >= 3.5 required.")

here = path.abspath(path.dirname(__file__))

# Get version
version = runpy.run_path(path.join(here, "pybase64", "_version.py"))["__version__"]

# Get the long description from the README file
with open(path.join(here, "README.rst"), encoding="utf-8") as f:
    long_description = f.read()

# Generate license text
with open(path.join(here, "pybase64/_license.py"), "wt") as f:
    f.write('_license = """')
    f.write("pybase64\n")
    f.write("=" * 79 + "\n")
    with open(path.join(here, "LICENSE")) as license:
        f.write(license.read())
    f.write("=" * 79 + "\n\n")
    f.write("libbase64\n")
    f.write("=" * 79 + "\n")
    with open(path.join(here, "base64/LICENSE")) as license:
        f.write(license.read())
    f.write("=" * 74)
    f.write('""" \\\n')
    f.write('    + "====="\n')

pybase64_ext = Extension(
    "pybase64._pybase64",
    [
        "pybase64/_pybase64.c",
        "pybase64/_pybase64_get_simd_flags.c",
        "base64/lib/lib.c",
        "base64/lib/codec_choose.c",
        "base64/lib/arch/generic/codec.c",
        "base64/lib/tables/tables.c",
    ],
    include_dirs=["base64/include/", "base64/lib/"],
)

pybase64_ext.optional = environ.get("CIBUILDWHEEL", "0") != "1"

pybase64_ext.sources_ssse3 = ["base64/lib/arch/ssse3/codec.c"]
pybase64_ext.sources_sse41 = ["base64/lib/arch/sse41/codec.c"]
pybase64_ext.sources_sse42 = ["base64/lib/arch/sse42/codec.c"]
pybase64_ext.sources_avx = ["base64/lib/arch/avx/codec.c"]
pybase64_ext.sources_avx2 = ["base64/lib/arch/avx2/codec.c"]
pybase64_ext.sources_neon32 = ["base64/lib/arch/neon32/codec.c"]
pybase64_ext.sources_neon64 = ["base64/lib/arch/neon64/codec.c"]


def pybase64_write_config(capabilities):
    log.info("creating 'base64/lib/config.h'")
    with open(path.join(here, "base64/lib/config.h"), mode="wt") as f:
        f.write(
            "\n#define HAVE_SSSE3                 %i"
            % capabilities.has(CCompilerCapabilities.SIMD_SSSE3)
        )
        f.write(
            "\n#define HAVE_SSE41                 %i"
            % capabilities.has(CCompilerCapabilities.SIMD_SSE41)
        )
        f.write(
            "\n#define HAVE_SSE42                 %i"
            % capabilities.has(CCompilerCapabilities.SIMD_SSE42)
        )
        f.write(
            "\n#define HAVE_AVX                   %i"
            % capabilities.has(CCompilerCapabilities.SIMD_AVX)
        )
        f.write(
            "\n#define HAVE_AVX2                  %i"
            % capabilities.has(CCompilerCapabilities.SIMD_AVX2)
        )
        f.write(
            "\n#define HAVE_NEON32                %i"
            % capabilities.has(CCompilerCapabilities.SIMD_NEON32)
        )
        f.write(
            "\n#define HAVE_NEON64                %i"
            % capabilities.has(CCompilerCapabilities.SIMD_NEON64)
        )
        f.write(
            "\n#define HAVE_FAST_UNALIGNED_ACCESS %i"
            % capabilities.has(CCompilerCapabilities.SIMD_SSSE3)
        )  # on x86
        f.write("\n")


class pybase64_build_ext(build_ext):
    def build_extension(self, ext):
        sources = ext.sources
        if sources is None or not isinstance(sources, (list, tuple)):
            raise DistutilsSetupError(
                "in 'ext_modules' option (extension '%s'), "
                "'sources' must be present and must be "
                "a list of source filenames" % ext.name
            )
        sources = list(sources)

        simd_sources = {
            CCompilerCapabilities.SIMD_SSSE3: ext.sources_ssse3,
            CCompilerCapabilities.SIMD_SSE41: ext.sources_sse41,
            CCompilerCapabilities.SIMD_SSE42: ext.sources_sse42,
            CCompilerCapabilities.SIMD_AVX: ext.sources_avx,
            CCompilerCapabilities.SIMD_AVX2: ext.sources_avx2,
            CCompilerCapabilities.SIMD_NEON32: ext.sources_neon32,
            CCompilerCapabilities.SIMD_NEON64: ext.sources_neon64,
        }

        ext_path = self.get_ext_fullpath(ext.name)
        depends = sources + ext.depends

        try:
            simd_sources_values = simd_sources.itervalues()
        except AttributeError:
            simd_sources_values = simd_sources.values()
        for add_sources in simd_sources_values:
            depends = depends + add_sources

        if not (self.force or newer_group(depends, ext_path, "newer")):
            log.debug("skipping '%s' extension (up-to-date)", ext.name)
            return
        else:
            log.info("building '%s' extension", ext.name)

        capabilities = CCompilerCapabilities(self.compiler)
        pybase64_write_config(capabilities)

        objects = []

        for simd_opt in (
            CCompilerCapabilities.SIMD_SSSE3,
            CCompilerCapabilities.SIMD_SSE41,
            CCompilerCapabilities.SIMD_SSE42,
            CCompilerCapabilities.SIMD_AVX,
            CCompilerCapabilities.SIMD_AVX2,
            CCompilerCapabilities.SIMD_NEON32,
            CCompilerCapabilities.SIMD_NEON64,
        ):
            if len(simd_sources[simd_opt]) == 0:
                continue
            if capabilities.has(simd_opt):
                objects = objects + self.compiler.compile(
                    simd_sources[simd_opt],
                    output_dir=self.build_temp,
                    include_dirs=ext.include_dirs,
                    debug=self.debug,
                    extra_postargs=capabilities.flags(simd_opt),
                    depends=ext.depends,
                )
            else:
                sources = sources + simd_sources[simd_opt]

        objects = objects + self.compiler.compile(
            sources,
            output_dir=self.build_temp,
            include_dirs=ext.include_dirs,
            debug=self.debug,
            extra_postargs=[],
            depends=ext.depends,
        )

        # Detect target language, if not provided
        language = ext.language or self.compiler.detect_language(sources)

        self.compiler.link_shared_object(
            objects,
            ext_path,
            libraries=self.get_libraries(ext),
            library_dirs=ext.library_dirs,
            runtime_library_dirs=ext.runtime_library_dirs,
            export_symbols=self.get_export_symbols(ext),
            debug=self.debug,
            build_temp=self.build_temp,
            target_lang=language,
        )


# Let's define a class to clean in-place built extensions
class CleanExtensionCommand(Command):
    """A custom command to clean all in-place built C extensions."""

    description = "clean all in-place built C extensions"
    user_options = []

    def initialize_options(self):
        """Set default values for options."""

    def finalize_options(self):
        """Post-process options."""

    def run(self):
        """Run command."""
        for ext in ["*.so", "*.pyd"]:
            for file in glob.glob("./pybase64/" + ext):
                log.info("removing '%s'", file)
                if self.dry_run:
                    continue
                os.remove(file)


# Get the C code
exts = [pybase64_ext]


setup(
    name="pybase64",
    cmdclass={
        "build_ext": pybase64_build_ext,
        "clean_ext": CleanExtensionCommand,
    },
    ext_modules=exts,
    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version=version,
    description="Fast Base64 encoding/decoding",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    # The project's main homepage.
    url="https://github.com/mayeut/pybase64",
    project_urls={
        "Source": "https://github.com/mayeut/pybase64",
        "Tracker": "https://github.com/mayeut/pybase64/issues",
        "Documentation": "https://pybase64.readthedocs.io/en/stable",
    },
    # Author details
    author="Matthieu Darbois",
    # author_email = 'mayeut@users.noreply.github.com',
    # Choose your license
    license="BSD-2-Clause",
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        "Development Status :: 5 - Production/Stable",
        # Indicate who your project is intended for
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
        # Pick your license as you wish (should match "license" above)
        "License :: OSI Approved :: BSD License",
        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        "Programming Language :: C",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    # Supported python versions
    python_requires=">=3.5",
    # What does your project relate to?
    keywords="base64",
    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(),
    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={
        "test": ["pytest>=5.0.0"],
    },
    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        "console_scripts": [
            "pybase64=pybase64.__main__:main",
        ],
    },
)
