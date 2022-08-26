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
bitstream = "../bof/adc_sst_v3/adc_sst_v3_2021_Nov_23_1226.fpg"

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
    f = np.arange(Nfft/2+1, dtype='float')# / Nfft * Fadc
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
Nspec_per_sec = Fadc*1e6 / Nfft

fpga.write_int('acc_len', Nspec_per_sec//10)
fpga.read_int('acc_len')

fpga.read_int('acc_cnt')

print('Configuration')
fpga.write_int('cnt_rst', 1)
time.sleep(0.2)
fpga.write_int('cnt_rst', 0)

fft_shift_reg = 0xfff
fpga.write_int('fft_shift', fft_shift_reg)
fft_shift = 2**(bin(fft_shift_reg)[2:].count('1'))

def fix2real(data, n_bits=18, bin_pt=17):
    data = data.view(np.int64).copy()
    neg = data > (2**(n_bits-1)-1)
    data[neg] -= 2**n_bits
    data = data / 2.0**bin_pt
    return data

def dump_fft_out():
    datas = []
    for snapshot in fpga.snapshots:
        if not 'fft_out' in snapshot.name.lower():
            continue
        if 'fft_out_pwr' in snapshot.name.lower():
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
        #n_bits = 18
        #bin_pt = 17
        #neg = data > (2**(n_bits-1)-1)
        #data[neg] -= 2**n_bits
        #data = data / 2.0**bin_pt
        data = fix2real(data, n_bits = 18, bin_pt = 17)

        #data.tofile(snapshot.name + "_fft_out_data.txt")
        datas.append(data)
    return datas

def dump_fft_out_pwr():
    datas = []
    for snapshot in fpga.snapshots:
        if not 'fft_out_pwr' in snapshot.name.lower():
            continue
        data = snapshot.read_raw(man_valid=True, man_trig=True)
        data = np.frombuffer(data[0]['data'], dtype='uint64')
        data = data.byteswap()
        # only 36.35 data saved in MSB of 64-bit words
        MSS = np.uint64(0x0000000FFFFFFFFF); MSZ = np.uint64(0)
        tmp = data
        #tmp = np.empty((len(data),1), dtype='int64')
        #for idx in range(len(tmp)):
        #    tmp[idx,1] = (data[idx] & MSS) >> MSZ

        data = tmp
        n_bits = 36
        bin_pt = 35
        data = data / 2.0**bin_pt

        #data.tofile(snapshot.name + "_fft_out_data.txt")
        datas.append(data)
    return datas


def plot_constellation(datas):
    for data in datas:
        plt.plot(data[:,0],data[:,1], '.')
    plt.axis('equal')


print('Wait for half second and arm PPS_trigger')
fpga.write_int('reg_arm', 0)

now = time.time()
before_half_second = 0.5 - (now-int(now))
if before_half_second < 0:
    before_half_second += 1
time.sleep(before_half_second)

fpga.write_int('reg_arm', 1)


print('Started!!!')
time.sleep(1)


if plot_fft_voltages:
    for fft_lane in range(8):
        fpga.write_int('bitselect1', fft_lane)
        fft_out = dump_fft_out()
        plt.figure()
        plot_constellation(fft_out)
        plt.xlim(-1, 1)
        plt.ylim(-1, 1)
        plt.title("fft_out cpx voltage for lane %i" % fft_lane)



def dump_vacc_snapshot(mode="auto", flush=False, normalize=True):
    assert mode in ["auto", "cross"]
    if mode == "auto":
        fpga.write_int("vacc_ss_sel", 0)
        bin_pt = 35
    else:
        fpga.write_int("vacc_ss_sel", 1)
        bin_pt = 34

    vacc_ss_snapshots = [v for v in fpga.snapshots if 'vacc_ss_ss' in v.name.lower()]
    vacc_ss_snapshots.sort(key=lambda x:x.name)

    if normalize:
        acc_len = fpga.read_int('acc_len')

    if flush:
        for snapshot in vacc_ss_snapshots:
            snapshot.read_raw(man_trig=True)

    for snapshot in vacc_ss_snapshots:  # This arms all RAMs
        snapshot.arm()

    datas = []
    for snapshot in vacc_ss_snapshots:
        data, t = snapshot.read_raw(arm=False)
        if mode == "auto":
            data = np.frombuffer(data['data'], dtype='uint64').reshape((256,2))
            data = data.byteswap()
        else: # cross
            pass
            #data = np.frombuffer(data[0]['data'], dtype='uint64')  #.reshape((512,2))
            #data = data.byteswap()
        #data.tofile(snapshot.name + "_vacc_data.txt")
        datas.append(data)
    datas = np.array(datas)
    datas = datas.transpose((1,0,2)).copy()
    datas.shape = (-1,2)
    if normalize:
        datas /= acc_len
    return datas



vacc_auto = dump_vacc_snapshot(mode="auto", flush=True, normalize=False)
plt.figure()
plt.plot(f[:2048], 10*np.log10(vacc_auto))
plt.title("vacc_auto from snapshot")

#vacc_cross = dump_vacc(mode="cross")
#figure()
#plot(vacc_cross)

def dump_vacc_bram(mode="auto", normalize=True):
    vacc_bram = [v for v in dev if 'vacc_bram' in v.lower()]
    vacc_bram.sort()

    if normalize:
        acc_len = fpga.read_int('acc_len')

    datas = []
    for bram in vacc_bram:
        data = fpga.read(bram,256*8,0)
        if mode == "auto":
            data = np.frombuffer(data, dtype='uint64')
            data = data.byteswap()
            
        else: # cross
            pass
            #data = np.frombuffer(data[0]['data'], dtype='uint64')  #.reshape((512,2))
            #data = data.byteswap()
        #data.tofile(snapshot.name + "_vacc_data.txt")
        datas.append(data)
    datas = np.array(datas)
    datas.shape = (2,8,256)
    datas = datas.transpose((2,1,0)).copy()
    datas.shape = (-1,2)
    if normalize:
        datas /= acc_len
    return datas


vacc_auto = dump_vacc_bram(mode="auto", normalize=False)
plt.figure()
plt.plot(f[:2048], 10*np.log10(vacc_auto))
plt.title("vacc from BRAM")

1/0

fpga.write_int('acc_len', 2)
n_bits = 18
debug_snapshot = [v for v in fpga.snapshots if 'debug' in v.name.lower()]
snapshot = debug_snapshot[0]
snapshot.arm(man_trig=True)
data, t = snapshot.read_raw(man_trig=True)
data=np.frombuffer(data['data'], dtype='uint64').reshape((-1,2))
data = data.byteswap()
debug_dt = np.dtype([('new_acc', np.int8  ),
                     ('din'    , np.complex64),
                     ('valid'  , np.int8  ),
                     ('dout'   , np.uint64),
                     ])
mydata = np.empty((len(data),),dtype=debug_dt)
for idx, reg_raw in enumerate(data):
    print(idx, np.binary_repr(reg_raw[0],64), np.binary_repr(reg_raw[1],64))

mydata['new_acc'] = (data[:,0] & np.uint64(0x8000000000000000)) >> np.uint64(63)
re =                (data[:,0] & np.uint64(0x000ffffc00000000)) >> np.uint64(34)
im =                (data[:,0] & np.uint64(0x00000003ffff0000)) >> np.uint64(16)
mydata['din']     = fix2real( re, 18, 17) + 1j*fix2real( im, 18, 17)
mydata['valid']   = (data[:,0] & np.uint64(0x0000000000000001)) >> np.uint64(0)
mydata['dout']    = data[:,1]


plt.figure()
plt.plot(mydata['new_acc'], '.')
plt.plot(mydata['din'].real, '.')
plt.plot(mydata['din'].imag, '.')
plt.plot(mydata['valid'], '.')
plt.plot(10*np.log10(mydata['dout'].astype(np.float64)/max(mydata['dout'])), '.')



debug_snapshot = [v for v in fpga.snapshots if 'debug' in v.name.lower()]
snapshot = debug_snapshot[0]
snapshot.arm(man_trig=True)
time.sleep(2)

for i in range(10):
    data, t = snapshot.read_raw(man_trig=True)
    data=np.frombuffer(data['data'], dtype='uint64').reshape((-1,2))
    data = data.byteswap()
    re =      (data[:,0] & np.uint64(0x000ffffc00000000)) >> np.uint64(34)
    im =      (data[:,0] & np.uint64(0x00000003ffff0000)) >> np.uint64(16)
    new_acc = (data[:,0] & np.uint64(0x8000000000000000)) >> np.uint64(63)


    trig_new_acc = np.where(new_acc == 1)[0]

    im = im.view(np.int64).copy()
    neg = im > (2**(n_bits-1)-1)
    im[neg] -= 2**n_bits
    plt.figure(1)
    plt.plot(np.arange(512)-trig_new_acc, im, '.')

    re = re.view(np.int64).copy()
    neg = re > (2**(n_bits-1)-1)
    re[neg] -= 2**n_bits
    plt.figure(2)
    plt.plot(np.arange(512)-trig_new_acc, re, '.')

plt.figure(1)
plt.title("imag on power_vacc0 in0 stream")
plt.figure(2)
plt.title("real on power_vacc0 in0 stream")


plt.show()


# code used to display vacc for both ADCs for all 56 mmcm_phase steps
# from https://github.com/Smithsonian/adc_tests
# forked here https://github.com/CedricDViou/adc_tests
# best values found to be:
ADC_phase_steps = ((32+53) // 2, (14+42) // 2)  # (zdok_1, zdok_1)


OPB_CONTROLLER = 'adc5g_controller'
OPB_DATA_FMT = '>H2B'

def inc_mmcm_phase(roach, zdok_n, inc=1):
    """
    This increments (or decrements) the MMCM clk-to-data phase relationship by 
    (1/56) * Pvco, where VCO is depends on the MMCM configuration.
    inc_mmcm_phase(roach, zdok_n)        # default increments
    inc_mmcm_phase(roach, zdok_n, inc=0) # set inc=0 to decrement
    """
    reg_val = struct.pack(OPB_DATA_FMT, (1<<(zdok_n*4)) + (inc<<(1+zdok_n*4)), 0x0, 0x0)
    roach.blindwrite(OPB_CONTROLLER, reg_val, offset=0x0)

figure, ax = plt.subplots(figsize=(10, 8))
vacc_auto = dump_vacc_snapshot(mode="auto", flush=True, normalize=False)
dat = 10*np.log10(vacc_auto)
line0, line1 = ax.plot(f[:2048], dat)
ax.set_title("vacc_auto from snapshot with mmcm_phase_inc=%d" % 0)
ax.set_xlabel('Freq (chan#)')
ax.set_ylabel('Power (dB)')
ax.set_xlabel('Freq')
ax.set_xlim((f[0], f[2047]))
ax.set_ylim((50, 140))

for i in range(56):
    inc_mmcm_phase(fpga, 0)
    inc_mmcm_phase(fpga, 1)
    vacc_auto = dump_vacc_snapshot(mode="auto", flush=True, normalize=False)
    dat = 10*np.log10(vacc_auto)
    line0.set_ydata(dat[:,0])
    line1.set_ydata(dat[:,1])
    ax.set_title("vacc_auto from snapshot with mmcm_phase_inc=%d" % i)
    figure.canvas.draw()
    figure.canvas.flush_events()



# Set best mmcm config for both ADCs:
for zdok_n, steps in enumerate(ADC_phase_steps):
    for i in range(steps):
        inc_mmcm_phase(fpga, zdok_n)


