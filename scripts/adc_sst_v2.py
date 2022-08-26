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
bitstream = "../bof/adc_sst_v2/adc_sst_v2_2021_Sep_26_1253.fpg"

katcp_port = 7147
dst_ip_base = 192*(2**24) + 168*(2**16) + 5*(2**8) + 40*(2**0)
dst_udp_port_base = 10000


print('Configuring Valon:')
S = valon_synth.Synthesizer('/dev/ttyUSB0')
Fe = 2500.0
Fadc = Fe/2
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



lh = logging.StreamHandler()
logger = logging.getLogger(roach2)
logger.addHandler(lh)
logger.setLevel(10)


print('Connecting to server %s on port %i... ' % (roach2, katcp_port))
fpga = casperfpga.CasperFpga(roach2)
time.sleep(0.2)


assert fpga.is_connected(), 'ERROR connecting to server %s on port %i.\n' % (roach2, katcp_port)

print('------------------------')
print('Programming FPGA with %s...' % bitstream)
sys.stdout.flush()
fpga.upload_to_ram_and_program(bitstream)
print('done')


dev = fpga.listdev()
for d in dev:
    print(d)


for snapshot in fpga.snapshots:
    if not 'adc' in snapshot.name.lower():
        continue
    data = snapshot.read_raw(man_valid=True, man_trig=True)
    data = np.frombuffer(data[0]['data'], dtype='int8')

    plt.figure(1)
    Nech_to_plot = 1000
    plt.plot(np.arange(Nech_to_plot) / Fe,
             data[:Nech_to_plot],
             label=snapshot.name)

    plt.figure(2)
    Nfft = len(data)
    f = np.arange(Nfft, dtype='float') / Nfft * 2*Fe
    w = np.blackman(Nfft)
    plt.plot(f,
             20*np.log10(np.abs(np.fft.fft(w * data))),
             label=snapshot.name)

    data.tofile(snapshot.name + "_adc_data.bin")

plt.figure(1)
plt.legend()
plt.figure(2)
plt.legend()

plt.show()


fpga.write_int('acc_len', 100)
fpga.read_int('acc_len')


1/0


print('Configuration')
fpga.write_int('cnt_rst', 1)
time.sleep(0.2)
fpga.write_int('cnt_rst', 0)

fpga.write_int('fft_shift', 0xaaa)
fpga.write_int('bitselect1', 0x1)

def dump_vacc():
    datas = []
    for snapshot in fpga.snapshots:
        if not 'vacc_ss_ss' in snapshot.name.lower():
            continue
        data = snapshot.read_raw(man_valid=True, man_trig=True)
        data = np.frombuffer(data[0]['data'], dtype='int64')  #.reshape((512,2))

        #data.tofile(snapshot.name + "_vacc_data.txt")
        datas.append(data)
    # DATA REFORMATING NOT FINISHED
    return np.array(datas)

def dump_fft_out():
    datas = []
    for snapshot in fpga.snapshots:
        if not 'fft_out' in snapshot.name.lower():
            continue
        data = snapshot.read_raw(man_valid=True, man_trig=True)
        data = np.frombuffer(data[0]['data'], dtype='uint64')
        data = data.byteswap()
        # only 2x18 bits saved in MSB of 64-bit words
        MSS = np.uint64(0x000000000003FFFF); MSZ = np.uint64(0)
        LSS = np.uint64(0x0000000FFFFC0000); LSZ = np.uint64(18)
        tmp = np.empty((len(data),2), dtype='int32')
        for idx in range(len(tmp)):
            tmp[idx,1] = (data[idx] & MSS) >> MSZ
            tmp[idx,0] = (data[idx] & LSS) >> LSZ
        data = tmp
        neg = data > (2**17-1)
        data[neg] -= 2**18

        #data.tofile(snapshot.name + "_fft_out_data.txt")
        datas.append(data)
    return datas

def plot_constellation(datas):
    for data in datas:
        plot(data[:,0],data[:,1], '.')
    axis('equal')


print('Wait for half second and arm PPS_trigger')
fpga.write_int('reg_arm', 0)

now = time.time()
before_half_second = 0.5 - (now-int(now))
if before_half_second < 0:
    before_half_second += 1
time.sleep(before_half_second)

fpga.write_int('reg_arm', 1)


print('Started!!!')


fpga.write_int('bitselect1', 0x0)
fft_out = dump_fft_out()

for fft_lane in range(8):
    figure()
    fpga.write_int('bitselect1', fft_lane)
    fft_out = dump_fft_out()
    plot_constellation(fft_out)
    xlim(-150000, 150000)
    ylim(-150000, 150000)


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




fpga.write_int('counter_ctrl', 0x01)
for i in range(10):
    print(fpga.read_uint('counter_value'))



for snapshot in fpga.snapshots:
    snapshot.arm()


fpga.write_int('snap_ctrl',3)








with open("adc_data.txt","w") as adc_file:
    for array_index in range(0, 1024):
        adc_file.write(str(adc_in['adc_data_ch1'][array_index]))
        adc_file.write("\n")
    for array_index in range(0, 1024):  
        adc_file.write(str(adc_in['adc_data_ch2'][array_index]))
        adc_file.write("\n")    
print 'done'



