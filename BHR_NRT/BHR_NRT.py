#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

dt_SPEAD_header = np.dtype(
    {'names':   ['MAGIC',
                 'VERSION',
                 'ITEM_WIDTH',
                 'ADDR_WIDTH',
                 'RESERVED',
                 'NUM_OF_ITEM',
                 'heap_id',
                 'heap_size',
                 'heap_offset',
                 'pkt_len_words',
                 '0x0005_DIR',
                 '0x0006_DIR',
                 '0x0007_DIR',
                 ],
     'formats': ['u1',
                 'u1',
                 'u1',
                 'u1',
                 '>u2',
                 '>u2',
                 '>u8',
                 '>u8',
                 '>u8',
                 '>u8',
                 '>u8',
                 '>u8',
                 '>u8',
                 ],
                      })

dt_packet = np.dtype([('HEADER' , dt_SPEAD_header),
                       ('PAYLOAD', 'i1', (2048, 2, 2)),
                       ])


field_name_mask  = np.array(0xffffff0000000000, dtype='uint64')
field_value_mask = np.array(0x000000ffffffffff, dtype='uint64')


def parse_header(data):
    packet = np.frombuffer(data, dtype=dt_packet)[0]
    MAGIC = packet['HEADER']['MAGIC']
    nof_chan = packet['HEADER']['0x0005_DIR'] & field_value_mask
    smpl_per_frm = packet['HEADER']['0x0006_DIR'] & field_value_mask
    chan_conf = int(packet['HEADER']['heap_offset'] & field_value_mask)
    chans = []
    for chan_idx in range(nof_chan):
        chans.append(chan_conf & 0xff)
        chan_conf = chan_conf >> 8
    header = {#'MAGIC'  : MAGIC,
              'heap_id': packet['HEADER']['heap_id'] & field_value_mask,
              'Fe'     : packet['HEADER']['heap_size'] & field_value_mask,
              'conf'   : {'nof_chan'    : nof_chan.astype('int'),
                          'smpl_per_frm': smpl_per_frm.astype('int'),
                          'chans'       : chans,
                          }
     }
    return header

def open(fname, nof_spec=None):
    dat = np.memmap(fname, dtype='uint8', mode='r',)
    nof_dumps = dat.size // dt_packet.itemsize
    dat = dat[:nof_dumps * dt_packet.itemsize]
    dat = dat.view(dtype=dt_packet)
    MAGIC = dat[0]['HEADER']['MAGIC']
    assert MAGIC == 0x53
    dat = dat.byteswap()
    return dat



