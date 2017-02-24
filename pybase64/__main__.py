import pybase64 as b64
import sys
from codecs import open
from timeit import default_timer as timer

import base64

def main(args=None):
    print('Use extension: %r' % b64._has_extension)
    with open(sys.argv[1], mode='rb') as f:
        filecontent = f.read()
    start = timer()
    encodedcontent = b64.standard_b64encode(filecontent)
    end = timer()
    print('pybase64.standard_b64encode: %8.5f s' % (end - start))
    start = timer()
    decodedcontent = b64.standard_b64decode(encodedcontent)
    end = timer()
    print('pybase64.standard_b64decode: %8.5f s' % (end - start))
    if not decodedcontent == filecontent:
        print('error got %d bytes, expected %d bytes' % (len(decodedcontent), len(filecontent)))
    start = timer()
    encodedcontent = base64.standard_b64encode(filecontent)
    end = timer()
    print('base64.standard_b64encode: %8.5f s' % (end - start))
    start = timer()
    decodedcontent = base64.standard_b64decode(encodedcontent)
    end = timer()
    print('base64.standard_b64decode: %8.5f s' % (end - start))
    if not decodedcontent == filecontent:
        print('error got %d bytes, expected %d bytes' % (len(decodedcontent), len(filecontent)))
    #print(encodedcontent.decode('ascii'))

if __name__ == "__main__":
    main()
