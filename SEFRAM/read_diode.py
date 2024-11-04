#!/usr/bin/env python
###############################################################################
#
# Copyright (C) 2021
# Station de Radioastronomie de Nançay,
# Observatoire de Paris, PSL Research University, CNRS, Univ. Orléans, OSUC,
# 18330 Nançay, France
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
# Author: Cedric Viou (Cedric.Viou@obs-nancay.fr)
#
# Description:
# Records sefram stream into a file
#
###############################################################################

import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('QtAgg')


import sys
import signal
import socket
import struct
from time import time, sleep

import imp
import sefram
sefram = imp.reload(sefram)

import numpy as np
import time
import datetime as dt

fname = '/data/renard/SEFRAM/diodes.bin'
fname = '/data/renard/SEFRAM/20230418_cornet_HF.bin'
fname = '/data/renard/SEFRAM/20230418_cornet_BF.bin'
fname = './data/20231129_000000.sefram.bin'

FullStokes = np.ones((sefram.nof_chans, 4), dtype='int64')  # 2048 chans, XX, YY, ReXY, ImXY
FullStokes_as_chunks = FullStokes.reshape((sefram.nof_chunks,
                                           sefram.nof_chans_per_chunk,
                                           4))

packets = np.memmap(fname, dtype=sefram.dt_packet)
XCorr = []
for packet in packets:
    FullStokes_as_chunks[packet['HEADER']['CHUNK_COUNT']] = packet['PAYLOAD']
    if packet['HEADER']['CHUNK_COUNT'] == sefram.nof_chunks-1:
        XCorr.append(FullStokes.copy())
        
XCorr = np.array(XCorr)

def calc(XCorr):
    XCorr = XCorr.astype('double')
    XX = 10*np.log10(XCorr[...,0])
    YY = 10*np.log10(XCorr[...,1])
    rho = np.sqrt(XCorr[...,2]**2 + XCorr[...,3]**2) / (XCorr[...,0]+XCorr[...,1])
    phase = np.arctan2(XCorr[...,3], XCorr[...,2])
    return XX, YY, rho, phase


XX, YY, rho, phase = calc(XCorr)

Fe = 3.2e9
f = (Fe/2 + np.arange(sefram.nof_chans) / sefram.nof_chans * Fe/2) * 1e-6


plt.figure()
plt.imshow(10*np.log10(XX))

plt.figure()
plt.imshow(10*np.log10(YY))

plt.figure()
plt.imshow(np.log10(rho))

plt.figure()
plt.imshow(phase)

plt.show()


