#!/usr/bin/env python
'''
This code configures the ROACH2 used for NRT spectral backend.
'''

import casperfpga
import time
import numpy
import struct
import sys
import logging
import pylab
import matplotlib
import signal

roach2 = "192.168.1.100"
bitstream = ".bof"
katcp_port = 7147
dst_ip_base = 192*(2**24) + 168*(2**16) + 5*(2**8) + 40*(2**0)
dst_udp_port_base = 10000


print('TODO: Configure Valon here!!!!')
print('')

print('Connecting to server %s on port %i... ' % (roach2, katcp_port))
fpga = casperfpga.CasperFpga(roach2)
time.sleep(0.2)


assert fpga.is_connected(), 'ERROR connecting to server %s on port %i.\n' % (roach2, katcp_port))

print('------------------------')
print('Programming FPGA with %s...' % bitstream)
sys.stdout.flush()
fpga.upload_to_ram_and_program(bitstream)
print('done')


print('Configuration')
fpga.write_int('reset', 1)
time.sleep(0.2)
fpga.write_int('reset', 0)

fpga.write_int('fft_shift', 0x2aa)

fpga.write_int('rescale_pol0_bitselect', 0)
fpga.write_int('rescale_pol1_bitselect', 0)

for stream in range(7):
    fpga.write_int('TenGbE%d_hdr_head_size' % stream, 2)
    fpga.write_int('TenGbE%d_hdr_head_offset' % stream, 3)
    fpga.write_int('TenGbE%d_hdr_pkt_len_words' % stream, 1024)
    fpga.write_int('TenGbE%d_hdr5_0x1600_DIR' % stream, 5)
    fpga.write_int('TenGbE%d_hdr6_0x1234_DIR' % stream, 6)
    fpga.write_int('TenGbE%d_dst_ip' % stream, dst_ip_base + stream)
    fpga.write_int('TenGbE%d_dst_port' % stream, dst_udp_port_base + stream)



print('Wait for half second and arm PPS_trigger')
now = time.time()
before_half_second = 0.5 - (now-int(now))
if before_half_second < 0:
    before_half_second += 1
time.sleep(before_half_second)

fpga.write_int('pps_arm', 1)
fpga.write_int('pps_arm', 0)

print('Started!!!')


regs_to_poll = ['reorder_frm_cnt0',
                ]
stream_regs_to_poll = ['TenGbE%d_data_overflow',
                       'TenGbE%d_tx_afull',
                       'TenGbE%d_tx_overflow',
                       ]

# define signal handler to quit the everlasting loop nicely
RUNNING = True
def signal_handler(signal, frame):
    global RUNNING
    print('\nExiting...')
    RUNNING = False
signal.signal(signal.SIGINT, signal_handler)


while RUNNING:
    print(time.ctime())
    for reg in regs_to_poll:
        print(' %25s = %d' % (reg, fpga.read_int(reg)))
    print('')
    for stream in range(7):
        for reg in stream_regs_to_poll:
            print(' %25s = %d' % (reg % stream, fpga.read_int(reg % stream)))
    print('')
    time.sleep(1)
