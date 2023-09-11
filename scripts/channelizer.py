
#!/home/cedric/anaconda3/envs/2point7/bin/python
# -*- coding: utf-8 -*-

################################################################################
#
# Copyright (C) 2022
# Observatoire Radioastronomique de Nancay,
# Observatoire de Paris, PSL Research University, CNRS, Univ. Orleans, OSUC,
# 18330 Nancay, France
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
# Configure Channelizers running on ROACH2 for NRT
#
################################################################################

import time

class galactic_channelizer(object):
  def __init__(self, fpga=None, Fe=None, channelizer_basename='channelizer_', rescale_basename='rescale_', select_basename='select_4f64_', network_basename='TenGbE0_'):
    assert fpga is not None
    assert Fe is not None
    self.fpga = fpga
    self.Fe = int(Fe)
    self.channelizer_basename = channelizer_basename
    self.rescale_basename = rescale_basename
    self.select_basename = select_basename
    self.network_basename = network_basename
    self.MAX_NOF_CHAN = 4

  def __str__(self):
    return "Channelizer for galactic mode -> 4 chans of 28MHz selected and sent from 64 channels available."

  def __repr__(self):
    return "Channelizer(fpga=%s, Fe=%d, channelizer_basename=\'%s\', rescale_basename=\'%s\', select_basename=\'%s\', network_basename=\'%s\')" % (
            str(self.fpga),
            self.Fe,
            self.channelizer_basename,
            self.rescale_basename,
            self.select_basename,
            self.network_basename,
            )
  
  def clear(self):
    print('Reset some counters')
    self.fpga.write_int(self.select_basename+'ctrl', 0)
    self.fpga.write_int('cnt_rst'    , 1)
    self.fpga.write_int(self.network_basename+'rst', 3)
    self.fpga.write_int(self.channelizer_basename+'clear_ovr', 3)
    time.sleep(0.2)
    self.fpga.write_int(self.select_basename+'ctrl', 1)
    self.fpga.write_int('cnt_rst'    , 0)
    self.fpga.write_int(self.network_basename+'rst', 0)
    self.fpga.write_int(self.channelizer_basename+'clear_ovr', 0)
    time.sleep(0.2)

  def network_config(self):
    # configure framer
    #self.fpga.write_int(self.network_basename+'hdr_heap_size'    ,         0)  # optionnal for SPEAD (?), thus could be used for own need
    self.fpga.write_int(self.network_basename+'hdr_ADC_Freq'      ,     int(self.Fe), blindwrite=True)  # So... used to store sampling frequency
    #self.fpga.write_int(self.network_basename+'hdr_heap_offset'  ,         0)  # required by SPEAD, but could be used for own need
    #self.fpga.write_int(self.network_basename+'hdr_heap_offset'  , chan_conf)  # So... driven by select/chan_cfg
    self.fpga.write_int(self.network_basename+'hdr_pkt_len_words',      1024)  # REQUIRED!!!
    # self.fpga.write_int(self.network_basename+'hdr5_0x0005_DIR'  ,         5)  # driven by select/nof_chan
    # self.fpga.write_int(self.network_basename+'hdr6_0x0006_DIR'  ,         6)  # driven by select/samples_per_frames
    self.fpga.write_int(self.network_basename+'hdr7_free'  ,         7) # free (really is 0x0007_DIR)

    # configure 10G
    self.fpga.write_int(self.network_basename+'dst_ip'  , 0xc0a805b4, blindwrite=True)  # 192.168.5.180
    self.fpga.write_int(self.network_basename+'dst_port',     0xdede)


  @property
  def fft_shift(self):
    self._fft_shift = self.fpga.read_uint(self.channelizer_basename+'fft_shift')
    return self._fft_shift

  @fft_shift.setter 
  def fft_shift(self, value):
    self._fft_shift = value
    self.fpga.write_int(self.channelizer_basename+'fft_shift', self._fft_shift)

  @property
  def scale(self):
    self._scale = (self.fpga.read_uint(self.rescale_basename+'pol0_bitselect'),
                   self.fpga.read_uint(self.rescale_basename+'pol1_bitselect'),
                   )
    return self._scale

  @scale.setter 
  def scale(self, value):
    assert len(value) == 2
    self._scale = value
    self.fpga.write_int(self.rescale_basename+'pol0_bitselect', self._scale[0])
    self.fpga.write_int(self.rescale_basename+'pol1_bitselect', self._scale[1])

  @property
  def channels(self):
    return self._channels

  @channels.setter 
  def channels(self, value):
    if type(value) == int:
      self._channels = (value, )
    elif  type(value) in (tuple, list):
      assert len(value) <= self.MAX_NOF_CHAN
      self._channels = value
    
    self.fpga.write_int(self.select_basename+'nof_channels', len(self._channels))
    for idx, chan in enumerate(self._channels):
        self.fpga.write_int(self.select_basename+'chan%d_sel' % idx, chan)



