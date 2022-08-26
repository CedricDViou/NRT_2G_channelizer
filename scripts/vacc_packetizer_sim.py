#!/home/cedric/anaconda3/envs/2point7/bin/python
'''
This code configures the ROACH2 used for NRT spectral backend.
'''

import casperfpga
import time
import numpy as np
import struct
import sys
import logging
import pylab
import matplotlib.pyplot as plt
import signal
import valon_synth


roach2 = "192.168.40.71"
bitstream = "../bof/vacc_packetizer_sim/vacc_packetizer_sim_2021_Dec_11_1735.fpg"
katcp_port = 7147
dst_ip_base = 192*(2**24) + 168*(2**16) + 5*(2**8) + 40*(2**0)
dst_udp_port_base = 10000

conf_Valon = True
conf_FPGA = True


Fe = 3600000000.0 # Hz
F_valon = Fe / 2
Fsys = F_valon / 8
Fin = 130000000# Hz



S = valon_synth.Synthesizer('/dev/ttyUSB1')
if conf_Valon:
    print('Configuring Valon:')
    ext_ref = True
    S.set_ref_select(ext_ref)
    S.set_reference(10000000.0)

    S.set_options(valon_synth.SYNTH_A, double=1, half=0, divider=1, low_spur=0)
    S.set_rf_level(valon_synth.SYNTH_A, -4)
    S.set_frequency(valon_synth.SYNTH_A, F_valon/1e6)

    S.set_options(valon_synth.SYNTH_B, double=1, half=0, divider=1, low_spur=0)
    S.set_rf_level(valon_synth.SYNTH_B, -4)
    S.set_frequency(valon_synth.SYNTH_B, Fin/1e6)

    print('Done\n')

FA = S.get_frequency(valon_synth.SYNTH_A)
PA = S.get_rf_level(valon_synth.SYNTH_A)
FB = S.get_frequency(valon_synth.SYNTH_B)
PB = S.get_rf_level(valon_synth.SYNTH_B)
LA = S.get_phase_lock(valon_synth.SYNTH_A)
LB = S.get_phase_lock(valon_synth.SYNTH_B)


print("  Input clock is %f MHz, %f dBm (%slocked)" % (FA,
                                                     PA,
                                                     "" if LA else "NOT "))
print("    =>  Sampling clock is %f MHz, %f dBm" % (2*FA, PA))
print("  Input tone is %f MHz, %f dBm (%slocked)" % (FB,
                                                    PB,
                                                    "" if LB else "NOT "))




lh = logging.StreamHandler()
logger = logging.getLogger(roach2)
logger.addHandler(lh)
logger.setLevel(10)


print('Connecting to server %s on port %i... ' % (roach2, katcp_port))
fpga = casperfpga.CasperFpga(roach2)
time.sleep(0.2)


assert fpga.is_connected(), 'ERROR connecting to server %s on port %i.\n' % (roach2, katcp_port)

if conf_FPGA:
    print('------------------------')
    print('Programming FPGA with %s...' % bitstream)
    sys.stdout.flush()
    fpga.upload_to_ram_and_program(bitstream)
    print('done')


dev = fpga.listdev()
for d in dev:
    print(d)

monitoring_regs = (
                   'packetizer_cur_timestamp',
                   'packetizer_cur_sample_cnt',
                   'packetizer_cur_sample_per_sec',
                   'packetizer_IFG_cnt_val',
                   'eof_cnt',
                   'gbe_tx_full',
                   )

def monitor():
    for reg in monitoring_regs:
        print(reg, fpga.read_uint(reg))



fpga.write_int('gbe_tx_ip', 0xc0a82901, blindwrite=True)  # 192.168.41.1
fpga.write_int('gbe_tx_port', 0xcece)

# simulates the generation of vacc data frames
vacc_frm_len = 256
inter_vacc_gap = Fsys/10-256
fpga.write_int('inter_frame_gap', inter_vacc_gap) # ~1/10s
fpga.write_int('frm_len', vacc_frm_len)  # vacc generates busrts of 256 words over 8 lanes -> 2048 chans

# resets system
fpga.write_int('frm_rst', 1)
fpga.write_int('gbe_rst', 1)
fpga.write_int('cnt_rst', 1)
fpga.write_int('frm_rst', 0)
fpga.write_int('gbe_rst', 0)
fpga.write_int('cnt_rst', 0)


# configure framer

def set_time():
    fpga.write_int('packetizer_timestamp_load', 0)
    now = time.time()
    timestamp = int(now)
    before_half_second = 0.5 - (now-timestamp)
    if before_half_second < 0:
       before_half_second += 1
    time.sleep(before_half_second)
    timestamp += 1
    fpga.write_int('packetizer_timestamp_init', timestamp, blindwrite=True)
    fpga.write_int('packetizer_timestamp_load', 1)
    return timestamp


bytes_per_chunks = 4096+32
nof_chunks = 16
IFG = 100000
time_per_frame = (bytes_per_chunks + IFG) * nof_chunks * (1/Fsys)
frame_period = inter_vacc_gap + vacc_frm_len
print("Average datarate: %f kiB/s" % (Fsys / frame_period * (bytes_per_chunks * nof_chunks) / 1024))
print("Peak datarate   : %f MiB/s" % ((bytes_per_chunks * nof_chunks) / time_per_frame / 1024**2))
fpga.write_int('packetizer_IFG', IFG)


fpga.write_int('packetizer_framer_id', 0xcece)
fpga.write_int('packetizer_ADC_freq', int(Fe), blindwrite=True)


# arm sync signal
print('Wait for half second and arm PPS_trigger')
fpga.write_int('reg_arm', 0)

now = time.time()
before_half_second = 0.5 - (now-int(now))
if before_half_second < 0:
    before_half_second += 1
time.sleep(before_half_second)

fpga.write_int('reg_arm', 1)


monitor()

# after dummy frame, allow outputing data and starting framer 
fpga.write_int('frm_ctrl', 1)

monitor()

print(set_time())

monitor()
time.sleep(1)
monitor()
time.sleep(1)
monitor()
time.sleep(1)
monitor()
time.sleep(1)


monitor()


