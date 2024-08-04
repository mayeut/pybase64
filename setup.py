from __future__ import annotations

import logging
import os
import platform as platform_module
import shutil
import subprocess
import sys
import sysconfig
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, cast

from setuptools import Extension, find_packages, setup
from setuptools.command.build_ext import build_ext

HERE = Path(__file__).resolve().parent
OPTIONAL_EXTENSION = os.environ.get("CIBUILDWHEEL", "0") != "1"
IS_64BIT = sys.maxsize > 2**32
IS_WINDOWS = sys.platform.startswith("win32")
IS_MACOS = sys.platform.startswith("darwin")

log = logging.getLogger("pybase64-setup")

# Get version
version_dict: dict[str, object] = {}
exec(HERE.joinpath("src", "pybase64", "_version.py").read_text(), {}, version_dict)
version = cast(str, version_dict["_version"])

# Get the long description from the README file
long_description = HERE.joinpath("README.rst").read_text()

# Generate license text
with HERE.joinpath("src", "pybase64", "_license.py").open("w") as f:
    f.write('_license = """')
    f.write("pybase64\n")
    f.write("=" * 79 + "\n")
    f.write(HERE.joinpath("LICENSE").read_text())
    f.write("=" * 79 + "\n\n")
    f.write("libbase64\n")
    f.write("=" * 79 + "\n")
    f.write(HERE.joinpath("base64", "LICENSE").read_text())
    f.write("=" * 74)
    f.write('""" \\\n')
    f.write('    + "====="\n')

pybase64_ext = Extension(
    "pybase64._pybase64",
    [
        "src/pybase64/_pybase64.c",
        "src/pybase64/_pybase64_get_simd_flags.c",
    ],
    include_dirs=["base64/include/", "base64/lib/", ".base64_build"],
    library_dirs=[".base64_build"],
    libraries=["base64"],
    define_macros=[("BASE64_STATIC_DEFINE", "1")],
    optional=OPTIONAL_EXTENSION,
)


def get_cmake_extra_config(plat_name: str | None, build_type: str) -> tuple[bool, list[str]]:
    log.info("getting cmake extra config")
    extra_config = []
    machine = platform_module.machine().lower()
    platform = sysconfig.get_platform()
    archflags = os.environ.get("ARCHFLAGS", None)

    log.info("  machine: %s", machine)
    log.info("  platform: %s", platform)
    log.info("  plat_name: %s", plat_name)
    log.info("  ARCHFLAGS: %s", archflags)
    log.info("  CC: %s", os.environ.get("CC", None))
    log.info("  CFLAGS: %s", os.environ.get("CFLAGS", None))
    log.info("  LDFLAGS: %s", os.environ.get("LDFLAGS", None))
    log.info("  sysconfig CC: %s", sysconfig.get_config_var("CC"))
    log.info("  sysconfig CCSHARED: %s", sysconfig.get_config_var("CCSHARED"))
    log.info("  sysconfig CFLAGS: %s", sysconfig.get_config_var("CFLAGS"))
    log.info("  sysconfig BASECFLAGS: %s", sysconfig.get_config_var("BASECFLAGS"))
    log.info("  sysconfig OPT: %s", sysconfig.get_config_var("OPT"))
    log.info("  sysconfig LDFLAGS: %s", sysconfig.get_config_var("LDFLAGS"))

    platform = plat_name or platform
    is_msvc = platform.startswith("win")

    if not is_msvc:
        extra_config.append(f"-DCMAKE_BUILD_TYPE={build_type}")

    if is_msvc:
        if not IS_WINDOWS:
            msg = f"Building {platform} is only supported on Windows"
            raise ValueError(msg)
        # setup cross-compile
        # assumes VS2019 or VS2022 will be used as the default generator
        if platform == "win-amd64" and machine != "amd64":
            extra_config.append("-A x64")
        if platform == "win32" and machine != "x86":
            extra_config.append("-A Win32")
        if platform == "win-arm64" and machine != "arm64":
            extra_config.append("-A ARM64")
    elif IS_MACOS:
        known_archs = {
            "arm64",
            "arm64e",
            "armv7",
            "armv7s",
            "x86_64",
            "i386",
            "ppc",
            "ppc64",
        }
        if not platform.startswith("macosx-"):
            msg = f"Building {platform} is not supported on macOS"
            raise ValueError(msg)
        _, _, platform_arch = platform.split("-")
        if platform_arch.startswith(("universal", "fat")):
            msg = f"multiple arch `{platform_arch}` is not supported"
            raise ValueError(msg)
        configured_archs = {platform_arch}
        if archflags:
            flags = [arch.strip() for arch in archflags.strip().split() if arch.strip()]
            for i in range(len(flags) - 1):
                if flags[i] == "-arch":
                    configured_archs.add(flags[i + 1])
        if len(configured_archs) > 1:
            msg = f"multiple arch `{configured_archs}` is not supported"
            raise ValueError(msg)
        arch = configured_archs.pop()
        if arch in known_archs:
            extra_config.append(f"-DCMAKE_OSX_ARCHITECTURES={arch}")
        else:
            log.warning("`%s` is not a known value for CMAKE_OSX_ARCHITECTURES", arch)

    return is_msvc, extra_config


