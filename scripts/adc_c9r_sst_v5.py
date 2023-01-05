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


import time
import numpy as np
import struct
import sys
import logging
import pylab
import matplotlib.pyplot as plt
import signal
import imp

import casperfpga
import ADC_clock
import ADC
import sefram
import channelizer

ADC_clock = imp.reload(ADC_clock)
ADC = imp.reload(ADC)
sefram = imp.reload(sefram)
channelizer = imp.reload(channelizer)


roach2 = "192.168.40.71"
bitstream = "../bof/adc_c9r_sst_v5/bit_files/adc_c9r_sst_v5_2022_Oct_12_1619.fpg"

conf_Valon = True
ADC_DVW_cal = True
ADC_OGP_cal = True

Fe = 3580000000.0 # Hz
F_valon = Fe / 2
Fsys = F_valon / 8
Fin = 130000000# Hz


Valon = ADC_clock.ADC_clock()
if conf_Valon:
  Valon.set_config(FA=F_valon/1e6,
                   PA=-4,
                   FB=Fin/1e6,
                   PB=-4,
                   )
Valon.print_config()


lh = logging.StreamHandler()
logger = logging.getLogger(roach2)
logger.addHandler(lh)
logger.setLevel(10)



# make class to control CASPER FPGA design for NRT channelizer
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
                   'select_4f64_nof_channels',
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

    # Add peripherals and submodules
    self.ADCs = (ADC.ADC(fpga=self.fpga, zdok_n=0, Fe=self.Fe, snap_basename='adcsnap'),
                 ADC.ADC(fpga=self.fpga, zdok_n=1, Fe=self.Fe, snap_basename='adcsnap'))
    self.SEFRAM = sefram.sefram(fpga=self.fpga, Fe=self.Fe)
    self.Channelizer = channelizer.channelizer(fpga=self.fpga, Fe=self.Fe)

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


mydesign = NRT_channelizer(
  roach2,
  bitstream=bitstream,
  Fe=Fe
  )

dev = mydesign.listdev()
for d in dev:
    print(d)
print()


if ADC_DVW_cal:
  print('Calibrating ADCs')
  [ ADC.run_DVW_calibration() for ADC in mydesign.ADCs ]
  [ ADC.print_DVW_calibration() for ADC in mydesign.ADCs ]
  print('Done')


if False:
  [ ADC.get_snapshot(count=100) for ADC in mydesign.ADCs ]
  [ ADC.dump_snapshot() for ADC in mydesign.ADCs ]



Nfft = 4096

[ ADC.get_snapshot() for ADC in mydesign.ADCs ]
fig, axs = plt.subplots(nrows = len(mydesign.ADCs), 
                        ncols = 3,
                        sharex='col', sharey='col',
                        )

for ADC_axs, ADC in zip(axs, mydesign.ADCs):
  ADC_wave = ADC.wave.copy()

  Nech_to_plot = 16384
  ADC_axs[0].plot(np.arange(Nech_to_plot) / Fe * 1e6,
                  ADC_wave[:Nech_to_plot],
                  label=ADC.name)

  cnt, bins, _ = ADC_axs[1].hist(ADC.wave, bins=np.arange(-128, 129) - 0.5)

  nof_samples = len(ADC_wave)
  f = np.arange(Nfft/2+1, dtype='float') / Nfft * Fe /1e6 
  w = np.blackman(Nfft)
  ADC_wave.shape = ((-1, Nfft))
  DATA = np.fft.rfft(w * ADC_wave, axis=-1)
  DATA = DATA.real**2 + DATA.imag**2
  DATA = DATA.mean(axis=0)
  ADC_axs[2].plot(f,
                  10*np.log10(DATA),
                  label=ADC.name)

ADC_axs[0].set_xlabel(u"Time (us)")
ADC_axs[0].set_xlim((0, (Nech_to_plot-1) / Fe * 1e6))
ADC_axs[1].set_xlabel("ADC code")
ADC_axs[1].set_xlim(bins[[0, -1]])
ADC_axs[2].set_xlabel("Frequency (MHz)")
ADC_axs[2].set_xlim((0, f[-1]))

[ ADC_axs[0].set_ylabel("ADC code\nin [-128, 128[") for ADC_axs in axs ]
[ ADC_axs[1].set_ylabel("Counts") for ADC_axs in axs ]
[ ADC_axs[2].set_ylabel("Power (dB)") for ADC_axs in axs ]

plt.tight_layout()
plt.show(block=False)


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



print('Channelizer Configuration')

mydesign.Channelizer.network_config()
mydesign.Channelizer.clear()

# configure FFT
#fft_shift = 0b000000
#fft_shift = 0b111111
fft_shift = 0b010111
mydesign.Channelizer.fft_shift = fft_shift


# configure rescaler
# Selects which 8 bits from 18 are outputted.
# 0 is lowest 8-bits: bits 0-7 (inclusive)
# 1: bits 4-11
# 2: bits 8-15
# 3 is highest 8-bits: bits 10-17
scale = 2
mydesign.Channelizer.scale = (scale, scale)


# configure channel_selector
#mydesign.Channelizer.channels = (0, 1, 2, 3)
mydesign.Channelizer.channels = 51   # HI line from galaxy should be there




print('Wait for half second and arm PPS_trigger')
mydesign.arm_PPS()
mydesign.monitor()

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



