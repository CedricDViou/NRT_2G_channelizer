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
bitstream = "../bof/adc_receiver_v2/adc_receiver_v2_2024_Apr_03_1713.fpg"
bitstream = "../bof/adc_receiver_v2/adc_receiver_v2_2024_Apr_05_0946.fpg"
bitstream = "../bof/adc_receiver_v2/adc_receiver_v2_2024_Apr_05_1818.fpg"
bitstream = "../bof/adc_receiver_v2/adc_receiver_v2_2024_Oct_28_1027.fpg"
bitstream = "../bof/adc_receiver_v2/adc_receiver_v2_2024_Oct_30_1703.fpg"
bitstream = "../bof/adc_receiver_v2/adc_receiver_v2_2024_Oct_31_1637.fpg"


conf_Valon = True
ADC_DVW_cal = True
ADC_OGP_cal = True
SEFRAM_conf = False

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


    self.monitoring_regs = tuple()
    if SEFRAM_conf:
      self.monitoring_regs += (
        # SEFRAM
        'frmr_pck_cur_timestamp',
        'frmr_pck_cur_sample_cnt',
        'frmr_pck_cur_sysfreq',
        'frmr_acc_cnt',
        'OneGbE_tx_full',
      )
    self.monitoring_regs += (
      # Channelizer
      'sync_cnt',
      'armed_sync_cnt',

      'TenGbE0_tx_cnt',
      'TenGbE0_status', # spead_overflow, tx_afull, tx_overflow
      
      'TenGbE1_tx_cnt',
      'TenGbE1_status', # spead_overflow, tx_afull, tx_overflow

      'TenGbE2_tx_cnt',
      'TenGbE2_status', # spead_overflow, tx_afull, tx_overflow

      'TenGbE3_tx_cnt',
      'TenGbE3_status', # spead_overflow, tx_afull, tx_overflow


    )

    # Add peripherals and submodules
    self.ADCs = (ADC.ADC(fpga=self.fpga, zdok_n=0, Fe=self.Fe, snap_basename='adcsnap'),
                 ADC.ADC(fpga=self.fpga, zdok_n=1, Fe=self.Fe, snap_basename='adcsnap'))

    self.Receivers = [channelizer.receiver(fpga=self.fpga, Fe=self.Fe, decimation=2, receiver_basename="rcvr0_", burster_basename="burster0_", network_basename='TenGbE0_'),
                      channelizer.receiver(fpga=self.fpga, Fe=self.Fe, decimation=2, receiver_basename="rcvr1_", burster_basename="burster1_", network_basename='TenGbE1_'),
                      channelizer.receiver(fpga=self.fpga, Fe=self.Fe, decimation=2, receiver_basename="rcvr2_", burster_basename="burster2_", network_basename='TenGbE2_'),
                      channelizer.receiver(fpga=self.fpga, Fe=self.Fe, decimation=2, receiver_basename="rcvr3_", burster_basename="burster3_", network_basename='TenGbE3_'),
                      ]
    # self.histograms = histogram.histogram(fpga=self.fpga, basename='histogram_')



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
        val = self.fpga.read_uint(reg)
        msg = ''
        if reg.endswith('status'):
          if val & 0x04:
            msg += "spead_overflow! "
          if val & 0x02:
            msg += "tx_afull! "
          if val & 0x01:
            msg += "tx_overflow! "
        print(reg, self.fpga.read_uint(reg), msg)

  def PPS_presents(self, nof_PPS=1):
    for pps in range(nof_PPS):
      prev = self.fpga.read_uint('sync_cnt')
      time.sleep(1)
      curr = self.fpga.read_uint('sync_cnt')
      assert curr-prev == 1, "PPS not detected"
      print(".")
    return True

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

print("PPS?")
if mydesign.PPS_presents(nof_PPS=2):
    print('PPS found!')

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
  ADC.get_snapshot()
  ADC.plot_interleaved_data(ADC_axs)
plt.tight_layout()
plt.show(block=False)

#mydesign.histograms.get_counts()
#mydesign.histograms.plot_counts()

print('Receivers Configuration')
receiver_configs = [
                    #{"Fc":1.415e9, "decimation": 8, "dst_IP": 0xc0a805b4, "dsp_port": 0xce00, },   # local HI
                    #{"Fc":1.415e9, "decimation": 2, "dst_IP": 0xc0a805b5, "dsp_port": 0xce02, },   # local HI
                    #{"Fc":1.385e9, "decimation": 2, "dst_IP": 0xc0a805b4, "dsp_port": 0xce00, },
                    #{"Fc":1.295e9, "decimation": 2, "dst_IP": 0xc0a805b5, "dsp_port": 0xce02, },
                    #{"Fc":0.900e9, "decimation": 2, "dst_IP": 0xc0a805b4, "dsp_port": 0xce00, },
                    #{"Fc":1.800e9, "decimation": 2, "dst_IP": 0xc0a805b5, "dsp_port": 0xce02, },
                    #{"Fc":1.6e9, "decimation": 2, "dst_IP": 0xc0a805b4, "dsp_port": 0xce00, },
                    #{"Fc":1.6e9, "decimation": 8, "dst_IP": 0xc0a805b5, "dsp_port": 0xce02, },
                    {"Fc":1.000e9, "decimation": 8, "dst_IP": 0xc0a805be, "dsp_port": 0xce00, },  # OH
                    {"Fc":1.100e9, "decimation": 8, "dst_IP": 0xc0a805be, "dsp_port": 0xce01, },  # OH
                    {"Fc":1.200e9, "decimation": 8, "dst_IP": 0xc0a805bf, "dsp_port": 0xce02, },  # OH
                    {"Fc":1.300e9, "decimation": 8, "dst_IP": 0xc0a805bf, "dsp_port": 0xce03, },  # OH
                    #{"Fc":1.666e9, "decimation": 8, "dst_IP": 0xc0a805bf, "dsp_port": 0xce00, },  # OH
                    #{"Fc":1.610e9, "decimation": 8, "dst_IP": 0xc0a805be, "dsp_port": 0xce02, },  # OH
                    #{"Fc":1.715e9, "decimation": 8, "dst_IP": 0xc0a805b5, "dsp_port": 0xce02, },  # OH
                    
                    ]

