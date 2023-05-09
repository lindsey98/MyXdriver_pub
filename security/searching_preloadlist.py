#!/usr/bin/python3

from hstspreload import in_hsts_preload

import os
import sys
import _pickle

def dump(obj, filename):
	with open(filename, 'wb') as wfp:
		_pickle.dump(obj, wfp, protocol = 2)

_abs_path = os.path.dirname(os.path.abspath(__file__))
_preload_result = os.path.join(_abs_path, "preload_result")

tmp = in_hsts_preload(sys.argv[1])

dump(tmp,_preload_result)
