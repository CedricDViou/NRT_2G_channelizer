#!/home/cedric/anaconda3/envs/2point7/bin/python
# -*- coding: utf-8 -*-

################################################################################
#
# Copyright (C) 2022
# Observatoire Radioastronomique de Nançay,
# Observatoire de Paris, PSL Research University, CNRS, Univ. Orléans, OSUC,
# 18330 Nançay, France
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
################################################################################
# Author: Cedric Viou (Cedric.Viou@obs-nancay.fr)
#
# Description:
# Configure and run design adc_sst_v7 (SEFRAM + Channelizer (4x28MHz from 1.8GHz))
################################################################################


from configparser import Interpolation
import time
import numpy as np
import struct
import sys
import logging
import pylab
import matplotlib.pyplot as plt
import matplotlib.dates
import datetime
import signal
import imp
import tqdm

import casperfpga
import ADC_clock
import ADC
import sefram
import channelizer
import histogram



ADC_clock = imp.reload(ADC_clock)
ADC = imp.reload(ADC)
sefram = imp.reload(sefram)
channelizer = imp.reload(channelizer)
histogram = imp.reload(histogram)


roach2 = "192.168.40.71"
bitstream = "../bof/adc_receiver_v1/adc_receiver_v1_2024_Feb_03_1855.fpg"
bitstream = "../bof/adc_receiver_v1/adc_receiver_v1_2024_Feb_05_1210.fpg"
bitstream = "../bof/adc_receiver_v1/adc_receiver_v1_2024_Feb_16_1505.fpg"

conf_Valon = True
ADC_DVW_cal = True
ADC_OGP_cal = True

#FEED, Fe = 'HF', 3200000000.0 # 1.6-3.2  GHz
FEED, Fe = 'BF', 3700000000.0 #   0-1.85 GHz
F_valon = Fe / 2
Fsys = F_valon / 8
Fin = 130000000# Hz


Valon = ADC_clock.ADC_clock()
if conf_Valon:
  Valon.set_config(FA=F_valon/1e6,
                   PA=5,
                   FB=Fin/1e6,
                   PB=-4,
                   )
Valon.print_config()


