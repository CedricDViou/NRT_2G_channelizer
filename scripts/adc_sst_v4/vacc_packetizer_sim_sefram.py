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

import sys
import signal
import socket
import struct
from time import time, sleep
import sefram


def recorder(dst_host, dst_port):
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
    if dst_host.startswith('224'):  # Multicast address
        print("Join Multicast Group %s" % dst_host)
        group = socket.inet_aton(dst_host)
        net_if = socket.inet_aton("192.168.5.103")
        mreq = struct.pack('4s4s', group, net_if)
        sock.setsockopt(socket.IPPROTO_IP,
                             socket.IP_ADD_MEMBERSHIP,
                             mreq)

    SDO_streams = {}
    data = []

    try:
        while True:
            data, addr = sock.recvfrom(sefram.dt_packet.itemsize)
            if addr not in SDO_streams:
                SDO_streams[addr] = open("/home/cedric/sefram/%s:%d_%s:%d.bin" % (*addr, dst_host, dst_port), "wb")
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


recorder("192.168.41.1", 52942)
