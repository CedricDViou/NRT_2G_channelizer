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
# Interact with ADC OGP parameters and show results on ADC data

################################################################################


import casperfpga
import time
import numpy as np
import struct
import sys
import logging
import pylab
import matplotlib.pyplot as plt
import signal
import imp


import ADC_clock
import ADC

ADC_clock = imp.reload(ADC_clock)
ADC = imp.reload(ADC)

roach2 = "192.168.40.71"
bitstream = "../bof/adc_receiver_v1/adc_receiver_v1_2024_Feb_03_1855.fpg"
conf_Valon = True
ADC_cal = False

#FEED, Fe = 'HF', 3200000000.0 # 1.6-3.2  GHz
FEED, Fe = 'BF', 3700000000.0 #   0-1.85 GHz
F_valon = Fe / 2
Fsys = F_valon / 8
Fin = 130000000# Hz

if conf_Valon:
  Valon = ADC_clock.ADC_clock()
  Valon.set_config(FA=F_valon/1e6,
                   PA=5, # -4, -1, 2, 5
                   FB=Fin/1e6,
                   PB=-4,
                   )
  Valon.print_config()


lh = logging.StreamHandler()
logger = logging.getLogger(roach2)
logger.addHandler(lh)
logger.setLevel(10)


# class to control CASPER FPGA design
class adc_calibrator(object):
  def __init__(self, name, bitstream=None, Fe=None, feed='BF'):
    self.name = name
    self.fpga = casperfpga.CasperFpga(self.name)
    time.sleep(0.2)
    self.Fe = Fe
    self.F_valon = self.Fe / 2
    self.Fsys = self.F_valon / 8
    self._feed = feed

    assert self.fpga.is_connected(), 'ERROR connecting to server %s.\n' % (self.name)
    if bitstream is not None:
      print('------------------------')
      print('Programming FPGA with %s...' % bitstream)
      sys.stdout.flush()
      self.fpga.upload_to_ram_and_program(bitstream)
      print('done')

    self.monitoring_regs = (
                   'frmr_pcktizer_cur_timestamp',
                   'frmr_pcktizer_cur_smpl_cnt',
                   'frmr_pcktizer_cur_smpl_per_sec',
                   'frmr_acc_cnt',
                   )
    # Add peripherals and submodules
    self.ADCs = (ADC.ADC(fpga=self.fpga, zdok_n=0, Fe=self.Fe, snap_basename='adcsnap'),
                 ADC.ADC(fpga=self.fpga, zdok_n=1, Fe=self.Fe, snap_basename='adcsnap'))

    # init modules


  def cnt_rst(self):
    self.fpga.write_int('cnt_rst', 1)
    self.fpga.write_int('cnt_rst', 0)

  def arm_PPS(self):
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
    NY_Zone = {'BF': 1,
               'HF': 2,
               }
    for ADC in self.ADCs:
      ADC.adcmode = adcmode[value]
      ADC.NY_Zone = NY_Zone[value]



mydesign = adc_calibrator(roach2, bitstream=bitstream, Fe=Fe)


dev = mydesign.listdev()
for d in dev:
    print(d)
print()


if ADC_cal:
  print('Calibrating ADCs')
  [ ADC.run_DVW_calibration() for ADC in mydesign.ADCs ]
  [ ADC.print_DVW_calibration() for ADC in mydesign.ADCs ]
  print('Done')


mydesign.feed = FEED



import ADC
ADC = imp.reload(ADC)
myADC0 = ADC.ADC(fpga=mydesign.fpga, zdok_n=0, Fe=mydesign.Fe, snap_basename='adcsnap')
myADC0.NY_Zone = 2
myADC0.create_calibration_GUI()
myADC1 = ADC.ADC(fpga=mydesign.fpga, zdok_n=1, Fe=mydesign.Fe, snap_basename='adcsnap')
myADC1.create_calibration_GUI()
self = myADC0

1/0

fig, axs = plt.subplots(nrows = len(mydesign.ADCs), 
                        ncols = 3, # wave, histogram, spectrum
                        sharex='col', sharey='col',
                        )
for ADC_axs, ADC in zip(axs, mydesign.ADCs):
  ADC.get_snapshot()
  ADC.plot_interleaved_data(ADC_axs)
plt.tight_layout()
plt.show(block=False)

