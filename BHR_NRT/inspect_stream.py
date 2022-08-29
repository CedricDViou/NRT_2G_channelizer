#!/usr/bin/env python

# Copyright (C) 2017 by Maciej Serylak
# Licensed under the Academic Free License version 3.0
# This program comes with ABSOLUTELY NO WARRANTY.
# You are free to modify and redistribute this code as long
# as you do not remove the above attribution and reasonably
# inform recipients that you have modified the original work.

# graphical display by Cedric Viou


from __future__ import absolute_import, division, print_function
import matplotlib
#matplotlib.use('GTK')
matplotlib.use('TkAgg')

import sys
import signal
import socket
import fcntl
import struct
import datetime
import time
import numpy
import BHR_NRT
from pathlib import Path

dump = False
if dump:
    dump_path = Path('./dump')
    if not dump_path.exists():
        dump_path.mkdir()
    prev_timeout = time.time()
    fid = (dump_path / f"{prev_timeout}.bin").open('wb')

def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
    s.fileno(),
    0x8915,  # SIOCGIFADDR
    struct.pack('256s', ifname.encode('utf-8')[:15])
    )[20:24])


print_data = False
plot_data = True
format_changed = False




if plot_data:
    import matplotlib.pyplot as plt

# Unicast on NB0
CEP = {0: ("BHR 0", "192.168.5.180", 0x0cece), 
       }


rcv_interface = get_ip_address('10GB02')



header_size = 64    # bytes
nof_beamlets_per_bank = 2048
RF_BW = 1800
nof_chans = 64
RF_BW_chan = 1800 / nof_chans
df = numpy.arange(-nof_beamlets_per_bank/2, nof_beamlets_per_bank/2) / nof_beamlets_per_bank * RF_BW_chan
f0 = 0
f = df + f0
nof_ticks = 16
tick_space = nof_beamlets_per_bank // nof_ticks
f_ticks = f[::tick_space]
w = numpy.hamming(nof_beamlets_per_bank)


CEP_FRAME_MAX_SIZE    = 8192 + 64
prev_conf = 0

if len(sys.argv) > 1:
    name, host, port = CEP[int(sys.argv[1])]
else:
    for item in CEP.items():
        print(f"Stream {item[0]} -> {item[1]}")
    sys.exit()


# create datagram (udp) socket
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(False)
    print('Socket created.')
except socket.error as msg_err:
    print('Failed to create socket. Error Code : %d, %s'.format(msg_err.errno, msg_err.strerror))
    sys.exit()


# bind socket to local host and port
try:
    sock.bind((host, port))
except socket.error as msg_err:
    print('Bind failed: {} {}:{}'.format(msg_err.strerror, *(host, port)))
    sys.exit()

print('Socket bind complete.')
print("Listening %s (IP=%s, port=0x%04X)" % (name, host, port))
print('Ctrl-C to quit.\n')


if host.startswith('224'):  # Multicast address
  print("Join Multicast Group {} from {}".format(host, rcv_interface))
  group = socket.inet_aton(host)
  net_if = socket.inet_aton(rcv_interface)
  mreq = struct.pack('4s4s', group, net_if)
  sock.setsockopt(
    socket.IPPROTO_IP,
    socket.IP_ADD_MEMBERSHIP,
    mreq)




if plot_data:
    plt.ion()
    fig, ax = plt.subplots(3, 1, figsize=(15, 5))

    # raw voltages
    l_V = ax[0].plot(numpy.arange(nof_beamlets_per_bank),
                     numpy.zeros((nof_beamlets_per_bank, 4)),
                     '.')
    ax[0].set_position([0.125/2, 0.53, 1.0-0.125, 0.88-0.53])#, which='original')
    ax[0].set_xlim((-1, nof_beamlets_per_bank))
    ax[0].set_xlabel('Time (samples)')
    ax[0].set_ylim((-128, 127))
    ax[0].set_ylabel('Voltage')

    # Constellation
    l_H = ax[1].plot(numpy.zeros(nof_beamlets_per_bank),
                     numpy.zeros(nof_beamlets_per_bank),
                     '.r',
                     numpy.zeros(nof_beamlets_per_bank),
                     numpy.zeros(nof_beamlets_per_bank),
                     '.b',
                     )
    ax[1].set_position([0.125/2, 0.11, 0.24-0.125, 0.46-0.11])#, which='original')
    ax[1].set_xlim((-128, 128))
    ax[1].set_xlabel('Real')
    ax[1].set_ylim((0, 20))
    ax[1].set_ylabel('Imag')

    # Power spectrum
    l_P = ax[2].plot(numpy.arange(nof_beamlets_per_bank),
                     numpy.zeros((nof_beamlets_per_bank, 2)),
                     '.')
    ax[2].set_position([0.26-0.125/2, 0.11, 1.0-0.22, 0.46-0.11])#, which='original')
    ax[2].set_xlabel('Freq')
    ax[2].set_ylim((0, 110))
    ax[2].set_ylabel('Power (dB)')
    f_ticks = list(f[::tick_space])
    f_ticks.append(f[-1])
    ax[2].set_xticks(f_ticks)
    ax[2].set_xlim((f[0], f[-1] + (f[-1]-f[-2])))
    ax[2].grid(True)


    format_txt = fig.text(0.01, 0.93, "format_txt", size=7)
    timing_txt = fig.text(0.01, 0.90, "timing_txt", size=7)
    fig.canvas.draw()


prev_utc = 0

# define signal handler to quit the everlasting loop nicely
EXIT = False


def signal_handler(signal, frame):
    global EXIT
    EXIT = True
    print('\nExiting...')


