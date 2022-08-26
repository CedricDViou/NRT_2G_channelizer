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
bitstream = "../bof/one_gbe_ref_design/one_gbe_ref_design_2021_Dec_07_1949.fpg"

katcp_port = 7147
dst_ip_base = 192*(2**24) + 168*(2**16) + 5*(2**8) + 40*(2**0)
dst_udp_port_base = 10000

conf_Valon = True
conf_FPGA = True
plot_fft_voltages = False


Fe = 1800.0
Fadc = Fe*2
Fin = 130



S = valon_synth.Synthesizer('/dev/ttyUSB1')
if conf_Valon:
    print('Configuring Valon:')
    ext_ref = True
    S.set_ref_select(ext_ref)
    S.set_reference(10000000.0)

    S.set_options(valon_synth.SYNTH_A, double=1, half=0, divider=1, low_spur=0)
    S.set_rf_level(valon_synth.SYNTH_A, -4)
    S.set_frequency(valon_synth.SYNTH_A, Fe)

    S.set_options(valon_synth.SYNTH_B, double=1, half=0, divider=1, low_spur=0)
    S.set_rf_level(valon_synth.SYNTH_B, -4)
    S.set_frequency(valon_synth.SYNTH_B, Fin)

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
1/0


fpga.write_int('gbe_tx_ip', 0xc0a82901, blindwrite=True)  # 192.168.41.1
fpga.write_int('gbe_tx_port', 0xcece)
fpga.write_int('inter_frame_gap', 220000000)
fpga.write_int('frm_len', 4096+32)

fpga.write_int('frm_rst', 1)
fpga.write_int('gbe_rst', 1)
fpga.write_int('cnt_rst', 1)
fpga.write_int('frm_rst', 0)
fpga.write_int('gbe_rst', 0)
fpga.write_int('cnt_rst', 0)

fpga.write_int('frm_ctrl', 1)

print('IFG_cnt_val', fpga.read_uint('IFG_cnt_val'))
print('frm_cnt_val', fpga.read_uint('frm_cnt_val'))
print(    'eof_cnt', fpga.read_uint('eof_cnt'))
print('gbe_tx_full', fpga.read_uint('gbe_tx_full'))






