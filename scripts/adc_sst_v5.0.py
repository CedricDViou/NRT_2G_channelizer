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
bitstream = "../bof/adc_sst_v5/bit_files/adc_sst_v5_2022_Apr_02_2303.fpg"

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



S = valon_synth.Synthesizer('/dev/ttyUSB_valon')
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
                   'vacc_n_frmr_pcktizer_cur_timestamp',
                   'vacc_n_frmr_pcktizer_cur_smpl_cnt',
                   'vacc_n_frmr_pcktizer_cur_smpl_per_sec',
                   'vacc_n_frmr_acc_cnt',
                   'OneGbE_tx_full',
                   )

def monitor():
    for reg in monitoring_regs:
        print(reg, fpga.read_uint(reg))

if ADC_cal:
    # Calibrate ADC DVW
    # from https://github.com/Smithsonian/adc_tests
    # forked here https://github.com/CedricDViou/adc_tests
    print('Calibrating ADCs')
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



Nfft = 2**12
Nspec_per_sec = Fe / Nfft
acc_len = Nspec_per_sec//10
fpga.write_int('vacc_n_frmr_acc_len', acc_len)
fpga.read_int('vacc_n_frmr_acc_len')

fpga.read_int('vacc_n_frmr_acc_cnt')

print('Configuration')
fpga.write_int('cnt_rst', 1)
fpga.write_int('vacc_n_frmr_rst', 1)

time.sleep(0.2)
fpga.write_int('cnt_rst', 0)
fpga.write_int('vacc_n_frmr_rst', 0)


print('Reset some counters')
fpga.write_int('OneGbE_rst', 1)
fpga.write_int('cnt_rst', 1)
fpga.write_int('vacc_n_frmr_rst', 1)
fpga.write_int('vacc_n_frmr_en', 0)
time.sleep(0.2)
fpga.write_int('OneGbE_rst', 0)
fpga.write_int('cnt_rst', 0)
fpga.write_int('vacc_n_frmr_rst', 0)
fpga.write_int('vacc_n_frmr_en', 0)
time.sleep(0.2)

fft_shift_reg = 0xfff
fpga.write_int('SEFRAM_fft_shift', fft_shift_reg)
fft_shift = 2**(bin(fft_shift_reg)[2:].count('1'))

def fix2real(data, n_bits=18, bin_pt=17):
    data = data.view(np.int64).copy()
    neg = data > (2**(n_bits-1)-1)
    data[neg] -= 2**n_bits
    data = data / 2.0**bin_pt
    return data

# configure framer

fpga.write_int('OneGbE_tx_ip', 0xc0a82901, blindwrite=True)  # 192.168.41.1
fpga.write_int('OneGbE_tx_port', 0xcece)

def set_time():
    fpga.write_int('vacc_n_frmr_pcktizer_timestamp_load', 0)
    now = time.time()
    timestamp = int(now)
    before_half_second = 0.5 - (now-timestamp)
    if before_half_second < 0:
       before_half_second += 1
    time.sleep(before_half_second)
    timestamp += 1
    fpga.write_int('vacc_n_frmr_pcktizer_timestamp_init', timestamp, blindwrite=True)
    fpga.write_int('vacc_n_frmr_pcktizer_timestamp_load', 1)
    return timestamp


bytes_per_chunks = 4096+32
nof_chunks = 16
IFG = 100000
time_per_frame = (bytes_per_chunks + IFG) * nof_chunks * (1/Fsys)
frame_period = acc_len / Nspec_per_sec
print("Average datarate: %f kiB/s" % (1/frame_period * (bytes_per_chunks * nof_chunks) / 1024))
print("Peak datarate   : %f MiB/s" % ((bytes_per_chunks * nof_chunks) / time_per_frame / 1024**2))
fpga.write_int('vacc_n_frmr_pcktizer_IFG', IFG)


fpga.write_int('vacc_n_frmr_pcktizer_framer_id', 0xcece)
fpga.write_int('vacc_n_frmr_pcktizer_ADC_freq', int(Fe), blindwrite=True)


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
time.sleep(1)
monitor()
time.sleep(1)
monitor()


# after dummy frame, allow outputing data and starting framer 
fpga.write_int('OneGbE_rst', 0)
fpga.write_int('vacc_n_frmr_en', 1)


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


plt.show()