# class to control CASPER FPGA design for NRT channelizer
class NRT_channelizer(object):
  def __init__(self, name, bitstream=None, Fe=None, feed='BF'):
    self.name = name
    self.fpga = casperfpga.CasperFpga(self.name)

    assert self.fpga.is_connected(), 'ERROR connecting to server %s.\n' % (self.name)
    if bitstream is not None:
      print('------------------------')
      print('Programming FPGA with %s...' % bitstream)
      sys.stdout.flush()
      self.fpga.upload_to_ram_and_program(bitstream)
      time.sleep(0.2)
      print('done')

    self.Fe = Fe
    self.F_valon = self.Fe / 2
    self.Fsys = self.F_valon / 8
    self._feed = feed


    self.monitoring_regs = (
                   # SEFRAM
                   'frmr_pck_cur_timestamp',
                   'frmr_pck_cur_sample_cnt',
                   'frmr_pck_cur_sysfreq',
                   'frmr_acc_cnt',
                   'OneGbE_tx_full',

                   # Channelizer
                   'sync_cnt',
                   'armed_sync_cnt',
                   'TenGbE0_gbe0_tx_cnt',
                   'TenGbE0_data_overflow',
                   'TenGbE0_tx_afull',
                   'TenGbE0_tx_overflow',
                   )

    # Add peripherals and submodules
    self.ADCs = (ADC.ADC(fpga=self.fpga, zdok_n=0, Fe=self.Fe, snap_basename='adcsnap'),
                 ADC.ADC(fpga=self.fpga, zdok_n=1, Fe=self.Fe, snap_basename='adcsnap'))
    self.SEFRAM = sefram.sefram(fpga=self.fpga, Fe=self.Fe)
    self.Receivers = [channelizer.receiver(fpga=self.fpga, Fe=self.Fe, decimation=2, receiver_basename="rcvr0_"),
                      #channelizer.receiver(fpga=self.fpga, Fe=self.Fe, decimation=2, receiver_basename="rcvr1_"),
                      ]
    self.histograms = histogram.histogram(fpga=self.fpga, basename='histogram_')


    # init modules
    self.SEFRAM.disable()


  def cnt_rst(self):
    self.fpga.write_int('cnt_rst', 1)
    self.fpga.write_int('cnt_rst', 0)

  def arm_PPS(self):
    """
    todo
    """
    self.fpga.write_int('reg_arm', 0)
    now = time.time()
    before_half_second = 0.5 - (now-int(now))
    if before_half_second < 0:
      before_half_second += 1
    time.sleep(before_half_second)
    self.fpga.write_int('reg_arm', 1)

  def listdev(self):
    return self.fpga.listdev()

  def monitor(self):
    for reg in self.monitoring_regs:
        print(reg, self.fpga.read_uint(reg))

  @property
  def feed(self):
    return self._feed

  @feed.setter
  def feed(self, value):
    if value not in ('BF', 'HF'):
      raise ValueError('NRT feeds are BF (1-1.8GHz, connected on ADC_I) or HF (1.7-3.5GHz, conected on ADC_Q)')
    self._feed = value
    adcmode = {'BF': 'I',
               'HF': 'Q',
               }
    for ADC in self.ADCs:
      ADC.adcmode=adcmode[self._feed]
      ADC.adcmode=adcmode[self._feed]


  def input_sel(self, source='ADC'):
    if source == 'ADC':
      self.fpga.write_int('din_sel', 0)
    elif source == 'Arb_gen':
      self.fpga.write_int('din_sel', 1)

  def conf_arb_gen(self, **kwargs):
    ADDR_W = 8
    nof_samples_per_w = 16
    dt, shape, d_w, d_dp = np.dtype('int8'), (2**ADDR_W, nof_samples_per_w), 8, 7

    assert "mode" in kwargs, "mode kwarg must be specified"
    if kwargs["mode"] == "constant":
      assert "amp" in kwargs, "amp kwarg must be specified for mode \"constant\""
      constant = kwargs['amp']
      data = np.full((2**ADDR_W) * nof_samples_per_w, constant, dtype=dt)
    elif kwargs["mode"] == "sine":
      assert "a0" in kwargs, "a0 kwarg must be specified for mode \"sine\""
      assert "f0" in kwargs, "k0 kwarg must be specified for mode \"sine\""
      nof_samples = (2**ADDR_W) * nof_samples_per_w
      k0 = kwargs['f0'] / self.Fe * nof_samples
      data = kwargs['a0'] * np.sin(2*np.pi * k0 * np.arange(nof_samples) / nof_samples)
      data = data.astype(dt)
    elif kwargs["mode"] == "sine+noise":
      assert "a0" in kwargs, "a0 kwarg must be specified for mode \"sine\""
      assert "f0" in kwargs, "k0 kwarg must be specified for mode \"sine\""
      assert "sigma" in kwargs, "sigma kwarg must be specified for mode \"sine\""
      nof_samples = (2**ADDR_W) * nof_samples_per_w
      k0 = kwargs['f0'] / self.Fe * nof_samples
      data = kwargs['a0'] * np.sin(2*np.pi * k0 * np.arange(nof_samples) / nof_samples)
      data += kwargs['sigma'] * np.random.randn(nof_samples)
      data = data.astype(dt)
    else:
      raise ValueError("Mode %s is not supported" % (kwargs["mode"]))

    data.shape = shape
    bin_content = data.tobytes()

    self.fpga.blindwrite("arb_gen0_mem", bin_content)
    self.fpga.blindwrite("arb_gen1_mem", bin_content)



mydesign = NRT_channelizer(
  roach2,
  bitstream=bitstream,
  Fe=Fe
  )

mydesign.feed = FEED


dev = mydesign.listdev()
for d in dev:
    print(d)
print()


if ADC_DVW_cal:
  print('Calibrating ADCs')
  [ ADC.run_DVW_calibration() for ADC in mydesign.ADCs ]
  [ ADC.print_DVW_calibration() for ADC in mydesign.ADCs ]
  print('Done')



