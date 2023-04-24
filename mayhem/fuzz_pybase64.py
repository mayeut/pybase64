#!/usr/bin/python3
import pdb

import atheris
import sys

with atheris.instrument_imports():
    from pybase64 import standard_b64encode, standard_b64decode


@atheris.instrument_func
def TestOneInput(data):
    # print(data)
    encoded = standard_b64encode(data)
    # print(encoded)
    decoded = standard_b64decode(encoded)
    # print(decoded)

    if data != decoded:
        pdb.set_trace()
        raise RuntimeError("Encoded and decoded data are not equal")


def main():
    atheris.Setup(sys.argv, TestOneInput, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    print("starting")
    main()
    print("ending")
