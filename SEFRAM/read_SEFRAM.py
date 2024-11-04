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
# Read sefram file
#
###############################################################################

import matplotlib
import matplotlib.pyplot as plt


import sys
import signal
import socket
import struct
from time import time, sleep

import imp
import sefram
sefram = imp.reload(sefram)
import tqdm

import numpy as np
import time
import datetime as dt


fname = './data/20231129_000000.sefram.bin'
fname = './data/20231202_000000.sefram.bin'
#fname = './data/20231203_000000.sefram.bin'

FullStokes = np.ones((sefram.nof_chans, 4), dtype='int64')  # 2048 chans, XX, YY, ReXY, ImXY
FullStokes_as_chunks = FullStokes.reshape((sefram.nof_chunks,
                                           sefram.nof_chans_per_chunk,
                                           4))

packets = np.memmap(fname, mode='r', dtype=sefram.dt_packet)

if False:
    print("Search for missing packets")
    
    def check_headers(curr_header, next_header):
        """
        Check that next_header should be right after curr_header
        """
        if curr_header['CHUNK_COUNT'] == 15:
            if next_header['CHUNK_COUNT'] != 0:
                return False
            if curr_header['FRAME_COUNT'] + 1 != next_header['FRAME_COUNT']:
                return False
            #OTHER CHECKS HERE ???
        else:
            if curr_header['CHUNK_COUNT'] + 1 != next_header['CHUNK_COUNT']:
                return False
            for field in ('FRAME_COUNT', 'TIMESTAMP', 'SAMPLE_COUNT'):
                if curr_header[field] != next_header[field]:
                    return False
        return True    
    
    
    def size_of_data_loss(curr_header, next_header):
        """
        Computes how many packets are lost between curr_header and next_header
        """
        return 1
    
    
    headers = packets['HEADER']
    curr_header = headers[0]
    nof_data_loss = 0
    wrong_packets = []
    size_of_data_losses = []
    for next_header in tqdm.tqdm(headers[1:]):
        if not check_headers(curr_header, next_header):
            nof_data_loss += 1
            wrong_packets.append((curr_header, next_header))
            size_of_data_losses.append(size_of_data_loss(curr_header, next_header))
        curr_header = next_header
    print(f"Nof data losses={nof_data_loss}")
    print(f"Sizes of data losses: {size_of_data_losses}")


NOF_POL = 2
NOF_CHAN = 1024
NOF_MINUTES = 24*60
NOF_PACKETS_PER_SECONDS = 5*16
NOF_PACKETS_PER_MINUTES = 60*NOF_PACKETS_PER_SECONDS


stats = {'min'     : np.empty((NOF_MINUTES, NOF_CHAN, NOF_POL), dtype='float32'),
         'mean'    : np.empty((NOF_MINUTES, NOF_CHAN, NOF_POL), dtype='float32'),
         'median'  : np.empty((NOF_MINUTES, NOF_CHAN, NOF_POL), dtype='float32'),
         '9decile' : np.empty((NOF_MINUTES, NOF_CHAN, NOF_POL), dtype='float32'),
         'max'     : np.empty((NOF_MINUTES, NOF_CHAN, NOF_POL), dtype='float32'),
         'flagged' : np.empty((NOF_MINUTES, NOF_CHAN, NOF_POL), dtype='uint32'),
         }
times = np.empty(NOF_MINUTES, dtype='uint32')

def calc(XCorr):
    XCorr = XCorr.astype('double')
    XX = XCorr[...,0]
    YY = XCorr[...,1]
    rho = np.sqrt(XCorr[...,2]**2 + XCorr[...,3]**2) / (XCorr[...,0]+XCorr[...,1])
    phase = np.arctan2(XCorr[...,3], XCorr[...,2])
    rho = None
    phase = None
    return XX, YY, rho, phase

Fe = 3.2e9
f = (Fe/2 + np.arange(sefram.nof_chans) / sefram.nof_chans * Fe/2) * 1e-6
f = f[0:NOF_CHAN]

first_chunk = 0
for packet in packets:
    if packet['HEADER']['CHUNK_COUNT'] == 0:
        break
    first_chunk += 1

for minute in tqdm.tqdm(range(NOF_MINUTES)):         
    XCorr = []
    block = packets[first_chunk + minute * NOF_PACKETS_PER_MINUTES:
                    first_chunk + (minute+1) * NOF_PACKETS_PER_MINUTES]

    FullStokes[:] = -1
    for packet in block:
        chunk_count = packet['HEADER']['CHUNK_COUNT']
        if 0 <= chunk_count < 16:
            FullStokes_as_chunks[chunk_count] = packet['PAYLOAD']
        if chunk_count == sefram.nof_chunks-1:
            XCorr.append(FullStokes.copy())
            times[minute] = packet['HEADER']['TIMESTAMP']
            
    XCorr = np.array(XCorr)[:, -1:-NOF_CHAN-1:-1, :2]
    # XX = XCorr[...,0]
    # YY = XCorr[...,1]
    # XX, YY, rho, phase = calc(XCorr)
    #I = XX + YY
    XCorr_dB = 10*np.log10(XCorr)
    stats['min'][minute, :] = np.nanmin(XCorr_dB, axis=0)
    stats['mean'][minute, :] = np.nanmean(XCorr_dB, axis=0)
    stats['max'][minute, :] = np.nanmax(XCorr_dB, axis=0)
    stats['median'][minute, :] = np.nanmedian(XCorr_dB, axis=0)
    stats['9decile'][minute, :] = np.nanquantile(XCorr_dB, 0.9, axis=0)
    stats['flagged'][minute, :] = np.sum(np.isnan(XCorr), axis=0)

1/0

if True:
    fig, axs = plt.subplots(ncols=2)
    for pol in range(NOF_POL):
        axs[pol].imshow(stats['mean'][..., pol],
                   #vmin=22.3, vmax=23.5,
                   aspect='auto',
                   extent=(f[0], f[-1], 0, 24),
                   interpolation='nearest')

    for stat_type, data in stats.items():
        fig, axs = plt.subplots(ncols=2)
        for pol in range(NOF_POL):
            axs[pol].imshow(data[..., pol],
                       #vmin=22.3, vmax=23.5,
                       aspect='auto',
                       extent=(f[0], f[-1], 0, 24))
            axs[pol].set_ylabel('Time (h)')
            axs[pol].set_xlabel('Freq (MHz)')
        fig.suptitle(f"{fname} {stat_type}")
    
    plt.show()

1/0


plt.figure(figsize=(15,5))
#plt.plot(f, I_min, label='min')
#plt.plot(f, I_median, label='median')
#plt.plot(f, I_9decile, label='9th decile')
plt.plot(f, stats['max'][:,:,0].T)  #, label='max')
plt.xlabel('Freq (MHz)')
plt.ylabel('Power (arb. dB)')
plt.xlim((f[0], f[-1]))
plt.ylim((90, 130))
plt.suptitle(fname)
plt.grid('on')
plt.legend()
plt.show()



