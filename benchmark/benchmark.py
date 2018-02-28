from base64 import b64encode as p_b64encode
from base64 import b64decode as p_b64decode

from pybase64 import b64encode as n_b64encode
from pybase64 import b64decode as n_b64decode
from pybase64._fallback import b64encode as f_b64encode
from pybase64._fallback import b64decode as f_b64decode
from pybase64._pybase64 import _set_simd_path
from numpy.random import randint as nprand
from timeit import default_timer as timer
import pygal

maxlen = 8*1024*1024
b64data = n_b64encode(nprand(255, size=maxlen, dtype='uint8'))
bindata = n_b64decode(b64data, validate=True)

def get_enc(label):
    if label == 'builtin':
        return p_b64encode
    if label == 'py':
        return f_b64encode
    if label == 'c':
        _set_simd_path(0)
    elif label == 'ssse3':
        _set_simd_path(4)
    elif label == 'avx':
        _set_simd_path(32)
    elif label == 'avx2':
        _set_simd_path(64)
    else:
        raise ValueError('Invalid label %r' % label)
    return n_b64encode


def bench_enc_one(data, enc, altchars):
    outer_iter = 10
    inner_iter = 5
    results = []
    stop = False

    while not stop:
        outer = outer_iter
        while outer > 0:
            inner = inner_iter
            time = timer()
            while inner > 0:
                encodedcontent = enc(data, altchars=altchars)
                inner -= 1
            results.append(timer() - time)
            outer -= 1
        numerator = (inner_iter * len(data)) / (1024.0 * 1024.0)
        results = sorted([numerator / time for time in results], reverse=True)
        results = results[:outer_iter]
        ninefive = [i for i in results if (results[0] - i) / results[0] < 0.15]
        if len(ninefive) == outer_iter:
            stop = True
    return results[0]

maxlen = len(bindata)

enc_dict = dict()
for clen in [2 ** i for i in range(4, 24)]:
    print(clen)
    for label in ['avx2', 'avx', 'ssse3', 'c', 'py', 'builtin']:
        fn = get_enc(label)
        delta = bench_enc_one(bindata[:clen], fn, None)
        #print('%s %d %r' % (label, clen, delta))
        enc_dict[label] = enc_dict.get(label, [])
        enc_dict[label].append((clen, delta))

xy_chart = pygal.XY(logarithmic=True)
xy_chart.title = 'Standard encoding'
for label in enc_dict.keys():
    xy_chart.add(label, enc_dict[label])
xy_chart.render_to_file('benchmark-std-encoding.svg')

enc_dict = dict()
for clen in [2 ** i for i in range(4, 24)]:
    print(clen)
    for label in ['avx2', 'avx', 'ssse3', 'c', 'py', 'builtin']:
        fn = get_enc(label)
        delta = bench_enc_one(bindata[:clen], fn, b'-_')
        #print('%s %d %r' % (label, clen, delta))
        enc_dict[label] = enc_dict.get(label, [])
        enc_dict[label].append((clen, delta))

xy_chart = pygal.XY(logarithmic=True)
xy_chart.title = 'URL-safe encoding'
for label in enc_dict.keys():
    xy_chart.add(label, enc_dict[label])
xy_chart.render_to_file('benchmark-url-encoding.svg')