signal.signal(signal.SIGINT, signal_handler)

prev_timeout = time.time()

while not EXIT:

    try:
        data, addr = sock.recvfrom(CEP_FRAME_MAX_SIZE)
        prev_timeout = time.time()
        if dump:
          fid.write(data)  
        nb0_time = datetime.datetime.fromtimestamp(prev_timeout)

    except socket.error:
        timeout = time.time()
        if (timeout-prev_timeout) > 0.5 and prev_conf != "Socket Timed Out":
            prev_conf = "Socket Timed Out"
            print("\n@ %s: No stream on %s (IP=%s, port=0x%04X)" % (datetime.datetime.utcnow().isoformat(),
                                                                    name,
                                                                    host,
                                                                    port))
            if plot_data:
                fig.patch.set_facecolor('xkcd:red')
                fig.canvas.draw()

        continue

    header = BHR_NRT.parse_header(data)

    if header is None:
        if prev_conf is not None:
            prev_conf = None
            print("\n@ %s: Invalid frames" % datetime.datetime.utcnow().isoformat())
        else:
            print(".", end='\r')  #, flush=True)
            sys.stdout.flush()
            prev_utc = 0
            time.sleep(1)
        continue


    utc = header['heap_id']
    if utc-prev_utc < 1000:  
        continue

    prev_utc = utc
    latency = -1
    payload_timing = "  Timestamp:%d -> latency=%f ms"% (header['heap_id'],
                                                         latency)


    # if stream resumed, print message
    if prev_conf == "Socket Timed Out":
        if plot_data:
            fig.patch.set_facecolor('xkcd:white')
        print("Stream resumed from %s:%u (%s) to %s:%u (This server)" % (addr[0], addr[1], name, host, port))
        prev_conf = (-1,)  # make dummy configuration to print new payload_format

    # if frame format changes, print new configuration
    if prev_conf != (header['conf'],):
        format_changed = True
        prev_conf = (header['conf'], )
        payload_format = """\n@ %s:
  from %s:%u (%s) to %s:%u (This server): (Fe, nof_chans, smpl_per_frm) = (%d, %d, %d), chans selected = %s""" % (nb0_time.isoformat(),
                       addr[0], addr[1], name, host, port,
                       header['Fe'], header['conf']['nof_chan'], header['conf']['smpl_per_frm'],
                       str(header['conf']['chans']))
        print(payload_format)
        print(payload_timing)
        k = numpy.arange(nof_beamlets_per_bank)

        nof_beamlets_per_bank = header['conf']['smpl_per_frm']
        RF_BW = header['Fe'] / 2 / 1e6
        RF_BW_chan = RF_BW / nof_chans
        df = numpy.arange(-nof_beamlets_per_bank/2, nof_beamlets_per_bank/2) / nof_beamlets_per_bank * RF_BW_chan
        f0 = header['conf']['chans'][0] * RF_BW_chan
        f = df + f0
        f_ticks = list(f[::tick_space])
        f_ticks.append(f[-1])
        ax[2].set_xlim((f[0], f[-1] + (f[-1]-f[-2])))
        ax[2].set_xticks(f_ticks)
        

    print(payload_timing, end='\r')  #, flush=True)
    sys.stdout.flush()

    dropped_frames = 0

    if plot_data:
        ax[1].set_ylim((-2**(8-1)-1, 2**(8-1)-1+1))

        dtype = 'int8'
        dat = numpy.frombuffer(data[header_size:], dtype=dtype)
        #dat.shape = (nof_beamlets_per_bank, 2 * 2)
        #dat = dat[:,[3,2,1,0]].copy()
        # samples odd and even were swapped
        # dat.shape = (nof_beamlets_per_bank//2, 2, 2, 2)
        # dat = dat[:,[1,0],:,:].copy()
        dat.shape = (nof_beamlets_per_bank, 2, 2)
        # make data complex
        dat = dat.astype('float32').view('complex64').squeeze()

        #print(dat[:5,:])
        l_V[0].set_xdata(k)
        l_V[0].set_ydata(dat[:,0].real)
        l_V[1].set_xdata(k)
        l_V[1].set_ydata(dat[:,0].imag)
        l_V[2].set_xdata(k)
        l_V[2].set_ydata(dat[:,1].real)
        l_V[3].set_xdata(k)
        l_V[3].set_ydata(dat[:,1].imag)

        l_H[0].set_xdata(dat[:,0].real)
        l_H[0].set_ydata(dat[:,0].imag)
        l_H[1].set_xdata(dat[:,1].real)
        l_H[1].set_ydata(dat[:,1].imag)

        DAT = numpy.fft.fft(w[:,numpy.newaxis] * dat, axis=0)
        P_DAT = 10 * numpy.log10( DAT.real**2 + DAT.imag**2)
        P_DAT = numpy.fft.fftshift(P_DAT, axes=0)
        l_P[0].set_xdata(f)
        l_P[0].set_ydata(P_DAT[:,0])
        l_P[1].set_xdata(f)
        l_P[1].set_ydata(P_DAT[:,1])
        fig.canvas.draw()

        timing_txt.set_text(payload_timing)
        fig.draw_artist(timing_txt)

        if format_changed:
            format_txt.set_text(payload_format)
            fig.draw_artist(format_txt)
            format_changed = False



if plot_data:
    plt.close('all')


if host.startswith('224'):  # Multicast address
  print("Leave Multicast Group {} from {}".format(host, rcv_interface))
  sock.setsockopt(
    socket.IPPROTO_IP,
    socket.IP_DROP_MEMBERSHIP,
    mreq)


sock.close()


if dump:
  fid.close()

