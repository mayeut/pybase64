import base64
import sys
from codecs import open
from timeit import default_timer as timer

import pybase64


if sys.version_info < (3, 0):
    from pybase64._fallback import b64decode as b64decodeValidate
else:
    from base64 import b64decode as b64decodeValidate


def bench_one(data, enc, dec, altchars=None, validate=False):
    number = 0
    time = timer()
    while True:
        encodedcontent = enc(data, altchars=altchars)
        number += 1
        if timer() - time > 0.25:
            break
    iter = number
    time = timer()
    while iter > 0:
        encodedcontent = enc(data, altchars=altchars)
        iter -= 1
    time = timer() - time
    print('{0:<32s} {1:9.3f} MB/s ({2:,d} bytes)'.format(
        enc.__module__ + '.' + enc.__name__ + ':',
        ((number * len(data)) / (1024.0 * 1024.0)) / time,
        len(data)))
    number = 0
    time = timer()
    while True:
        decodedcontent = dec(encodedcontent, altchars=altchars)
        number += 1
        if timer() - time > 0.25:
            break
    iter = number
    time = timer()
    while iter > 0:
        decodedcontent = dec(encodedcontent, altchars=altchars, validate=True)
        iter -= 1
    time = timer() - time
    print('{0:<32s} {1:9.3f} MB/s ({2:,d} bytes)'.format(
        dec.__module__ + '.' + dec.__name__ + ':',
        ((number * len(data)) / (1024.0 * 1024.0)) / time,
        len(data)))
    assert decodedcontent == data


def bench(data):
    bench_one(data, pybase64.b64encode, pybase64.b64decode)
    bench_one(data, base64.b64encode, b64decodeValidate)


def main(args=None):
    print(pybase64.get_version())
    with open(sys.argv[1], mode='rb') as f:
        filecontent = f.read()
    bench(filecontent)
#    print(encodedcontent.decode('ascii'))


if __name__ == "__main__":
    main()
