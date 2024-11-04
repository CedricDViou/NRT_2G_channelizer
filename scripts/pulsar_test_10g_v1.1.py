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
bitstream = "../bof/pulsar_test_10g_v1/bit_files/pulsar_test_10g_v1_2022_Nov_15_1414.fpg"

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

    # Configure 10G network
    # stop everything before configuration
    self.fpga.write_int('TenGbE_rst', 0xff)
    self.fpga.write_int('sim_enable', 0x00)

    # round robin over 8 different ports
    TenGbE_ports = (10000,
                    10000,
                    10000,
                    10000,
                    10000,
                    10000,
                    10000,
                    10000,
                    )
    for reg, port in enumerate(TenGbE_ports):
        self.fpga.write_int('TGbEs_dst_port_cfg' , port)
        self.fpga.write_int('TGbEs_dst_port_wr'  , 1<<reg)
        self.fpga.write_int('TGbEs_dst_port_wr'  , 0)
        

    # fixed IP
    self.fpga.write_int('TGbE_dst_ip0'   , 0xc0a805b4, blindwrite=True)   # 192.168.5.180
    self.fpga.write_int('TGbE_dst_ip1'   , 0xc0a805b5, blindwrite=True)   # 192.168.5.181
    self.fpga.write_int('TGbE_dst_ip2'   , 0xc0a805b6, blindwrite=True)   # 192.168.5.182
    self.fpga.write_int('TGbE_dst_ip3'   , 0xc0a805b7, blindwrite=True)   # 192.168.5.183
    self.fpga.write_int('TGbE_dst_ip4'   , 0xc0a805b8, blindwrite=True)   # 192.168.5.184
    self.fpga.write_int('TGbE_dst_ip6'   , 0xc0a805b9, blindwrite=True)   # 192.168.5.185
    self.fpga.write_int('TGbE_dst_ip7'   , 0xc0a805ba, blindwrite=True)   # 192.168.5.186
    self.fpga.write_int('TGbE_dst_ip5'   , 0xc0a805bb, blindwrite=True)   # 192.168.5.187


    # MAC table
    # 192.168.5.180-183  9c63c0f82f6e
    # 192.168.5.184-187  9c63c0f82f6f
    # 192.168.5.190      b0262849fcc0
    # 192.168.5.191      b0262849fcc1
    
    
    macs = [0x00ffffffffffff, ] * 256
    macs[180] = 0x9c63c0f82f6e
    macs[181] = 0x9c63c0f82f6e
    macs[182] = 0x9c63c0f82f6e
    macs[183] = 0x9c63c0f82f6e
    macs[184] = 0x9c63c0f82f6f
    macs[185] = 0x9c63c0f82f6f
    macs[186] = 0x9c63c0f82f6f
    macs[187] = 0x9c63c0f82f6f

    macs[190] = 0xb0262849fcc0
    macs[191] = 0xb0262849fcc1
   
    
    #gbe.set_arp_table(macs) # will fail
    macs_pack = struct.pack('>%dQ' % (len(macs)), *macs)
    for gbe in self.fpga.gbes:
        self.fpga.blindwrite(gbe.name, macs_pack, offset=0x3000)
    
    #for gbe in self.fpga.gbes:
    #    print(gbe.get_arp_details()[170:190])


    pkt_len=1024  # as 64-bit words, as 8-byte words
    T_1s = self.Fe/16
    nof_pkt_per_s = 1
    nof_pkt_per_s = 112915  # packets that fit 16 samples from 128 sb of a 2048-sample FFT fed by a 3.7 GS/s ADC
    pkt_period = T_1s // nof_pkt_per_s
    print(pkt_period)
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

  def force_eof(self):
    self.fpga.write_int('TenGbE_force_eof', 1)
    self.fpga.write_int('TenGbE_force_eof', 0)

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

Nfft = 4096
nof_lanes = 8
mydesign.feed = FEED


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



print('Wait for half second and arm PPS_trigger')
#mydesign.cnt_rst()
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
    mydesign.fpga.write_int('sim_enable', 0x00)
    mydesign.force_eof()
    mydesign.fpga.write_int('TenGbE_rst', 0xff)
    #mydesign.cnt_rst()
    mydesign.monitor()
    time.sleep(0.5)
    mydesign.fpga.write_int('TenGbE_rst', 0x00)
    time.sleep(0.5)
    mydesign.fpga.write_int('sim_enable', 0xff)
    mydesign.monitor()
    time.sleep(1)
    mydesign.monitor()





mydesign.monitor()

plt.show()


