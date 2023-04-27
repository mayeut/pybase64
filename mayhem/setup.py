from setuptools import setup, find_packages

setup(
    name='fuzz_pybase64',
    version='0.1',
    packages=find_packages(),
    install_requires=['pybase64'],
    entry_points={
        'console_scripts': [
            'fuzz_pybase64 = fuzz_pybase64:main'
        ]
    }
)