# ungracefully force reset of 10G interfaces
mydesign.monitor()
for receiver, config in zip(mydesign.Receivers, receiver_configs):
  print('Reseting ', receiver.receiver_basename[:-1])
  while receiver.status() != 0:
    receiver.disable()
    receiver.enable()


mydesign.monitor()
for receiver, config in zip(mydesign.Receivers, receiver_configs):
  print("Configure with: ", config)
  receiver.Fc = config["Fc"]
  receiver.decimation = config["decimation"]
  receiver.scale = 7
  receiver.network_config(config["dst_IP"], config["dsp_port"])
  receiver.enable()


print('Wait for half second and arm PPS_trigger')
mydesign.monitor()
mydesign.arm_PPS()
mydesign.monitor()

print('Started!!!')
for itt in range(5):
    time.sleep(1)
    mydesign.monitor()

1/0


receiver = mydesign.Receivers[0]
config = receiver_configs[0]
#for Fc in np.arange(0, 33) * Fe/2/32: 
for Fc in np.arange(32, 65) * Fe/2/32: 
    print(Fc)
    receiver.Fc=Fc
    receiver.network_config(config["dst_IP"], config["dsp_port"])
    time.sleep(10)
receiver.Fc=0
receiver.network_config(config["dst_IP"], config["dsp_port"])


receiver0 = mydesign.Receivers[0]
config = receiver_configs[0]
receiver0.Fc= config["Fc"]
receiver0.scale = 9
receiver0.network_config(config["dst_IP"], config["dsp_port"])

receiver1 = mydesign.Receivers[1]
config = receiver_configs[1]
receiver1.Fc= config["Fc"]
receiver1.scale = 9
receiver1.network_config(config["dst_IP"], config["dsp_port"])



receiver = mydesign.Receivers[0]
if True:
              # snap_name,          decimation, ymin, ymax
  confs = (#(    "dec_out",                   1,  -20,   30),
           ("HBs_HB2_out",                   2,  -20,   30),
           ("HBs_HB1_out",                   4,  -20,   30),
           ("HBs_HB0_out", receiver.decimation,  -20,   30),
           ("rescale_out", receiver.decimation,  -20,   30),
           
           )
  base_BW = receiver.Fe / receiver.NCO_par
  for snap_name, decimation, ymin, ymax in confs:
    print(snap_name, decimation, ymin, ymax)
    
    dats = []
    t0 = datetime.datetime.utcnow()
    Nacc = 10
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
    BW = receiver.Fe / receiver.NCO_par / decimation
    
    if True:
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
      fig.suptitle(str(receiver) + " " + snap_name + "\nBW=%6.2f MHz" % (BW*1e-6))
    
    
    DATs = np.fft.fft(dats, axis=1)
    DATs[DATs == 0] = 0.01
    DATs = np.fft.fftshift(DATs, axes=1)
    DATs = DATs.real**2 + DATs.imag**2
    DAT_min = DATs.min(axis=0)
    DAT_mean = DATs.mean(axis=0)
    DAT_max = DATs.max(axis=0)
    df = np.arange(-Nfft/2, Nfft/2, dtype=float)/Nfft * BW
    f = (receiver.Fc + df)
    
    fig, axs = plt.subplots(nrows=2, ncols=2,
                            sharex='all', sharey='row',
                            figsize=(38.34, 10))

    plt.tight_layout()
    
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
    
    fig.img0 = axs[1, 0].imshow(10*np.log10(DATs[:,:,0]),
                                extent=(f[0], f[-1], t0, t1),
                                aspect='auto',
                                vmin=ymin, vmax=ymax,
                                origin='upper',
                                cmap='gray',
                                interpolation='nearest'
                                )
    fig.img1 = axs[1, 1].imshow(10*np.log10(DATs[:,:,1]),
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
    axs[1, 1].set_xlim((receiver.Fc-base_BW/2, receiver.Fc+base_BW/2))
    axs[1, 0].set_xlabel('Freq (Hz)')
    axs[1, 1].set_xlabel('Freq (Hz)')
    fig.suptitle(str(receiver) + " " + snap_name + "\nBW=%6.2f MHz" % (BW*1e-6))
    
        
    def update_clim(ax):
      f_start, P_min, BW, dP = ax.viewLim.bounds
      ax.figure.img0.set_clim(vmin = P_min, vmax = P_min+dP)
      ax.figure.img1.set_clim(vmin = P_min, vmax = P_min+dP)
    
    axs[0, 0].callbacks.connect('ylim_changed', update_clim)
    axs[0, 1].callbacks.connect('ylim_changed', update_clim)
    update_clim(axs[0, 0])   # force fisrt clim computation
    
plt.show(block=False)





