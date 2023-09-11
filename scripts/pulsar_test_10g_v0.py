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
# Configure and run design pulsar_test_10g_v0
# 8x Simple ramp generator, framer and 10G interface
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

ADC_clock = imp.reload(ADC_clock)
ADC = imp.reload(ADC)


roach2 = "192.168.40.71"
bitstream = "../bof/pulsar_test_10g_v0/bit_files/pulsar_test_10g_v0_2022_Nov_14_0933.fpg"

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
class test_10g(object):
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
        'sync_cnt',
        'armed_sync_cnt',
        'TGbE_tx_cnt0',
        'TGbE_tx_cnt1',
        'TGbE_tx_cnt2',
        'TGbE_tx_cnt3',
        'TGbE_tx_cnt4',
        'TGbE_tx_cnt5',
        'TGbE_tx_cnt6',
        'TGbE_tx_cnt7',
        'TGbE_tx_ovr0',
        'TGbE_tx_ovr1',
        'TGbE_tx_ovr2',
        'TGbE_tx_ovr3',
        'TGbE_tx_ovr4',
        'TGbE_tx_ovr5',
        'TGbE_tx_ovr6',
        'TGbE_tx_ovr7',
           
                   )

    # Add peripherals and submodules
    self.ADCs = (ADC.ADC(fpga=self.fpga, zdok_n=0, Fe=self.Fe, snap_basename='adcsnap'),
                 ADC.ADC(fpga=self.fpga, zdok_n=1, Fe=self.Fe, snap_basename='adcsnap'))

    # init modules
    self.fpga.write_int('TenGbE_rst', 0xff)

    self.fpga.write_int('TGbE_dst_ip0'   , 0xc0a805b4, blindwrite=True)   # 192.168.5.180
    self.fpga.write_int('TGbE_dst_ip1'   , 0xc0a805b5, blindwrite=True)   # 192.168.5.181
    self.fpga.write_int('TGbE_dst_ip2'   , 0xc0a805b6, blindwrite=True)   # 192.168.5.182
    self.fpga.write_int('TGbE_dst_ip3'   , 0xc0a805b7, blindwrite=True)   # 192.168.5.183
    self.fpga.write_int('TGbE_dst_ip4'   , 0xc0a805b8, blindwrite=True)   # 192.168.5.184
    self.fpga.write_int('TGbE_dst_ip6'   , 0xc0a805ba, blindwrite=True)   # 192.168.5.186
    self.fpga.write_int('TGbE_dst_ip7'   , 0xc0a805bb, blindwrite=True)   # 192.168.5.187
    self.fpga.write_int('TGbE_dst_ip5'   , 0xc0a805b9, blindwrite=True)   # 192.168.5.185

    self.fpga.write_int('TGbE_dst_port0' , 10000)
    self.fpga.write_int('TGbE_dst_port1' , 10001)
    self.fpga.write_int('TGbE_dst_port2' , 10002)
    self.fpga.write_int('TGbE_dst_port3' , 10003)
    self.fpga.write_int('TGbE_dst_port4' , 10004)
    self.fpga.write_int('TGbE_dst_port5' , 10005)
    self.fpga.write_int('TGbE_dst_port6' , 10006)
    self.fpga.write_int('TGbE_dst_port7' , 10007)


    pkt_len=1024
    T_1s = self.Fe/16
    nof_pkt_per_s = 5
    pkt_period = T_1s // nof_pkt_per_s
    self.fpga.write_int('sim_enable',      0)
    self.fpga.write_int('sim_payload_len', pkt_len)
    self.fpga.write_int('sim_period'     , pkt_period)

    #                                               # header 1 : hdr_head_id: packet counter generated in HW
    self.fpga.write_int('hdr_ADC_Freq',   0xcc02)  # header 2
    self.fpga.write_int('hdr_heapoffset', 0xcc03)  # header 3
    self.fpga.write_int('hdr_len_w',      pkt_len)  # header 4 : MUST be packet payload len
    self.fpga.write_int('hdr5',           0xcc05)  # header 5
    self.fpga.write_int('hdr6',           0xcc06)  # header 6
    self.fpga.write_int('hdr7_free',      0xcc07)  # header 7




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
    for ADC in self.ADCs:
      ADC.adcmode=adcmode[self._feed]
      ADC.adcmode=adcmode[self._feed]


mydesign = test_10g(
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
  [ ADC.get_snapshot(count=1000) for ADC in mydesign.ADCs ]
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



print('Wait for half second and arm PPS_trigger')
mydesign.cnt_rst()
mydesign.arm_PPS()
mydesign.fpga.write_int('TenGbE_rst', 0x00)
mydesign.fpga.write_int('sim_enable', 0xff)
mydesign.monitor()




print('Started!!!')
time.sleep(1)
mydesign.monitor()
time.sleep(1)
mydesign.monitor()


if False:
    mydesign.fpga.write_int('TenGbE_rst', 0xff)
    mydesign.fpga.write_int('sim_enable', 0x00)
    mydesign.cnt_rst()


mydesign.monitor()

plt.show()



