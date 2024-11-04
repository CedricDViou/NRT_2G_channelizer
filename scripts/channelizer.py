
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
import struct
import numpy as np

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
    # reset reorder
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



class receiver(object):
  def __init__(self, fpga=None, Fe=None, decimation=None, receiver_basename='receiver_', NCO_basename='L0_%d_mem', HB_basename='HB_', burster_basename="burster_", network_basename='TenGbE0_'):
    assert fpga is not None
    assert Fe is not None
    assert decimation is not None
    self.fpga = fpga
    self.Fe = int(Fe)
    self.receiver_basename = receiver_basename
    self.scale_basename = self.receiver_basename+'bitselect'
    self.NCO_basename = self.receiver_basename + NCO_basename
    self.HB_basename = self.receiver_basename + HB_basename
    self.burster_basename = burster_basename
    self.network_basename = network_basename
    self._kc = 0
    self.K = 1024     # NCO kc can be configured from 0 to K-1
    self.NCO_par = 16 # NCO processes 16 samples in //
    self.NCO_tables = None
    self.decimation = decimation  # receiver1_HBs_true


  def __str__(self):
    return "Receiver -> Fc=%f" % (self.Fc)


  def __repr__(self):
    return "Receiver(fpga=%s, Fe=%d, receiver_basename=\'%s\', NCO_basename=\'%s\', HB_basename=\'%s\', burster_basename=\'%s\', network_basename=\'%s\')" % (
            str(self.fpga),
            self.Fe,
            self.receiver_basename,
            self.NCO_basename,
            self.HB_basename,
            self.burster_basename,
            self.network_basename,
            )


  def disable(self):
    self.fpga.write_int(self.network_basename + 'rst', 3)
    self.fpga.write_int(self.burster_basename + 'rst', 1)
    self.fpga.write_int(self.receiver_basename + 'rst', 1)


  def enable(self):
    self.fpga.write_int(self.receiver_basename + 'rst', 0)
    self.fpga.write_int(self.burster_basename + 'rst', 0)
    self.fpga.write_int(self.network_basename + 'rst', 0)

  def status(self):
    return self.fpga.read_uint(self.network_basename + 'status')

  def force_eof(self):
    self.fpga.write_int('TenGbE_force_eof', 1)
    self.fpga.write_int('TenGbE_force_eof', 0)

  def network_config(self, dst_ip, dst_port):
    print('Write MAC table')
    # MAC table
    # 192.168.5.180-183  9c63c0f82f6e (CARRI)
    # 192.168.5.184-187  9c63c0f82f6f (CARRI)
    # 192.168.5.190      b0262849fcc0 (Renard)
    # 192.168.5.191      b0262849fcc1 (Renard)
    
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


    print('Config SPEAD packets')
    self.fpga.write_int(self.network_basename + 'hdr_ADC_Freq'      ,     int(self.Fe/1e6), blindwrite=True)  # So... used to store sampling frequency
    self.fpga.write_int(self.network_basename + 'hdr_kc'            , self.kc)
    self.fpga.write_int(self.network_basename + 'hdr_pkt_len_words' , 1024)
    self.fpga.write_int(self.network_basename + 'hdr_decimation'    , self.decimation)
    self.fpga.write_int(self.network_basename + 'hdr_nof_spf'       , 2048)
    self.fpga.write_int(self.network_basename + 'hdr7_free'         , 6)

    print('Config IP/UDP')
    self.fpga.write_int(self.network_basename + 'dst_ip', dst_ip, blindwrite=True)
    self.fpga.write_int(self.network_basename + 'dst_port', dst_port)


  @property
  def scale(self):
    self._scale = self.fpga.read_uint(self.scale_basename)
    return self._scale

  @scale.setter 
  def scale(self, value):
    self._scale = value
    self.fpga.write_int(self.scale_basename, self._scale)

  def NCO_calc_tables(self):
    NCO_w = 16
    NCO_dp = 15
    Max_NCO_val = 2**(NCO_dp)-1
    ReIm = 2
    L0_mem = np.exp(2j*np.pi*(-self.kc) * np.arange(self.K * self.NCO_par) / self.K)
    L0_mem = L0_mem.reshape((self.K, self.NCO_par))
    L0_mem_ReIm = L0_mem.view(np.float64).reshape((self.K, self.NCO_par, ReIm))
    L0_mem_ReIm_int = np.round(L0_mem_ReIm * Max_NCO_val)
    L0_mem_ReIm_int16 = L0_mem_ReIm_int.astype(np.int16)
    self.NCO_tables = L0_mem_ReIm_int16.transpose((1,0,2)).copy()

  def NCO_write_tables(self):
    L0_mem_uint32 = self.NCO_tables.view(np.uint16).byteswap()  # byte swap 16-bit data
    if self.NCO_tables is not None:
      for table_idx, table_content in enumerate(L0_mem_uint32):
        bin_content = table_content.tobytes()
        self.fpga.blindwrite(self.NCO_basename % table_idx, bin_content)
    #raise Exception('NOT TESTED')

  def NCO_read_tables(self):
    self.NCO_tables = np.empty((self.NCO_par, self.K, 2), dtype=np.int16)
    for table_idx in range(self.NCO_par):
        bin_content = self.fpga.read(self.NCO_basename % table_idx, self.K * 4, 0, unsigned=False)
        table_content = np.frombuffer(bin_content, dtype=np.int16).byteswap()  # byte swap 16-bit data
        table_content = table_content.reshape((self.K, 2))
        self.NCO_tables[table_idx] = table_content
    #raise Exception('NOT TESTED')

  def test_L0_i_mem(self, dat_in, mem_idx=0, nof_read = 10):
    # Write
    self.fpga.blindwrite(self.NCO_basename % mem_idx, dat_in.tobytes())
    # reads
    dat_outs = []
    nof_word = len(dat_in)
    for read_idx in range(nof_read):
      dat_out = self.fpga.read(self.NCO_basename % mem_idx, nof_word, 0, unsigned=True)
      dat_out = np.frombuffer(dat_out, dtype=np.int8)
      dat_outs.append(dat_out)
    # prints
    l = "   W@ :   wr : "
    for read_idx in range(nof_read):
      l += ("rd%02d " % read_idx)
    print(l)
    for word_idx in range(nof_word):
      l = ("0x%03X : " % word_idx) + ("%4d : " % dat_in[word_idx])
      for read_idx in range(nof_read):
        l += ("%4d " % dat_outs[read_idx][word_idx])
      print(l)

  def get_snapshot(self, snap_name="dec_out", count=1, man_valid=True, man_trig=True, raw_fmt=False):
    snap = self.fpga.snapshots[self.receiver_basename + snap_name]
    data = snap.read_raw(man_valid=man_valid, man_trig=man_trig)

    if snap_name == 'dec_out':
      dt, shape, d_w, d_dp = np.dtype('int16'), (-1, 4), 16, 15
    elif snap_name == "decim_out":
      dt, shape, d_w, d_dp = np.dtype('int16'), (-1, 4), 16, 15
    elif snap_name == "HBs_HB2_out":
      dt, shape, d_w, d_dp = np.dtype('int16'), (-1, 4), 16, 15
    elif snap_name == "HBs_HB1_out":
      dt, shape, d_w, d_dp = np.dtype('int16'), (-1, 4), 16, 15
    elif snap_name == "HBs_HB0_out":
      dt, shape, d_w, d_dp = np.dtype('int16'), (-1, 4), 16, 15
    elif snap_name == "valid_out":
      dt, shape, d_w, d_dp = np.dtype('int8'), (-1), 8, 0
    elif snap_name == "L0_0_din0_in":
      dt, shape, d_w, d_dp = np.dtype('int32'), (-1), 8, 7
    elif snap_name == "L0_0_mult_out":
      dt, shape, d_w, d_dp = np.dtype('int32'), (-1), 24, 22
    elif snap_name == "L0_0_cast_out":
      dt, shape, d_w, d_dp = np.dtype('int32'), (-1), 16, 15
    elif snap_name == "dec_fir0_sum_out":
      dt, shape, d_w, d_dp = np.dtype('int64'), (-1), 40, 30 
    elif snap_name == "dec_fir0_sr5_out":
      dt, shape, d_w, d_dp = np.dtype('int64'), (-1), 40, 30
    elif snap_name == "rescale_out":
      dt, shape, d_w, d_dp = np.dtype('int8'), (-1, 4), 8, 7
     
    dt = dt.newbyteorder('>')
    tmp = np.frombuffer(data[0]['data'], dtype=dt).copy()
    if raw_fmt:
      return (None, None), tmp

    tmp[tmp>2**(d_w-1)-1] -= 2**d_w
    tmp = tmp / 2.0**d_dp
    tmp = tmp.reshape(shape)
    return (d_w, d_dp), tmp


  @property
  def Fc(self):
    return float(self.kc) / self.K * self.Fe
  
  @Fc.setter 
  def Fc(self, value):
    self.kc = int(value / self.Fe * self.K)

  @property
  def kc(self):
    return self._kc
  
  @kc.setter 
  def kc(self, value):
    assert type(value) is int
    self._kc = value
    self.NCO_calc_tables()
    self.NCO_write_tables()

  @property
  def decimation(self):
    return self._decimation
  
  @decimation.setter 
  def decimation(self, value):
    configs = {2: 0,
               8: 1,
               }
    assert value in configs.keys()
    self._decimation = value
    self.fpga.write_int( self.receiver_basename + "HBs_true", configs[value])