mydesign.input_sel(source='ADC')
#mydesign.input_sel(source='Arb_gen')
#mydesign.conf_arb_gen(mode="constant", amp=10)
#mydesign.conf_arb_gen(mode="sine+noise", a0=10, f0=100e6, sigma=30)


if False:
  [ ADC.get_snapshot(count=100) for ADC in mydesign.ADCs ]
  [ ADC.dump_snapshot() for ADC in mydesign.ADCs ]

fig, axs = plt.subplots(nrows = len(mydesign.ADCs), 
                        ncols = 3,
                        sharex='col', sharey='col',
                        )
for ADC_axs, ADC in zip(axs, mydesign.ADCs):
  ADC.plot_snapshot(ADC_axs)
plt.tight_layout()
plt.show(block=False)

mydesign.histograms.get_counts()
mydesign.histograms.plot_counts()



print('SEFRAM Configuration')

mydesign.SEFRAM.disable()
mydesign.cnt_rst()
time.sleep(0.2)



Nspec_per_sec = mydesign.SEFRAM.Fe / mydesign.SEFRAM.Nfft
acc_len = int(Nspec_per_sec // 10)
mydesign.SEFRAM.acc_len = acc_len

print('vacc_n_frmr_acc_cnt = ', mydesign.SEFRAM.acc_cnt)

fft_shift_reg = 0b1111111111
mydesign.SEFRAM.fft_shift = fft_shift_reg
print('SEFRAM FFT gain = ', mydesign.SEFRAM.fft_gain)

mydesign.SEFRAM.dst_addr = ("192.168.41.1", 0xcece)
mydesign.SEFRAM.IFG = 100000
mydesign.SEFRAM.print_datarate()

# fpga.write_int('vacc_n_frmr_pcktizer_ADC_freq', int(Fe), blindwrite=True)
# set during SEFRAM instanciation

# mydesign.SEFRAM.ID = 0xcece
# set in SEFRAM constructor

mydesign.SEFRAM.arm()    # à renomer



print('Receivers Configuration')
receiver_configs = [
                    #{"Fc":1.623e9, "decimation": 2, "dst_IP": 0xc0a805b4, "dsp_port": 0xce00, },
                    #{"Fc":1.628e9, "decimation": 2, "dst_IP": 0xc0a805b4, "dsp_port": 0xce01, },
                    #{"Fc":100e6, "decimation": 2, "dst_IP": 0xc0a805b4, "dsp_port": 0xce00, },
                    #{"Fc":60e6, "decimation": 2, "dst_IP": 0xc0a805b4, "dsp_port": 0xce01, },
                    #{"Fc":1.421e9, "decimation": 8, "dst_IP": 0xc0a805b4, "dsp_port": 0xce00, },
                    {"Fc":1.425e9, "decimation": 2, "dst_IP": 0xc0a805b4, "dsp_port": 0xce01, },
                    {"Fc":1.5e9, "decimation": 2, "dst_IP": 0xc0a805b4, "dsp_port": 0xce02, },
                    {"Fc":1.6e9, "decimation": 2, "dst_IP": 0xc0a805b4, "dsp_port": 0xce03, },
                    ]

for receiver, config in zip(mydesign.Receivers, receiver_configs):
  #receiver.network_config(config["dst_IP"], config["dsp_port"])
  #receiver.clear()
  #receiver.scale = 0
  receiver.Fc = config["Fc"]
  receiver.decimation = config["decimation"]
  #receiver.kc = 450



# check that NCO tables are programmed properly
if True:
  for receiver, config in zip(mydesign.Receivers, receiver_configs):
    prev_tables = receiver.NCO_tables.copy()
    receiver.NCO_read_tables()
    new_tables = receiver.NCO_tables.copy()
    assert (prev_tables == new_tables).all()



print('Wait for half second and arm PPS_trigger')
mydesign.arm_PPS()
mydesign.monitor()



# get and plot some data from mixer and dec_fir to chek data formats and overflows
for receiver in mydesign.Receivers:
  snap_names = ("dec_out",
                "HBs_HB2_out",
                "HBs_HB1_out",
                "HBs_HB0_out",
                )
  raw_fmt = False                
  snap_data = {}
  fig, axs = plt.subplots(figsize=(10, 10),
                          nrows = len(snap_names), 
                          ncols = 1,
                          sharex='col',
                          #sharey='col',
                          )
  if len(snap_names) == 1:
    axs = (axs,)
  for ax, snap_name in zip(axs, snap_names):
    (d_w, d_dp), dat = receiver.get_snapshot(snap_name=snap_name, raw_fmt=raw_fmt)
    integer_part_w = d_w - d_dp - 1
    max_modulus = 2**integer_part_w
    if len(dat.shape) == 1:
      dat = dat[:, None]
    mean = np.mean(dat, axis=0)
    std = np.std(dat, axis=0)
    ax.plot(dat)
    snap_data[snap_name] = dat
    title = snap_name + "\n$\mu \pm \sigma =$"
    for m,s in zip(mean, std):
      title +=  "\n$%4.2f \pm %4.2f$" % (m, s)
    title = title[:-1] + "$"
    ax.set_title(title)
    ax.set_ylim((-max_modulus, max_modulus))
    
    if snap_name == "dec_out":
      dat.shape = (-1, 2, 2)
      dat = dat[..., 0] + 1j * dat[..., 1]
      DAT = np.fft.fft(dat, axis=0)
      DAT[DAT == 0] = 0.01
      DAT = np.fft.fftshift(DAT, axes=0)
      DAT = 10*np.log10(DAT.real**2 + DAT.imag**2)
      fig_tx, ax = plt.subplots(figsize=(10, 10))
      ax.plot(DAT)
      ax.axvline(1023, c='r')
      ax.axvline(2048+1024, c='r')
plt.show(block=False)


for receiver in mydesign.Receivers:
  snap_name, decimation, ymin, ymax = "dec_out", 1, 0, 10
  #snap_name, decimation, ymin, ymax = "HBs_HB2_out", 2, -6, 2
  #snap_name, decimation, ymin, ymax = "HBs_HB1_out", 4, -15, -6
  #snap_name, decimation, ymin, ymax = "HBs_HB0_out", receiver.decimation, -2, 6
  if decimation == 8:
    ymin, ymax = -25, -15

  dats = []
  t0 = datetime.datetime.utcnow()
  Nacc = 100
  raw_fmt = False
  for itt in tqdm.tqdm(range(Nacc)):
    (d_w, d_dp), dat = receiver.get_snapshot(snap_name=snap_name, raw_fmt=raw_fmt, man_valid=False)
    dats.append(dat)
  t1 = datetime.datetime.utcnow()

  t0 = matplotlib.dates.date2num(t0)
  t1 = matplotlib.dates.date2num(t1)

  dats =  np.array(dats)
  Nacc, Nfft, _ = dats.shape
  dats.shape = (Nacc, Nfft, 2, 2)
  dats = dats[..., 0] + 1j * dats[..., 1]

  fig, axs = plt.subplots(nrows=2, ncols=2,
                          sharex='row', sharey='all',
                          figsize=(10, 5))

  for itt in (0, ):
    for pol in (0, 1):
      axs[0, pol].plot(dats[itt, :, pol].real, dats[itt, :, pol].imag, 'k.')
      axs[1, pol].plot(dats[itt, :, pol].real, 'r')
      axs[1, pol].plot(dats[itt, :, pol].imag, 'g')
  axs[0, 0].set_xlim(-1,1)
  axs[0, 0].set_ylim(-1,1)
  fig.suptitle(str(receiver) + "\nBW=%6.2f MHz" % (BW*1e-6))

    

  DATs = np.fft.fft(dats, axis=1)
  DATs[DATs == 0] = 0.01
  DATs = np.fft.fftshift(DATs, axes=1)
  DATs = DATs.real**2 + DATs.imag**2
  DAT_min = DATs.min(axis=0)
  DAT_mean = DATs.mean(axis=0)
  DAT_max = DATs.max(axis=0)
  BW = receiver.Fe / receiver.NCO_par / decimation
  df = np.arange(-Nfft/2, Nfft/2, dtype=float)/Nfft * BW
  f = (receiver.Fc + df)

  fig, axs = plt.subplots(nrows=2, ncols=2,
                          sharex='all', sharey='row',
                          figsize=(10, 10))

  spectral_lines = {"HI": (1420405751.768,),
                    "OH": (1612.231e6, 1665.402e6, 1667.359e6, 1720.530e6,),
                    "CH": (3263.794e6, 3335.481e6, 3349.193e6,),
                    }
  def plot_spectral_lines(ax):
    for idx, (name, freqs) in enumerate(spectral_lines.items()):
      for line in freqs:
          ax.axvline(line, c='b')

  plot_spectral_lines(axs[0, 0])
  plot_spectral_lines(axs[0, 1])

  axs[0, 0].axvline(receiver.Fc, c='k', ls=':')
  axs[0, 1].axvline(receiver.Fc, c='k', ls=':')

  axs[0, 0].fill_between(f, 10*np.log10(DAT_min[:,0].T), 10*np.log10(DAT_max[:,0].T) , facecolor='r', alpha=0.5)
  axs[0, 1].fill_between(f, 10*np.log10(DAT_min[:,1].T), 10*np.log10(DAT_max[:,1].T) , facecolor='r', alpha=0.5)
  axs[0, 0].plot(f, 10*np.log10(DAT_mean[:,0].T),'k')
  axs[0, 1].plot(f, 10*np.log10(DAT_mean[:,1].T),'k')
  axs[0, 1].set_ylim((ymin, ymax))

  img0 = axs[1, 0].imshow(10*np.log10(DATs[:,:,0]),
                   extent=(f[0], f[-1], t0, t1),
                   aspect='auto',
                   vmin=ymin, vmax=ymax,
                   origin='upper',
                   cmap='gray',
                   interpolation='nearest'
                   )
  img1 = axs[1, 1].imshow(10*np.log10(DATs[:,:,1]),
                   extent=(f[0], f[-1], t0, t1),
                   aspect='auto',
                   vmin=ymin, vmax=ymax,
                   origin='upper',
                   cmap='gray',
                   interpolation='nearest'
                   )
  axs[1, 0].yaxis.set_major_formatter(matplotlib.dates.DateFormatter('%H:%M:%S'))                 
  axs[1, 1].yaxis.set_major_formatter(matplotlib.dates.DateFormatter('%H:%M:%S'))                 
  axs[1, 0].yaxis_date()
  axs[1, 1].yaxis_date()
  ticks = (f[0], f[Nfft/4], f[Nfft/2],  f[3*Nfft/4], f[-1])
  for (name, lines) in spectral_lines.items():
    for line in lines:
      if f[0] < line < f[-1]:
        ticks = ticks + (line, )
  ticks = list(ticks)
  ticks.sort()
  axs[1, 1].set_xticks(ticks)
  axs[1, 0].set_xlabel('Freq (Hz)')
  axs[1, 1].set_xlabel('Freq (Hz)')
  fig.suptitle(str(receiver) + "\nBW=%6.2f MHz" % (BW*1e-6))

  def update_clim(ax):
      f_start, P_min, BW, dP = ax.viewLim.bounds
      img0.set_clim(vmin = P_min, vmax = P_min+dP)
      img1.set_clim(vmin = P_min, vmax = P_min+dP)
      
  axs[0, 0].callbacks.connect('ylim_changed', update_clim)
  axs[0, 1].callbacks.connect('ylim_changed', update_clim)
  update_clim(axs[0, 0])
  update_clim(axs[0, 1])


  plt.tight_layout()

plt.show(block=False)

1/0






print('Started!!!')
time.sleep(1)
mydesign.monitor()
time.sleep(1)
mydesign.monitor()


mydesign.monitor()

# after dummy frame, allow outputing data and starting framer 
mydesign.SEFRAM.enable()

mydesign.SEFRAM.time = "now"  # set time to current UNIX timestamp
print(mydesign.SEFRAM.time)


time.sleep(1)
mydesign.monitor()
time.sleep(1)
mydesign.monitor()
time.sleep(1)
mydesign.monitor()
time.sleep(1)


plt.show()