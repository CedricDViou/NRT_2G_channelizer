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
# Configure ADC5G ADCs connected on ROACH2 for NRT
################################################################################


import numpy as np
import matplotlib.pyplot as plt
import struct
import adc5g
import tqdm


class ADC(object):
  def __init__(self, fpga=None, zdok_n=None, Fe=None, adcmode='I', snap_basename='ADC_wave'):
    assert fpga is not None
    assert zdok_n is not None
    assert Fe is not None
    self.fpga = fpga
    self.zdok_n = zdok_n
    self.Fe = Fe
    self.name = 'ADC%d' % self.zdok_n
    self.snap_basename = snap_basename
    self.snapshot = fpga.snapshots[snap_basename+'%d' % self.zdok_n]
    
    self.wave = None

    self.adcmodes = {'I' : 0b1000,
                     'Q' : 0b1010,
                     }
    self.adcmode_codes = {0b1000: 'I',
                          0b1010: 'Q',
                          }
    self._adcmode=adcmode            

    
    # overload adc5g get_snapshot
    global adc5g
    adc5g.tools.get_snapshot = self._get_snapshot

  def __str__(self):
    return "ASIAA 5 GSps ADC on ZDOK%d sampling input %s at %f GS/s" % (self.zdok_n, self._adcmode, self.Fe/1e9)

  def __repr__(self):
    return "ADC(fpga=%s, zdok_n=%d, Fe=%d, snap_basename=\'%s\')" % (str(self.fpga), self.zdok_n, self.Fe, self.snap_basename)

  # define get_snapshot as we don't have it available in our casperfpga lib version
  def _get_snapshot(self, fpga, snap_name, bitwidth=8, man_trig=True, wait_period=2):
    """
    Reads a one-channel snapshot off the given 
    ROACH and returns the time-ordered samples.
    USN version
    """
    grab = fpga.snapshots[snap_name].read_raw(man_trig=man_trig)[0] 
    data = struct.unpack('%ib' %grab['length'], grab['data'])
    return data

  def run_DVW_calibration(self):
    # Calibrate ADC DVW
    # from https://github.com/Smithsonian/adc_tests
    # forked here https://github.com/CedricDViou/adc_tests
    adc5g.tools.set_test_mode(self.fpga, self.zdok_n)
    opt0, glitches0  = adc5g.tools.calibrate_mmcm_phase(self.fpga, self.zdok_n, [self.snapshot.name,])
    self.DVW_cal = opt0, glitches0
    adc5g.tools.unset_test_mode(self.fpga, self.zdok_n)

  def print_DVW_calibration(self):
    print(adc5g.tools.pretty_glitch_profile(*self.DVW_cal))

  def get_snapshot(self, count=1):
    data = self.snapshot.read_raw(man_valid=True, man_trig=True)
    tmp = np.frombuffer(data[0]['data'], dtype='int8')
    if count == 1:
      self.wave = tmp
    elif count > 1:
      nof_samples = tmp.shape[0]
      self.wave = np.empty((count, nof_samples), dtype='int8')
      self.wave[0] = tmp
      for itt in tqdm.tqdm(range(1, count)):
        data = self.snapshot.read_raw(man_valid=True, man_trig=True)
        self.wave[itt] = np.frombuffer(data[0]['data'], dtype='int8')

  def dump_snapshot(self):
    if self.wave is not None:
      self.wave.tofile(self.snapshot.name + "_data.bin", sep = '')

  def plot_snapshot(self, axs):
    self.get_snapshot()
    ADC_wave = self.wave.copy()
    Nfft = 4096
    Nech_to_plot = 16384

    axs[0].plot(np.arange(Nech_to_plot) / self.Fe * 1e6,
                ADC_wave[:Nech_to_plot],
                label=self.name)

    cnt, bins, _ = axs[1].hist(self.wave, bins=np.arange(-128, 129) - 0.5)

    nof_samples = len(ADC_wave)
    f = np.arange(Nfft/2+1, dtype='float') / Nfft * self.Fe /1e6 
    w = np.blackman(Nfft)
    ADC_wave.shape = ((-1, Nfft))
    DATA = np.fft.rfft(w * ADC_wave, axis=-1)
    DATA = DATA.real**2 + DATA.imag**2
    DATA = DATA.mean(axis=0)
    axs[2].plot(f,
                10*np.log10(DATA),
                label=self.name)

    axs[0].set_xlabel(u"Time (us)")
    axs[0].set_xlim((0, (Nech_to_plot-1) / self.Fe * 1e6))
    axs[1].set_xlabel("ADC code")
    axs[1].set_xlim(bins[[0, -1]])
    axs[2].set_xlabel("Frequency (MHz)")
    axs[2].set_xlim((0, f[-1]))
    
    axs[0].set_ylabel("ADC code\nin [-128, 128[")
    axs[1].set_ylabel("Counts")
    axs[2].set_ylabel("Power (dB)")

  @property
  def adcmode(self):
    self._adcmode = adc5g.spi.get_spi_control(self.fpga,
                                         self.zdok_n)['adcmode']
    return self.adcmode_codes[self._adcmode]

  @adcmode.setter
  def adcmode(self, value):
    if value not in self.adcmodes.keys():
      raise ValueError("Only I or Q inputs implemented on ADC5Gs")
    self._adcmode = value
    adc5g.spi.set_spi_control(self.fpga,
                              self.zdok_n,
                              adcmode=self.adcmodes[self._adcmode])
