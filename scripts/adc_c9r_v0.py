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
bitstream = "../bof/adc_c9r_v0/bit_files/adc_c9r_v0_2022_Jan_19_1145.fpg"

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
                   'select_chan0_status',
                   'select_chan1_status',
                   'select_chan2_status',
                   'select_chan3_status',
                   'select_chan4_status',
                   'select_chan5_status',
                   'select_chan6_status',
                   'select_chan7_status',
                   'sync_cnt',
                   'channelizer_ovr',
                   'armed_sync_cnt',
                   'TenGbE0_data_overflow',
                   'TenGbE0_tx_afull',
                   'TenGbE0_tx_overflow',
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
    opt0, glitches0 = adc5g.tools.calibrate_mmcm_phase(fpga, 0, ['adcsnap0',])
    opt1, glitches1 = adc5g.tools.calibrate_mmcm_phase(fpga, 1, ['adcsnap1',])
    adc5g.tools.unset_test_mode(fpga, 0)
    adc5g.tools.unset_test_mode(fpga, 1)
    
    print(adc5g.tools.pretty_glitch_profile(opt0, glitches0))
    print(adc5g.tools.pretty_glitch_profile(opt1, glitches1))
    print('Done')



Nfft = 4096
nof_lanes = 8

adc_wave_snapshots = [v for v in fpga.snapshots if 'adcsnap' in v.name.lower()]
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


plt.show()
1/0

# switch ADC buses for constants
fpga.write_int('adc_in', 0b00)
fpga.write_int('adc_in', 0b01)
fpga.write_int('adc_in', 0b10)

# switch FFT_out buses for constants
#                3         2         1
#               10987654321098765432109876543210
# polar         11111111111111110000000000000000
# chan          77665544332211007766554433221100
# re             x x x x x x x x x x x x x x x x
# im            x x x x x x x x x x x x x x x x
#fft_out_swp = 0b00000000000000000000000000000000
#fft_out_swp = 0b11111111111111111111111111111111
#fpga.write_int('channelizer_out_swp', fft_out_swp, blindwrite=True)



print('Reset some counters')
fpga.write_int('select_ctrl', 0)
fpga.write_int('cnt_rst'    , 1)
fpga.write_int('TenGbE0_rst', 3)
time.sleep(0.2)
fpga.write_int('select_ctrl', 1)
fpga.write_int('cnt_rst'    , 0)
fpga.write_int('TenGbE0_rst', 0)
time.sleep(0.2)

# configure FFT
fft_shift = 0b000000
fft_shift = 0b010101
fpga.write_int('channelizer_fft_shift', fft_shift)

# configure rescaler
# Selects which 8 bits from 18 are outputted.
# 0 is lowest 8-bits: bits 0-7 (inclusive)
# 1: bits 4-11
# 2: bits 8-15
# 3 is highest 8-bits: bits 10-17
scale = 0
scale = 3
fpga.write_int('rescale_pol0_bitselect', scale)
fpga.write_int('rescale_pol1_bitselect', scale)



# configure channel_selector
nof_chan = 1
ch0, ch1, ch2, ch3 = 0, 1, 2, 3
fpga.write_int('select_nof_channels', nof_chan)
fpga.write_int('select_chan0_sel', ch0)
fpga.write_int('select_chan1_sel', ch1)
fpga.write_int('select_chan2_sel', ch2)
fpga.write_int('select_chan3_sel', ch3)
fpga.write_int('select_chan4_sel',  16)
fpga.write_int('select_chan5_sel',  17)
fpga.write_int('select_chan6_sel',  18)
fpga.write_int('select_chan7_sel',  19)

# configure framer
#fpga.write_int('TenGbE0_hdr_heap_size'    ,         0)  # optionnal for SPEAD (?), thus could be used for own need
fpga.write_int('TenGbE0_hdr_heap_size'    ,     int(Fe), blindwrite=True)  # So... used to store sampling frequency
#fpga.write_int('TenGbE0_hdr_heap_offset'  ,         0)  # required by SPEAD, but could be used for own need
chan_conf = (ch3 << 24) + (ch2 << 16) + (ch1 << 8) + (ch0 << 0)
fpga.write_int('TenGbE0_hdr_heap_offset'  , chan_conf)  # So... used to store the list of selected channels (4 chan max)
fpga.write_int('TenGbE0_hdr_pkt_len_words',      1024)  # REQUIRED!!!
# fpga.write_int('TenGbE0_hdr5_0x0005_DIR'  ,         5)  # driven by select/nof_chan
# fpga.write_int('TenGbE0_hdr6_0x0006_DIR'  ,         6)  # driven by select/samples_per_frames
fpga.write_int('TenGbE0_hdr7_0x1800    '  ,         7) # free (really is 0x0007_DIR)


# configure 10G
fpga.write_int('TenGbE0_dst_ip'  , 0xc0a805b4, blindwrite=True)  # 192.168.5.180
fpga.write_int('TenGbE0_dst_port',     0xcece)



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



