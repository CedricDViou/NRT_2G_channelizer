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
import imp

# python3 -m pip install RxLab-Instruments
#from labinstruments.agilent import AgilentE8257D

import adc5g
from tqdm import tqdm 

import channelizer
channelizer = imp.reload(channelizer)



roach2 = "192.168.40.71"
bitstream = "../bof/adc_c9r_v4/bit_files/adc_c9r_v4_2022_Mar_26_1308.fpg"


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

#sig = AgilentE8257D("192.168.40.100")
#sig.set_frequency(21.9726, "MHz")
#sig.set_power(-1, "dBm")
#sig.rf_power("on")
#sig.close()


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


monitoring_regs = ('select_4f64_nof_channels',
                   'select_4f64_chan0_status',
                   'select_4f64_chan1_status',
                   'select_4f64_chan2_status',
                   'select_4f64_chan3_status',
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

adc_wave_snapshots = [v for v in fpga.snapshots if 'adcsnap' in v.name.lower()]
adc_wave_snapshots.sort(key=lambda x:x.name)

def get_adc_data():
  datas = []
  for snapshot in adc_wave_snapshots:
    data = snapshot.read_raw(man_valid=True, man_trig=False)
    data = np.frombuffer(data[0]['data'], dtype='int8')
    datas.append(data)
  return np.array(datas)


def get_adc_data(nb_itt=1):
  if nb_itt==1: 
    datas = []
    for snapshot in adc_wave_snapshots:
      data = snapshot.read_raw(man_valid=True, man_trig=False)
      data = np.frombuffer(data[0]['data'], dtype='int8')
      datas.append(data)
    datas = np.array(datas)
  else:
    data = get_adc_data(nb_itt=1)
    datas = np.empty(((nb_itt,) + data.shape))
    datas[0, :, :] = data
    for itt in tqdm(range(1, nb_itt)):
      for adc_idx, snapshot in enumerate(adc_wave_snapshots):
        data = snapshot.read_raw(man_valid=True, man_trig=False)
        data = np.frombuffer(data[0]['data'], dtype='int8')
        datas[itt, adc_idx, :] = data  
  return datas


def plot_adc_data(ax, datas):
  for adc_idx, data in enumerate(datas):
    Nech_to_plot = 1000
    ax.plot(np.arange(Nech_to_plot) / Fe * 1e9,
            data[:Nech_to_plot],
            label="ADC%d" % adc_idx)
  ax.legend()
  ax.set_xlabel('time (ns)')
  ax.set_ylabel('Amplitude (ADU)')


def plot_adc_spec(ax, datas):
  for adc_idx, data in enumerate(datas):
    nof_samples = len(data)
    f = np.arange(Nfft/2+1, dtype='float') / Nfft * Fe /1e6 
    w = np.blackman(Nfft)
    data.shape = ((-1, Nfft))
    DATA = np.fft.rfft(w * data, axis=-1)
    DATA = DATA.real**2 + DATA.imag**2
    DATA = DATA.mean(axis=0)
    ax.plot(f,
            10*np.log10(DATA),
            label="ADC%d" % adc_idx)

  # Overprint channels produced by firmware
  nof_chan = 64
  ax.set_ylim((0,100))
  df = Fe / 1e6 / 2 / nof_chan
  for chan in range(nof_chan+1):
    f0 =  Fe / 2 /1e6 * chan / nof_chan
    ax.axvspan(f0-df/2, f0+df/2, facecolor='br'[chan%2], alpha=0.1)
    ax.text(f0, 95, str(chan))

  ax.legend()
  ax.set_xlabel('Frequency (MHz)')
  ax.set_ylabel('Power (dB)')



datas = get_adc_data()
fig, axs = plt.subplots(nrows=1, ncols=2, figsize=(14,7))
plot_adc_data(axs[0], datas)
plot_adc_spec(axs[1], datas)



# ADC OGP (Offset, Gain, Phase) calibration experiments
# before trying to integrate https://github.com/CedricDViou/adc5g_devel

# Calibration sin frequency
sig_freq = 21.9726e6

# Read current OGP
n_cores = 4
adc_cores = (1, 2, 3, 4)  # ... yes starting at 1
adc_core_names = "ABCD"

def reset_OGP(roach):
  for zdok_n in (0, 1):
    for core in adc_cores:
      adc5g.set_spi_offset(roach, zdok_n, core, 0)
      adc5g.set_spi_gain  (roach, zdok_n, core, 0)
      adc5g.set_spi_phase (roach, zdok_n, core, 0)

def set_OGP(roach, OGP):
  for zdok_n in (0, 1):
    for idx_core, core in enumerate(adc_cores):
      adc5g.set_spi_offset(roach, zdok_n, core, OGP[zdok_n][idx_core][0])
      adc5g.set_spi_gain  (roach, zdok_n, core, OGP[zdok_n][idx_core][1])
      adc5g.set_spi_phase (roach, zdok_n, core, OGP[zdok_n][idx_core][2])

def get_OGP(roach):
  OGP = [[],[]]
  for zdok_n in (0, 1):
    for core in adc_cores:
      offset = adc5g.get_spi_offset(fpga, zdok_n, core)
      gain   = adc5g.get_spi_gain  (fpga, zdok_n, core)
      phase  = adc5g.get_spi_phase (fpga, zdok_n, core)
      OGP[zdok_n].append((offset, gain, phase))
  return OGP

def print_OGP(OGP):
  print( "#%6.2fMHz  zero(mV) amp(%%)  dly(ps) (adj by .4, .14, .11)" % (sig_freq/1e6))
  for zdok_n in (0, 1):
    for idx, core in enumerate(adc_cores):
      print( "ADC%d core %s  %7.4f %7.4f %8.4f" %  (zdok_n,
                                                  adc_core_names[idx],
                                                  OGP[zdok_n][idx][0],
                                                  OGP[zdok_n][idx][1],
                                                  OGP[zdok_n][idx][2]))



reset_OGP(fpga)
print_OGP(get_OGP(fpga))


def plot_adc_cores(axs, datas, Nech_to_plot=4096):
  """Plot data for individual ADC cores"""
  shape = datas.shape
  datas = datas.reshape((shape[0], shape[1]/n_cores, n_cores))
  for ax, data in zip(axs, datas):
    ax.plot(data[:Nech_to_plot,:])
  ax.legend(('a', 'b', 'c', 'd'))
  ax.set_xlabel('Time (sample#)')
  ax.set_ylabel('Amplitude (arb.)')
 
datas = get_adc_data()
fig, axs = plt.subplots(nrows=1, ncols=2, figsize=(14,7))
plot_adc_cores(axs, datas, Nech_to_plot=100)







# express offsets as mV.  1 lsb = 500mV/256. z_fact converts from lsb to mV
z_fact = 500.0/256.0

# Express delay in ps.  d_fact converts from angle at sig_freq(Hz) to ps
d_fact = 1e12/(2*np.pi*sig_freq)


from scipy.optimize import leastsq, curve_fit

def nrao_adc5g_cal(datas, plot=False):
  """Simplify/optimise https://github.com/nrao/adc5g_devel
fit A0 + A1 sin(2*pi*f) + B1 cos(2*pi*f) on each ADC cores
"""

  def fitsin(p, s, c):
    return p[0] +  p[1] * s + p[2] * c
  
  def sin_residuals(p, s, c, adc):
    res = adc - fitsin(p, s, c)
    res[adc == -128] = 0
    res[adc == 127] = 0
    return res
  
  p0 = [0.0, 90.0, 90.0]
  delta_phi = 2 * np.pi * sig_freq / Fe
  Nech = 16384
  s = np.sin(delta_phi * np.arange(Nech)).reshape(-1, 4)
  c = np.cos(delta_phi * np.arange(Nech)).reshape(-1, 4)
  t = (np.arange(Nech) / Fe).reshape(-1, 4)
  
  nb_itt = datas.shape[0]

  OGPs = []  # shape = (nb_itt, nb_ADC, n_cores, (offset, gain, phase))
  for itt in tqdm(range(nb_itt)):
  
    OGPs.append([[],[]])
    data = datas[itt]
    data = data.reshape((2,-1, 4))
  
    for zdok_n in (0, 1):
      if plot:
        plt.figure() 
      for core_idx, core in enumerate(adc_cores):
        args = (s[:,core_idx], c[:,core_idx], data[zdok_n][:,core_idx])
        plsq = leastsq(sin_residuals, p0, args)
        if not plsq[1] in (1,2,3,4):
          print "Fit failed to converge"
        z = z_fact * plsq[0][0]
        sa = plsq[0][1]
        ca = plsq[0][2]
        amp = np.sqrt(sa**2 + ca**2)
        dly = d_fact*np.arctan2(sa, ca)
          
        OGPs[itt][zdok_n].append((z, amp, dly))
      OGPs[itt][zdok_n] = np.array(OGPs[itt][zdok_n])
      avz, avamp, avdly = OGPs[itt][zdok_n].mean(axis=0)
      # Reverse the amplitude and zero differences so they can be applied to the
      # offset and gain registers directly.  The phase registers don't need the
      # reversal
      ap = 100*(avamp - OGPs[itt][zdok_n][:,1])/avamp
      OGPs[itt][zdok_n][:,0] = - OGPs[itt][zdok_n][:,0]
      OGPs[itt][zdok_n][:,1] = ap
      OGPs[itt][zdok_n][:,2] = OGPs[itt][zdok_n][:,2] - avdly
      
      if plot:
        for core_idx, core in enumerate(adc_cores):
          z, ap, dly = OGPs[itt][zdok_n][core_idx]
          plt.plot(t[:,core_idx]-dly*1e-12, (1+ap/100)* data[zdok_n][:,core_idx] + z , '.')

  return np.array(OGPs)


def usn_adc5g_cal(datas, plot=False):
  """Based on nrao_adc5g_cal,
  but replacing "p[0] +  p[1] * sin(wt) + p[2] * cos(wt)" model
  by "x[0] + x[1]*np.sin(wt + x[2])" """
  delta_phi = 2 * np.pi * sig_freq
  Nech = 16384
  t = (np.arange(Nech) / Fe).reshape(-1, 4)
  wt = delta_phi * t
  p0 = [0, 90, 0]

  nb_itt = datas.shape[0]

  OGPs = []  # shape = (nb_itt, nb_ADC, n_cores, (offset, gain, phase))
  for itt in tqdm(range(nb_itt)):
  
    OGPs.append([[],[]])
    data = datas[itt]
    data = data.reshape((2,-1, 4))
  
    for zdok_n in (0, 1):
      if plot:
        plt.figure() 
      for core_idx, core in enumerate(adc_cores):  
        optimize_func = lambda x: x[0] + x[1]*np.sin(wt[:,core_idx] - x[2]) - data[zdok_n][:,core_idx]
        plsq = leastsq(optimize_func, p0)
        if not plsq[1] in (1,2,3,4):
          print "Fit failed to converge"
        z   = z_fact * plsq[0][0]
        amp =          plsq[0][1]
        dly = d_fact * plsq[0][2]
  
        OGPs[itt][zdok_n].append((z, amp, dly))
      OGPs[itt][zdok_n] = np.array(OGPs[itt][zdok_n])
      avz, avamp, avdly = OGPs[itt][zdok_n].mean(axis=0)
      # Reverse the amplitude and zero differences so they can be applied to the
      # offset and gain registers directly.  The phase registers don't need the
      # reversal
      ap = 100*(avamp - OGPs[itt][zdok_n][:,1])/avamp
      OGPs[itt][zdok_n][:,0] = - OGPs[itt][zdok_n][:,0]
      OGPs[itt][zdok_n][:,1] = ap
      OGPs[itt][zdok_n][:,2] = OGPs[itt][zdok_n][:,2] - avdly
      
      if plot:
        for core_idx, core in enumerate(adc_cores):
          z, ap, dly = OGPs[itt][zdok_n][core_idx]
          plt.plot(t[:,core_idx]-dly*1e-12, (1+ap/100)* data[zdok_n][:,core_idx] + z , '.')

  return np.array(OGPs)

1/0


datas = get_adc_data(nb_itt=100)
nrao_OGPs = nrao_adc5g_cal(datas, plot=False)
usn_OGPs = usn_adc5g_cal(datas, plot=False)
OGPs = usn_OGPs
OGPs = nrao_OGPs

def gauss(x, H, A, x0, sigma):
    return H + A * np.exp(-(x - x0) ** 2 / (2 * sigma ** 2))


def gauss_fit(x, y):
    mean = sum(x * y) / sum(y)
    sigma = np.sqrt(sum(y * (x - mean) ** 2) / sum(y))
    popt, pcov = curve_fit(gauss, x, y, p0=[min(y), max(y), mean, sigma])
    return popt


# OGP.shape = (nb_itt, nb_ADC, n_cores, (offset, gain, phase))
OGP = np.zeros(OGPs.shape[1:])
fig, axs = plt.subplots(3,2)
for zdok_n in (0, 1):
  #print("ADC %d" % zdok_n)
  for core_idx, core in enumerate(adc_cores):
    #print("core %d" % core)
    #for itt in range(nb_itt):
    #  print(OGPs[itt,zdok_n,core_idx, :])
    for corr_idx in (0,1,2) :
      dat = OGPs[:,zdok_n,core_idx, corr_idx]
      axs[corr_idx, zdok_n].plot(dat, np.zeros_like(dat), '.')
      if False:
        dat.sort()
        dat = dat[nb_itt//10:-nb_itt//10]
        hist, bin_edges = np.histogram(dat, nb_itt/10, density=True)
        bin_centers = (bin_edges[:-1]+bin_edges[1:])/2
        axs[corr_idx, zdok_n].plot(bin_centers, hist, '.')
        H, A, x0, sigma = gauss_fit(bin_centers, hist)
        axs[corr_idx, zdok_n].plot(bin_centers, gauss(bin_centers, H, A, x0, sigma), 'k')
        OGP[zdok_n,core_idx, corr_idx] = x0
      if False:
        OGP[zdok_n,core_idx, corr_idx] = np.median(dat)
      if True:
        med = np.median(dat)
        mad = np.median(abs(dat-med))
        est = dat[ (med-3*mad < dat) & (dat < med+3*mad) ].mean()
        OGP[zdok_n,core_idx, corr_idx] = est
        #axs[corr_idx, zdok_n].plot((est, est), (-1, 1), '-')
        axs[corr_idx, zdok_n].errorbar(est, 0, xerr=mad, fmt='o')
        
[ax.set_xlabel('Offset (mV)') for ax in axs[0,:]]
[ax.set_xlabel('Gain (%)')    for ax in axs[1,:]]
[ax.set_xlabel('Phase (ps)')  for ax in axs[2,:]]
[ax.set_xlim((-50, 50)) for ax in axs[0,:]]
[ax.set_xlim((-18, 18))    for ax in axs[1,:]]
[ax.set_xlim((-14, 14))  for ax in axs[2,:]]
fig.tight_layout()


print_OGP(OGP)
set_OGP(fpga, OGP)


datas = get_adc_data()
fig, axs = plt.subplots(nrows=1, ncols=2, figsize=(14,7))
plot_adc_data(axs[0], datas)
plot_adc_spec(axs[1], datas)


plt.show()

my_channelizer = channelizer.Channelizer(fpga=fpga, Fe=Fe)
my_channelizer.debug_params()
my_channelizer.network_config()
my_channelizer.clear()


# configure FFT
#fft_shift = 0b000000
#fft_shift = 0b111111
fft_shift = 0b010111
my_channelizer.fft_shift = fft_shift


# configure rescaler
# Selects which 8 bits from 18 are outputted.
# 0 is lowest 8-bits: bits 0-7 (inclusive)
# 1: bits 4-11
# 2: bits 8-15
# 3 is highest 8-bits: bits 10-17
scale = 3
my_channelizer.scale = (scale, scale)


# configure channel_selector
#my_channelizer.channels = (0, 1, 2, 3)
my_channelizer.channels = 50

my_channelizer.arm()



monitor()
print('Started!!!')
for i in range(10):
    time.sleep(0.5)
    monitor()


plt.show()



