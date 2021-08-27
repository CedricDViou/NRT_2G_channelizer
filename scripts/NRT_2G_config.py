#!/home/cedric/anaconda3/envs/2point7/bin/python
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
import valon_synth

roach2 = "192.168.40.71"
bitstream = "../bof/nrt_2g_no_dsp/nrt_2g_no_dsp_2019_Aug_27_1439.fpg"
bitstream = "../bof/adc_and_regs/adc_and_regs_2021_Aug_24_1159.fpg"
katcp_port = 7147
dst_ip_base = 192*(2**24) + 168*(2**16) + 5*(2**8) + 40*(2**0)
dst_udp_port_base = 10000


print('Configuring Valon:')
S = valon_synth.Synthesizer('/dev/ttyUSB0')
Fe = 1500.0
Fin = 130.0

ext_ref = True
S.set_ref_select(ext_ref)
S.set_reference(10000000.0)

S.set_options(valon_synth.SYNTH_A, double=1, half=0, divider=1, low_spur=0)
S.set_rf_level(valon_synth.SYNTH_A, -4)
S.set_frequency(valon_synth.SYNTH_A, Fe)

S.set_options(valon_synth.SYNTH_B, double=1, half=0, divider=1, low_spur=0)
S.set_rf_level(valon_synth.SYNTH_B, -4)
S.set_frequency(valon_synth.SYNTH_B, Fin)

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
print('Done\n')


print('Connecting to server %s on port %i... ' % (roach2, katcp_port))
fpga = casperfpga.CasperFpga(roach2)
time.sleep(0.2)


assert fpga.is_connected(), 'ERROR connecting to server %s on port %i.\n' % (roach2, katcp_port)

print('------------------------')
print('Programming FPGA with %s...' % bitstream)
sys.stdout.flush()
fpga.upload_to_ram_and_program(bitstream)
print('done')


print(fpga.listdev())

fpga.write_int('counter_ctrl', 0x01)
for i in range(10):
    print(fpga.read_uint('counter_value'))

fpga.write_int('a', 0x01)
fpga.write_int('b', 0x10)
print(fpga.read_int('sum_a_b'))



for snapshot in fpga.snapshots:
    data = snapshot.read_raw(man_valid=True, man_trig=True)
    data = np.frombuffer(data[0]['data'], dtype='int8')

    figure(1)
    plot(data[:1000])

    figure(2)
    Nfft = len(data)
    f = np.arange(Nfft, dtype='float') / Nfft * 2*Fe
    plot(f, 20*np.log10(np.abs(fft.fft(data*blackman(Nfft)))))

    data.tofile(snapshot.name + "_adc_data.txt")

