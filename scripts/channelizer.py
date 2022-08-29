
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
# Configure Channelizer running on ROACH2 for NRT
################################################################################

import time

class Channelizer(object):
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


  def debug_params(self):
    # switch buses for constants to help debug
    # 0b00 : ADC input
    # 0b01 : 0's
    # 0b10 : "other" ADC input
    # 0b11 : 64, 0 (15 times), 64, 0 , ....
    self.fpga.write_int('set_fft_input', 0b0000)
    #self.fpga.write_int('set_fft_input', 0b0001)
    #self.fpga.write_int('set_fft_input', 0b0100)
    #self.fpga.write_int('set_fft_input', 0b1010)
    
    self.fpga.write_int(self.channelizer_basename+'set_out_zeros', 0b0000)
    #self.fpga.write_int(self.channelizer_basename+'set_out_zeros', 0b0001)
    #self.fpga.write_int(self.channelizer_basename+'set_out_zeros', 0b0101)
    #self.fpga.write_int(self.channelizer_basename+'set_out_zeros', 0b0100)
    #self.fpga.write_int(self.channelizer_basename+'set_out_zeros', 0b1010)
    #self.fpga.write_int(self.channelizer_basename+'set_out_zeros', 0b1000)
    #self.fpga.write_int(self.channelizer_basename+'set_out_zeros', 0b0010)


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
    self.fpga.write_int(self.network_basename+'dst_port',     0xcece)


  def arm(self):
    print('Wait for half second and arm PPS_trigger')
    self.fpga.write_int('reg_arm', 0)

    now = time.time()
    before_half_second = 0.5 - (now-int(now))
    if before_half_second < 0:
        before_half_second += 1
    time.sleep(before_half_second)

    self.fpga.write_int('reg_arm', 1)


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