class pulsar_channelizer(object):
  def __init__(self, fpga=None, Fe=None, channelizer_basename='channelizer_', rescale_basename='rescale_'):
    assert fpga is not None
    assert Fe is not None
    self.fpga = fpga
    self.Fe = int(Fe)
    self.channelizer_basename = channelizer_basename
    self.rescale_basename = rescale_basename

  def __str__(self):
    return "Channelizer for pulsar mode -> 1024 chans reordered and sent"

  def __repr__(self):
    return "Channelizer(fpga=%s, Fe=%d, channelizer_basename=\'%s\', rescale_basename=\'%s\', network_basename=\'%s\')" % (
            str(self.fpga),
            self.Fe,
            self.channelizer_basename,
            self.rescale_basename,
            )
  
  def disable(self):
    print('Reset some counters')
    self.fpga.write_int('TenGbE_rst', 0xFF)

  def enable(self):
    self.fpga.write_int('TenGbE_rst', 0x00)
    self.fpga.write_int('channelizer_arm', 1)
    self.fpga.write_int('channelizer_arm', 0)


  def force_eof(self):
    self.fpga.write_int('TenGbE_force_eof', 1)
    self.fpga.write_int('TenGbE_force_eof', 0)


  def network_config(self):
    print('Config SPEAD packets')
    #self.fpga.write_int('hdr_heap_size'    ,         0)  # optionnal for SPEAD (?), thus could be used for own need
    self.fpga.write_int('hdr_ADC_Freq'      ,     int(self.Fe), blindwrite=True)  # So... used to store sampling frequency
    self.fpga.write_int('hdr_heap_offset'  ,         0)  # required by SPEAD, but could be used for own need
    #self.fpga.write_int('hdr_pkt_len_words',      1024)  # REQUIRED!!!
    self.fpga.write_int('hdr_len_w',              1024)  # REQUIRED!!!
    self.fpga.write_int('hdr5'             ,         5)  # driven by select/nof_chan
    self.fpga.write_int('hdr6'             ,         6)  # driven by select/samples_per_frames
    self.fpga.write_int('hdr7_free'        ,         7) # free (really is 0x0007_DIR)

    print('Config destination IP addresses')
    IPs = (
      0xc0a805b4, # 192.168.5.180
      0xc0a805b5, # 192.168.5.181
      0xc0a805b6, # 192.168.5.182
      0xc0a805b7, # 192.168.5.183
      0xc0a805b8, # 192.168.5.184
      0xc0a805b9, # 192.168.5.185
      0xc0a805ba, # 192.168.5.186
      0xc0a805bb, # 192.168.5.187
    )
    assert len(IPs) == 8
    for net_if, IP in enumerate(IPs):
      self.fpga.write_int('TGbE_dst_ip' + str(net_if) , IP, blindwrite=True)

    print('Config destination UDP ports (same set of 8 ports for all IPs)')
    # No dupplicates
    # write 0's on unused ones (will be used to reset round robin later on)
    ports = (
      2000,
      2001,
      2002,
      2003,
      2004,
      2005,
      2006,
      2007,
    )
    ports = (
      2000,
      2000,
      2000,
      2000,
      2000,
      2000,
      2000,
      2000,
    )
    assert len(ports) == 8
    for port_idx, port in enumerate(ports):
      self.fpga.write_int('TGbEs_dst_port_wr' , 0)           # release latch
      self.fpga.write_int('TGbEs_dst_port_cfg', port)        # set port to configure
      self.fpga.write_int('TGbEs_dst_port_wr' , 1<<port_idx) # latch appropriate reg
    self.fpga.write_int('TGbEs_dst_port_wr' , 0)             # release latch when done
  
  @property
  def scale(self):
    self._scale = self.fpga.read_uint(self.rescale_basename+'shift')
    return self._scale
  
  @scale.setter 
  def scale(self, value):
    self._scale = value
    self.fpga.write_int(self.rescale_basename+'shift', self._scale)
