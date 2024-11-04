#!/home/nenufarobs/anaconda3/bin/python3

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
# Data format description of sefram data
#
###############################################################################

import struct
import numpy as np


dt_header = np.dtype({'names':   ['MAGIC',
                                  'FRAMER_ID',
                                  'FRAME_COUNT',
                                  'TIMESTAMP',
                                  'SAMPLE_COUNT',
                                  'SAMPLE_PER_SEC',
                                  'CHUNK_COUNT',
                                  'ADC_FREQ',
                                  ],
                      'formats': ['uint32',
                                  'uint32',
                                  'uint32',
                                  'uint32',
                                  'uint32',
                                  'uint32',
                                  'uint32',
                                  'uint32',
                                  ],
                      })

dt_packet = np.dtype([('HEADER' , dt_header),
                       ('PAYLOAD', np.int64, (128, 4,)),
                       ])
dt_packet = dt_packet.newbyteorder('>')


nof_chunks = 16
nof_chans_per_chunk = 128
nof_chans = nof_chunks * nof_chans_per_chunk

def open_sefram(fname, nof_spec=None):
    dat = np.memmap(fname, dtype='uint8', mode='r',)
    nof_dumps = dat.size // dt_packet.itemsize
    dat = dat[:nof_dumps * dt_packet.itemsize]
    dat = dat.view(dtype=dt_packet)
    MAGIC = dat[0]['HEADER']['MAGIC']
    if MAGIC == 0x4030201:
        swap_bytes = True
    elif MAGIC == 0x01020304:
        swap_bytes = False
    else:
        raise
    if swap_bytes:
        dat = dat[:nof_chunks].byteswap()
    assert dat[0]['HEADER']['MAGIC'] == 0x01020304
    first_chunk = np.where(dat['HEADER']['CHUNK_COUNT'] == 0)
    assert len(first_chunk) == 1
    assert len(first_chunk[0]) == 1
    dat = np.memmap(fname, dtype=dt_packet, mode='r', offset=first_chunk[0][0] * dt_packet.itemsize)
    if swap_bytes:
        dat = dat.byteswap()
    max_available_spec = len(dat) // nof_chunks * nof_chunks
    if nof_spec is None:
        nof_spec = max_available_spec
    else:
        nof_spec = min(nof_spec, max_available_spec)
    dat = dat[:nof_spec * nof_chunks]
    return dat


def get_specs(dat):

    TIMESTAMP = dat[::nof_chunks]['HEADER']['TIMESTAMP']
    SAMPLE_COUNT = dat[::nof_chunks]['HEADER']['SAMPLE_COUNT']
    SAMPLE_PER_SEC = dat[::nof_chunks]['HEADER']['SAMPLE_PER_SEC']
    #assert (SAMPLE_PER_SEC==224999999).all()
    SAMPLE_PER_SEC = SAMPLE_PER_SEC[0]
    t = TIMESTAMP + SAMPLE_COUNT / SAMPLE_PER_SEC
    
    Fe = dat[0]['HEADER']['ADC_FREQ']
    f = np.arange(nof_chans) / nof_chans * Fe/2
    
    nof_spec = len(dat) // nof_chunks
    dat=dat[:nof_spec * nof_chunks]['PAYLOAD'].reshape((nof_spec,128*nof_chunks,4))
    dat = dat.astype('float32')
    XX = dat[:,:,0].copy()
    YY = dat[:,:,1].copy()
    XY = dat[:,:,2:4].copy()
    XY = XY.view(dtype='complex64').squeeze()
    
    return t, f, XX, YY, XY


