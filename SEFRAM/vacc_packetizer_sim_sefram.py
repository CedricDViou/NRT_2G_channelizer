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
#matplotlib.use('QtAgg')


import sys
import signal
import socket
import struct
from time import time, sleep
import sefram
import numpy as np
import time
import datetime as dt

def create_and_bind(dst_host, dst_port):
    # create datagram (udp) socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # print('Socket created.')
    except socket.error as msg_err:
        print('Failed to create socket. Error Code : %d, %s'.format(msg_err.errno, msg_err.strerror))
        sys.exit()

    # bind socket to local host and port
    try:
        sock.bind((dst_host, dst_port))
    except socket.error as msg_err:
        print('Bind failed. Error Code : %d, %s'.format(msg_err.errno, msg_err.strerror))
        sys.exit()

    print("Listening %s:%d" % (dst_host, dst_port))

    return sock


def plotter(dst_host, dst_port):
    sock = create_and_bind(dst_host, dst_port)
    EXPECTED_SRC_ADDR = ("192.168.41.10", 4321)
    fig, ax = plt.subplots(3, 1, figsize=(15, 5), sharex=True)
    
    FullStokes = np.ones((sefram.nof_chans, 4), dtype='int64')  # 2048 chans, XX, YY, ReXY, ImXY
    FullStokes_as_chunks = FullStokes.reshape((sefram.nof_chunks,
                                               sefram.nof_chans_per_chunk,
                                               4))
    Fe = 100   # dummmy value to start
    f = np.arange(sefram.nof_chans) / sefram.nof_chans * Fe/2
    l_P = ax[0].plot(f, 10*np.log10(FullStokes[:,0]), 'r',
                     f, 10*np.log10(FullStokes[:,1]), 'b')
    l_rho = ax[1].plot(f, np.sqrt(FullStokes[:,2]**2 + FullStokes[:,3]**2) / (FullStokes[:,0]+FullStokes[:,1]))
    l_phy = ax[2].plot(f, np.arctan2(FullStokes[:,3], FullStokes[:,2]))
    ax[0].set_ylim((105, 150))
    ax[1].set_ylim((0, 1))
    ax[2].set_ylim((-np.pi, np.pi))
    
    ax[0].set_xlim(f[[0, -1]])
    ax[1].set_xlim(f[[0, -1]])
    ax[2].set_xlim(f[[0, -1]])
    
    ax[0].set_ylabel('E and W Power (dB)')
    ax[1].set_ylabel('Coherence ratio')
    ax[2].set_ylabel('E/W phase (rad.)')
    ax[2].set_xlabel('Frequency (MHz)')
    
    timing_txt = fig.text(0.01, 0.90, "timing_txt", size=7)
    timing_txt.set_text("???-??-?? ??:??:??")

    
    plt.show(block=False)             
    
    try:
        while True:
            data, addr = sock.recvfrom(sefram.dt_packet.itemsize)
            if addr == EXPECTED_SRC_ADDR:
                packet = np.frombuffer(data, dtype=sefram.dt_packet).byteswap()
                # store in right chunk holder
                FullStokes_as_chunks[packet[0]['HEADER']['CHUNK_COUNT']] = packet[0]['PAYLOAD']
                if packet[0]['HEADER']['CHUNK_COUNT'] == sefram.nof_chunks-1:  # when a full set of chunks was received, update plots
                    payload_timing = dt.datetime.fromtimestamp(packet[0]['HEADER']['TIMESTAMP'])
                    if packet[0]['HEADER']['ADC_FREQ'] != Fe:
                        Fe = packet[0]['HEADER']['ADC_FREQ']
                        f = np.arange(sefram.nof_chans) / sefram.nof_chans * Fe/2 *1e-6
                        l_P[0].set_xdata(f)
                        l_P[1].set_xdata(f)
                        l_rho[0].set_xdata(f)
                        l_phy[0].set_xdata(f)
                        ax[0].set_xlim(f[[0, -1]])
                        ax[1].set_xlim(f[[0, -1]])
                        ax[2].set_xlim(f[[0, -1]])

                    l_P[0].set_ydata(10*np.log10(FullStokes[:,0]))
                    l_P[1].set_ydata(10*np.log10(FullStokes[:,1]))
                    l_rho[0].set_ydata(np.sqrt(FullStokes[:,2]**2 + FullStokes[:,3]**2) / (FullStokes[:,0]+FullStokes[:,1]))
                    l_phy[0].set_ydata(np.arctan2(FullStokes[:,3], FullStokes[:,2]))
                    timing_txt.set_text(payload_timing)

                    fig.canvas.draw()
                    fig.draw_artist(timing_txt)
                    fig.canvas.flush_events()

    except KeyboardInterrupt:
        print("Keyboard interrupt in process")

    finally:
        # ... Clean shutdown code here ...
        print("Close socket")
        sock.close()

        if len(data) > 0:
            print("%s:%d Last data frame was %d-byte long." % (dst_host, dst_port, len(data)))
        else:
            print("%s:%d No frames recorded." % (dst_host, dst_port))
    


def recorder(dst_host, dst_port):
    sock = create_and_bind(dst_host, dst_port)

    SDO_streams = {}
    data = []

    try:
        while True:
            data, addr = sock.recvfrom(sefram.dt_packet.itemsize)
            if addr not in SDO_streams:
                SDO_streams[addr] = open("/data/renard/SEFRAM/%s:%d_%s:%d.bin" % (*addr, dst_host, dst_port), "wb")
            SDO_streams[addr].write(data)

    except KeyboardInterrupt:
        print("Keyboard interrupt in process")

    finally:
        # ... Clean shutdown code here ...
        print("Close socket")
        sock.close()

        for (addr, fid) in SDO_streams.items():
            print("Close %s:%d_%s:%d.bin" % (*addr, dst_host, dst_port))
            fid.close()

        if len(data) > 0:
            print("%s:%d Last data frame was %d-byte long." % (dst_host, dst_port, len(data)))
        else:
            print("%s:%d No frames recorded." % (dst_host, dst_port))


#recorder("192.168.41.1", 52942)
plotter("192.168.41.1", 52942)
