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
# Configure and run SEFRAM running on ROACH2 for NRT
################################################################################


import time
import struct


# https://stackoverflow.com/questions/5619685/conversion-from-ip-string-to-integer-and-backward-in-python
import socket

def ip2int(addr):
    return struct.unpack("!I", socket.inet_aton(addr))[0]

def int2ip(addr):
    return socket.inet_ntoa(struct.pack("!I", addr))
##########



class sefram(object):
  def __init__(self, fpga=None, Fe=None, vacc_n_framer_basename='frmr_', channelizer_basename='SEFRAM_', network_basename='OneGbE_'):
    assert fpga is not None
    self.fpga = fpga
    self.vacc_n_framer_basename = vacc_n_framer_basename
    self.packetizer_basename = 'pck_'
    self.channelizer_basename = channelizer_basename
    self.network_basename = network_basename
    self.Fe = int(Fe)
    self.F_valon = self.Fe / 2
    self.Fsys = self.F_valon / 8
    self.ID = 0xcece
    self.Nfft = 2**11

  def __str__(self):
    return "SEFRAM __str__"

  def __repr__(self):
    return "sefram(fpga=%s, Fe=%d, vacc_n_framer_basename=\'%s\', channelizer_basename=\'%s\', network_basename=\'%s\')" % (
            str(self.fpga),
            self.Fe,
            self.vacc_n_framer_basename,
            self.channelizer_basename,
            self.network_basename,
            )
            
  @property
  def acc_len(self):
    return self.fpga.read_uint(self.vacc_n_framer_basename+'acc_len')

  @acc_len.setter 
  def acc_len(self, value): 
    if (value < 0) : 
      raise ValueError("acc_len can't be negative") 
    self.fpga.write_int(self.vacc_n_framer_basename+'acc_len', value)

  @property
  def Fe(self):
    return self.fpga.read_uint(self.vacc_n_framer_basename + self.packetizer_basename + 'ADC_freq')

  @Fe.setter 
  def Fe(self, value):
    assert type(value) is int
    self.fpga.write_int(self.vacc_n_framer_basename + self.packetizer_basename + 'ADC_freq', value, blindwrite=True)

  @property
  def ID(self):
    return self.fpga.read_uint(self.vacc_n_framer_basename + self.packetizer_basename + 'framer_id')

  @ID.setter 
  def ID(self, value):
    self.fpga.write_int(self.vacc_n_framer_basename + self.packetizer_basename + 'framer_id', value)


  @property
  def acc_cnt(self):
    return self.fpga.read_uint(self.vacc_n_framer_basename+'acc_cnt')

  @property
  def fft_shift(self):
    self._fft_shift = self.fpga.read_uint(self.channelizer_basename+'fft_shift')
    return self._fft_shift

  @fft_shift.setter 
  def fft_shift(self, value):
    self._fft_shift = value
    self.fpga.write_int(self.channelizer_basename+'fft_shift', self._fft_shift)

  @property
  def fft_gain(self):
    return 2**(bin(self._fft_shift)[2:].count('1'))

  @property
  def dst_addr(self):
    """
    Read IP/UDP_port from FPGA, convert and return ("xxx.xxx.xxx.xxx", UDP_port)
    """
    ip = self.fpga.read_uint(self.network_basename+'tx_ip')
    port = self.fpga.read_uint(self.network_basename+'tx_port')
    ip = int2ip(ip)
    return (ip, port)
    
  @dst_addr.setter 
  def dst_addr(self, value):
    """
    Configure destination serveur IP/UDP
    value = ("IP_adress_xxx.xxx.xxx.xxx_as_string", UDP_port)
    """
    ip, port = value
    ip = ip2int(ip)
    self.fpga.write_int(self.network_basename+'tx_ip', ip, blindwrite=True)
    self.fpga.write_int(self.network_basename+'tx_port', port)

  def disable(self):
    self.fpga.write_int(self.network_basename+'rst', 1)
    self.fpga.write_int(self.vacc_n_framer_basename+'rst', 1)
    self.fpga.write_int(self.vacc_n_framer_basename+'en', 0)

  def arm(self):   # à renomer
    self.fpga.write_int(self.network_basename+'rst', 0)
    self.fpga.write_int(self.vacc_n_framer_basename+'rst', 0)

  def enable(self):
    self.fpga.write_int(self.vacc_n_framer_basename+'en', 1)

  @property
  def time(self):
    ts         = self.fpga.read_uint(self.vacc_n_framer_basename + self.packetizer_basename + 'cur_timestamp')
    sample_cnt = self.fpga.read_uint(self.vacc_n_framer_basename + self.packetizer_basename + 'cur_sample_cnt')
    sysfreq    = self.fpga.read_uint(self.vacc_n_framer_basename + self.packetizer_basename + 'cur_sysfreq')
    return ts + float(sample_cnt) / (sysfreq+1)
                   
  @time.setter 
  def time(self, value):
    """
    Set timestamp for framer.
    if time == "now", set timestamp to next int(time.time())
    """
    self.fpga.write_int(self.vacc_n_framer_basename + self.packetizer_basename + 'timestamp_load', 0)
    if value == "now":
      now = time.time()
      timestamp = int(now) + 1
    else:
      timestamp = value
    before_half_second = 0.5 - (now-timestamp)
    if before_half_second < 0:
       before_half_second += 1
    time.sleep(before_half_second)
    self.fpga.write_int(self.vacc_n_framer_basename + self.packetizer_basename + 'timestamp_init', timestamp, blindwrite=True)
    self.fpga.write_int(self.vacc_n_framer_basename + self.packetizer_basename + 'timestamp_load', 1)

  @property
  def IFG(self):
    """
    Set Inter Frame Gap used to send data by framer
    """
    return self.fpga.read_uint(self.vacc_n_framer_basename + self.packetizer_basename + 'IFG')

  @IFG.setter 
  def IFG(self, value):
    self._IFG = value
    self.fpga.write_int(self.vacc_n_framer_basename + self.packetizer_basename + 'IFG', self._IFG)

  def print_datarate(self):
    bytes_per_chunks = 4096+32
    nof_chunks = 16
    time_per_frame = (bytes_per_chunks + self._IFG) * nof_chunks * (1.0/self.Fsys)
    Nspec_per_sec = float(self.Fe) / self.Nfft
    frame_period = self.acc_len / Nspec_per_sec
    print("Average datarate: %f kiB/s" % (1/frame_period * (bytes_per_chunks * nof_chunks) / 1024))
    print("Peak datarate   : %f MiB/s" % ((bytes_per_chunks * nof_chunks) / time_per_frame / 1024**2))