def plot_tf(t, f, XX, YY, XY, vmin=40, vmax=140, figsize=(12,6)):

    import matplotlib.pyplot as plt
    import matplotlib.dates as md
    import datetime as dt
    
    f = f / 1e6  # MHz
    t = t[[0, -1]]
    t = [dt.datetime.fromtimestamp(ts) for ts in t]
    t = md.date2num(t)
    
    fig, ax = plt.subplots(figsize=figsize)
    ax.imshow(10*np.log10(XX),
              origin = 'lower',
              extent = (f[0], f[-1], t[0], t[-1]),
              vmin=vmin, vmax=vmax)
    ax.set_title('<XX>')
    ax.set_aspect('auto')
    ax.set_xlabel('Freq (MHz)')
    ax.set_ylabel('Time')
    xfmt = md.DateFormatter('%Y-%m-%d %H:%M:%S')
    ax.yaxis.set_major_formatter(xfmt)
    fig.tight_layout()
    
    fig, ax = plt.subplots(figsize=figsize)
    ax.imshow(10*np.log10(YY),
              origin = 'lower',
              extent = (f[0], f[-1], t[0], t[-1]),
              vmin=vmin, vmax=vmax)
    ax.set_title('<YY>')
    ax.set_aspect('auto')
    ax.set_xlabel('Freq (MHz)')
    ax.set_ylabel('Time')
    xfmt = md.DateFormatter('%Y-%m-%d %H:%M:%S')
    ax.yaxis.set_major_formatter(xfmt)
    fig.tight_layout()
    
    fig, ax = plt.subplots(figsize=figsize)
    ax.imshow(10*np.log10(abs(XY)),
              origin = 'lower',
              extent = (f[0], f[-1], t[0], t[-1]),
              vmin=vmin, vmax=vmax)
    ax.set_title('|<XY>|')
    ax.set_aspect('auto')
    ax.set_xlabel('Freq (MHz)')
    ax.set_ylabel('Time')
    xfmt = md.DateFormatter('%Y-%m-%d %H:%M:%S')
    ax.yaxis.set_major_formatter(xfmt)
    fig.tight_layout()
    
    fig, ax = plt.subplots(figsize=figsize)
    ax.imshow(np.angle(XY),
              origin = 'lower',
              extent = (f[0], f[-1], t[0], t[-1]),
              vmin=-np.pi, vmax=np.pi)
    ax.set_title('arg <XY>')
    ax.set_aspect('auto')
    ax.set_xlabel('Freq (MHz)')
    ax.set_ylabel('Time')
    xfmt = md.DateFormatter('%Y-%m-%d %H:%M:%S')
    ax.yaxis.set_major_formatter(xfmt)
    fig.tight_layout()

    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(f, 10*np.log10(XX.transpose()))
    ax.set_xlim((f[0], f[-1]))
    ax.set_ylim((vmin, vmax))
    ax.set_title('<XX>')
    ax.set_xlabel('Freq (MHz)')
    ax.set_ylabel('Power (dB)')
    fig.tight_layout()
    
    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(f, 10*np.log10(YY.transpose()))
    ax.set_xlim((f[0], f[-1]))
    ax.set_ylim((vmin, vmax))
    ax.set_title('<YY>')
    ax.set_xlabel('Freq (MHz)')
    ax.set_ylabel('Power (dB)')
    fig.tight_layout()

    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(f, 10*np.log10(abs(XY.transpose())))
    ax.set_xlim((f[0], f[-1]))
    ax.set_ylim((vmin, vmax))
    ax.set_title('|<XY>|')
    ax.set_xlabel('Freq (MHz)')
    ax.set_ylabel('Crosspower (dB)')
    fig.tight_layout()

    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(f, np.angle(XY.transpose()))
    ax.set_xlim((f[0], f[-1]))
    ax.set_ylim((-np.pi, np.pi))
    ax.set_title('arg<XY>')
    ax.set_xlabel('Freq (MHz)')
    ax.set_ylabel('Phase (rad)')
    fig.tight_layout()

    plt.show()



# plot_tf(*get_specs(open_sefram('/home/cedric/sefram/192.168.41.10:4321_192.168.41.1:52942.bin')))



