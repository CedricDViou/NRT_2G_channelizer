#!/home/cedric/anaconda3/envs/2point7/bin/python
'''
This code configures the ROACH2 used for NRT spectral backend.
'''

import casperfpga
import time
import numpy as np
import struct
import adc5g



def fix2real(data, n_bits=18, bin_pt=17):
    data = data.view(np.int64).copy()
    neg = data > (2**(n_bits-1)-1)
    data[neg] -= 2**n_bits
    data = data / 2.0**bin_pt
    return data