def cmake(*args: str) -> None:
    args_string = " ".join(f"'{arg}'" for arg in args)
    log.info("running cmake %s", args_string)
    subprocess.run(["cmake", *args], check=True)


@contextmanager
def base64_build(plat_name: str | None) -> Generator[bool, None, None]:
    base64_built = False
    source_dir = HERE / "base64"
    build_dir = HERE / ".base64_build"
    build_type = "Release"
    config_options = [
        "-S",
        str(source_dir),
        "-B",
        str(build_dir),
        "-DBASE64_BUILD_TESTS:BOOL=OFF",
        "-DBASE64_BUILD_CLI:BOOL=OFF",
        "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
    ]
    if build_dir.exists():
        shutil.rmtree(build_dir)
    try:
        try:
            cmake("--version")
            is_msvc, extra_config = get_cmake_extra_config(plat_name, build_type)
            config_options.extend(extra_config)
            cmake(*config_options)
            cmake("--build", str(build_dir), "--config", build_type, "--verbose")
            if is_msvc:
                shutil.copyfile(build_dir / build_type / "base64.lib", build_dir / "base64.lib")
            base64_built = True
        except Exception as e:
            log.error("error: %s", e)
            if not OPTIONAL_EXTENSION:
                raise
        yield base64_built
    finally:
        if build_dir.exists():
            shutil.rmtree(build_dir, ignore_errors=True)


class BuildExt(build_ext):
    def finalize_options(self) -> None:
        if "-coverage" in os.environ.get("CFLAGS", "").split():
            plat_name = getattr(self, "plat_name", None) or sysconfig.get_platform()
            temp_name = f"coverage-{plat_name}-{sys.implementation.cache_tag}"
            coverage_build = HERE / "build" / temp_name
            if coverage_build.exists():
                shutil.rmtree(coverage_build)
            self.build_temp = str(coverage_build)
        super().finalize_options()

    def run(self) -> None:
        plat_name = getattr(self, "plat_name", None)
        with base64_build(plat_name) as build_successful:
            if build_successful:
                super().run()
            else:
                assert OPTIONAL_EXTENSION
                log.warning("warning: skipping optional C-extension, base64 library build failed")


setup(
    name="pybase64",
    cmdclass={"build_ext": BuildExt},
    ext_modules=[pybase64_ext],
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
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    # Supported python versions
    python_requires=">=3.8",
    # What does your project relate to?
    keywords="base64",
    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={"pybase64": ["py.typed", "_pybase64.pyi"]},
    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        "console_scripts": [
            "pybase64=pybase64.__main__:main",
        ],
    },
)
