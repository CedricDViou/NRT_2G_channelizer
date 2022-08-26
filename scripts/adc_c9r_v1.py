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
import adc5g


roach2 = "192.168.40.71"
bitstream = "../bof/adc_c9r_v1/bit_files/adc_c9r_v1_2022_Jan_05_1101.fpg"

katcp_port = 7147
dst_ip_base = 192*(2**24) + 168*(2**16) + 5*(2**8) + 40*(2**0)
dst_udp_port_base = 10000

conf_Valon = True
conf_FPGA = True
ADC_cal = True


Fe = 3600000000.0 # Hz
F_valon = Fe / 2
Fsys = F_valon / 8
Fin = 130000000# Hz



S = valon_synth.Synthesizer('/dev/ttyUSB1')
if conf_Valon:
    print('\nConfiguring Valon:')
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


print('\nConnecting to server %s on port %i... ' % (roach2, katcp_port))
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
                   'select1_chan0_status',
                   'select1_chan1_status',
                   'select1_chan2_status',
                   'select1_chan3_status',
                   'select1_chan4_status',
                   'select1_chan5_status',
                   'select1_chan6_status',
                   'select1_chan7_status',
                   'sync_cnt',
                   'armed_sync_cnt',
                   'TenGbE1_data_overflow',
                   'TenGbE1_tx_afull',
                   'TenGbE1_tx_overflow',
                   )

def monitor():
    for reg in monitoring_regs:
        print(reg, fpga.read_uint(reg))

if ADC_cal:
    # Calibrate ADC DVW
    # from https://github.com/Smithsonian/adc_tests
    # forked here https://github.com/CedricDViou/adc_tests
    print('\nCalibrating ADCs')
    # define get_snapshot as we don't have it available in our casperfpga lib version
    def get_snapshot(roach, snap_name, bitwidth=8, man_trig=True, wait_period=2):
        """
        Reads a one-channel snapshot off the given 
        ROACH and returns the time-ordered samples.
        USN version
        """
    
        grab = roach.snapshots[snap_name].read_raw(man_trig=True)[0] 
        data = struct.unpack('%ib' %grab['length'], grab['data'])
    
        return data

    # overload adc5g get_snapshot
    adc5g.tools.get_snapshot = get_snapshot
    
    adc5g.tools.set_test_mode(fpga, 0)
    adc5g.tools.set_test_mode(fpga, 1)
    opt0, glitches0 = adc5g.tools.calibrate_mmcm_phase(fpga, 0, ['ADC_wave0',])
    opt1, glitches1 = adc5g.tools.calibrate_mmcm_phase(fpga, 1, ['ADC_wave1',])
    adc5g.tools.unset_test_mode(fpga, 0)
    adc5g.tools.unset_test_mode(fpga, 1)
    
    print(adc5g.tools.pretty_glitch_profile(opt0, glitches0))
    print(adc5g.tools.pretty_glitch_profile(opt1, glitches1))
    print('Done')



Nfft = 4096
nof_lanes = 8

adc_wave_snapshots = [v for v in fpga.snapshots if 'adc_wave' in v.name.lower()]
adc_wave_snapshots.sort(key=lambda x:x.name)
for snapshot in adc_wave_snapshots:
    data = snapshot.read_raw(man_valid=True, man_trig=True)
    data = np.frombuffer(data[0]['data'], dtype='int8')

    plt.figure(1)
    Nech_to_plot = 1000
    plt.plot(np.arange(Nech_to_plot) / Fe,
             data[:Nech_to_plot],
             label=snapshot.name)

    plt.figure(2)
    nof_samples = len(data)
    f = np.arange(Nfft/2+1, dtype='float') / Nfft * Fe /1e6 
    w = np.blackman(Nfft)
    data.shape = ((-1, Nfft))
    DATA = np.fft.rfft(w * data, axis=-1)
    DATA = DATA.real**2 + DATA.imag**2
    DATA = DATA.mean(axis=0)
    plt.plot(f,
             10*np.log10(DATA),
             label=snapshot.name)

    data.tofile(snapshot.name + "_adc_data.bin")

plt.figure(1)
plt.legend()
plt.figure(2)
plt.legend()


1/0


print('Reset some counters')
fpga.write_int('select1_ctrl', 0)
fpga.write_int('cnt_rst'    , 1)
fpga.write_int('TenGbE1_rst', 3)
time.sleep(0.2)
fpga.write_int('select1_ctrl', 1)
fpga.write_int('cnt_rst'    , 0)
fpga.write_int('TenGbE1_rst', 0)
time.sleep(0.2)


# configure channel_selector
fpga.write_int('select1_nof_channels', 8)
fpga.write_int('select1_chan0_sel', 12)
fpga.write_int('select1_chan1_sel', 13)
fpga.write_int('select1_chan2_sel', 14)
fpga.write_int('select1_chan3_sel', 15)
fpga.write_int('select1_chan4_sel', 16)
fpga.write_int('select1_chan5_sel', 17)
fpga.write_int('select1_chan6_sel', 18)
fpga.write_int('select1_chan7_sel', 19)

# configure framer
fpga.write_int('TenGbE1_hdr_heap_size'    ,    2)
fpga.write_int('TenGbE1_hdr_heap_offset'  ,    3)
fpga.write_int('TenGbE1_hdr_pkt_len_words', 1024)
fpga.write_int('TenGbE1_hdr5_0x1600_DIR'  ,    5)
fpga.write_int('TenGbE1_hdr6_0x1234_DIR'  ,    6)
fpga.write_int('TenGbE1_hdr7_0x1800'      ,    7)


# configure 10G
fpga.write_int('TenGbE1_dst_ip'  , 0xc0a805b4, blindwrite=True)  # 192.168.5.180
fpga.write_int('TenGbE1_dst_port',     0xcece)



print('Wait for half second and arm PPS_trigger')
fpga.write_int('reg_arm', 0)

now = time.time()
before_half_second = 0.5 - (now-int(now))
if before_half_second < 0:
    before_half_second += 1
time.sleep(before_half_second)

fpga.write_int('reg_arm', 1)

monitor()
print('Started!!!')
for i in range(100):
    time.sleep(0.1)
    monitor()


plt.show()



