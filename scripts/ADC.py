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
from matplotlib.widgets import Button
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
    self.nof_trig = 0

    self.adcmodes = {'I' : 0b1000,
                     'Q' : 0b1010,
                     }
    self.adcmode_codes = {0b1000: 'I',
                          0b1010: 'Q',
                          }
    self._adcmode=adcmode            

    self.ADC_nof_cores = 4
    self.ADC_cores = (1, 3, 2, 4)
    self.ADC_OGP = {'offset': {1:0, 2:0, 3:0, 4:0},
                    'gain': {1:0, 2:0, 3:0, 4:0},
                    'phase': {1:0, 2:0, 3:0, 4:0},
                    }
    self.ADC_read = {'offset': adc5g.spi.get_spi_offset,
                    'gain': adc5g.spi.get_spi_gain,
                    'phase': adc5g.spi.get_spi_phase,
                    }                
    self.ADC_write = {'offset': adc5g.spi.set_spi_offset,
                      'gain': adc5g.spi.set_spi_gain,
                      'phase': adc5g.spi.set_spi_phase,
                      }                
  
    self.ADC_nof_bits = 8
    self.ADC_bins = np.arange(-2**(self.ADC_nof_bits-1), 2**(self.ADC_nof_bits-1)+1) - 0.5

    self.Nfft = 4096
    self.Nech_to_plot = 16384
    self.f = np.arange(self.Nfft/2+1, dtype='float') / self.Nfft * self.Fe /1e6 
    self.window = np.blackman(self.Nfft)

    # set by plot_snapshot and used by update_snapshot 
    self.line_ADC_code = None
    self.patches_hist = None
    self.line_ADC_DSP = None

    
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

  def run_DVW_calibration(self, event=None):
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
    self.nof_trig = count
    data = self.snapshot.read_raw(man_valid=True, man_trig=True)
    tmp = np.frombuffer(data[0]['data'], dtype='int8')
    nof_samples = tmp.shape[0]
    self.wave = np.empty((count, nof_samples), dtype='int8')
    self.wave[0] = tmp
    if count > 1:
      for itt in tqdm.tqdm(range(1, count)):
        data = self.snapshot.read_raw(man_valid=True, man_trig=True)
        self.wave[itt] = np.frombuffer(data[0]['data'], dtype='int8')

  def dump_snapshot(self):
    if self.wave is not None:
      self.wave.tofile(self.snapshot.name + "_data.bin", sep = '')

  def create_calibration_GUI(self):
    self.fig, self.axs = plt.subplots(figsize=(20, 8), #   muADC1,   muADC2,    muADC3,   muADC4
                                      nrows = 4,       #  stdADC1,  stdADC2,   stdADC3,  stdADC4
                                      ncols = 4,       #  phiADC1,  phiADC2,   phiADC3,  phiADC4
                                                       # controls,     wave, histogram, spectrum
                                      )
    self.fig.subplots_adjust(left=0.05, bottom=0.07, right=0.99, top=0.99)
    for ax in self.axs[:3]:
      ax[0].get_shared_y_axes().join(ax[0], *ax[1:])
      ax[0].get_shared_x_axes().join(ax[0], *ax[1:])
      for a in ax:
        a.grid('on')
    self.axs[-1][0].remove()

    axDVW_cal = self.fig.add_axes([0.01, 0.05, 0.1, 0.05])
    bDVW_cal = Button(axDVW_cal, 'DVW calibration')
    bDVW_cal.on_clicked(self.run_DVW_calibration)

    axupdate_data = self.fig.add_axes([0.01, 0.10, 0.1, 0.05])
    bupdate_data = Button(axupdate_data, 'Update')
    bupdate_data.on_clicked(self.update_data)
    
    axClear_OPB = self.fig.add_axes([0.01, 0.15, 0.1, 0.05])
    bClear_OPB = Button(axClear_OPB, 'Clear OPB')
    bClear_OPB.on_clicked(self.clear_OPB)

    axclear_data = self.fig.add_axes([0.11, 0.10, 0.1, 0.05])
    bclear_data = Button(axclear_data, 'Clear data')
    bclear_data.on_clicked(self.clear_data)

    self.axsctrl = [axDVW_cal, axupdate_data, axclear_data, axClear_OPB, ]
    self.buttons = [bDVW_cal, bupdate_data, bclear_data, bClear_OPB, ]

    self.cidweel = self.fig.canvas.mpl_connect('scroll_event', self.callback_scroll)

    self.get_snapshot(count=10)
    self.plot_interleaved_data()
    self.plot_ADC_Core_data()

    plt.show(block=False)


  def plot_interleaved_data(self):
    axs = self.axs[-1][1:]
    ADC_wave = self.wave.copy()

    self.line_ADC_code = axs[0].plot(np.arange(self.Nech_to_plot) / self.Fe * 1e6,
                                     ADC_wave[:, :self.Nech_to_plot].T,
                                     '.', markersize=1,
                                     label=self.name)

    cnt, bins, self.patches_hist = axs[1].hist(self.wave.flatten(), bins=self.ADC_bins, orientation='horizontal' )

    ADC_wave.shape = ((self.nof_trig, -1, self.Nfft))
    DATA = np.fft.rfft(self.window * ADC_wave, axis=-1)
    DATA = DATA.real**2 + DATA.imag**2
    DATA = DATA.mean(axis=0)
    DATA = 10*np.log10(DATA)
    self.line_ADC_DSP = axs[2].plot(self.f,
                                    DATA.T,
                                    '-', linewidth=1,
                                    label=self.name)

    axs[0].set_xlabel(u"Time (us)")
    axs[0].set_xlim((0, (self.Nech_to_plot-1) / self.Fe * 1e6))
    axs[1].set_ylabel("ADC code")
    axs[1].set_ylim(bins[[0, -1]])
    axs[2].set_xlabel("Frequency (MHz)")
    axs[2].set_xlim((self.f[0], self.f[-1]))
    
    axs[0].set_ylabel("ADC code\nin [-128, 128[")
    axs[0].set_ylim((-128, 127))
    axs[1].set_xlabel("Counts")
    axs[1].set_xlim((0, 2*max(cnt)))
    axs[2].set_ylabel("Power (dB)")
    axs[2].set_ylim((20, 80))

  def update_data(self, event=None):
    self.get_snapshot(count=10)
    self.update_interleaved_data()
    self.update_ADC_Core_data()
    self.fig.canvas.draw()

  def update_interleaved_data(self):
    ADC_wave = self.wave.copy()
    for l, data in zip(self.line_ADC_code, ADC_wave):
      l.set_ydata(data)

    n, _ = np.histogram(self.wave.flatten(), self.ADC_bins)
    for count, rect in zip(n, self.patches_hist):
           rect.set_width(count)

    ADC_wave.shape = ((self.nof_trig, -1, self.Nfft))
    DATA = np.fft.rfft(self.window * ADC_wave, axis=-1)
    DATA = DATA.real**2 + DATA.imag**2
    DATA = DATA.mean(axis=0)
    DATA = 10*np.log10(DATA)
    for l, data in zip(self.line_ADC_DSP, DATA):
      l.set_ydata(data)

  def plot_ADC_Core_data(self):
    axs = self.axs[:2]
    ADC_wave = self.wave.copy()
    nof_trig, nof_samples = ADC_wave.shape
    nof_samples = nof_samples//self.ADC_nof_cores
    ADC_wave.shape = (nof_trig, nof_samples, self.ADC_nof_cores)
    
    DCs = ADC_wave.mean(axis=1).T
    stds = ADC_wave.std(axis=1).T
    
    self.line_DCs = []
    self.line_stds = []
    for DC_ax, vals in zip(axs[0], DCs):
      self.line_DCs.append(*DC_ax.plot(vals, '.'))
    for std_ax, vals in zip(axs[1], stds):
      self.line_stds.append(*std_ax.plot(vals, '.'))
    
    axs[0][0].set_ylabel('DC')
    axs[1][0].set_ylabel('Std')

  def update_ADC_Core_data(self):
    ADC_wave = self.wave.copy()
    nof_trig, nof_samples = ADC_wave.shape
    nof_samples = nof_samples//self.ADC_nof_cores
    ADC_wave.shape = (nof_trig, nof_samples, self.ADC_nof_cores)
    
    DCs = ADC_wave.mean(axis=1).T
    stds = ADC_wave.std(axis=1).T
    
    ylims = self.axs[0][0].get_ylim()
    for line, vals in zip(self.line_DCs, DCs):
      xs = line.get_xdata()
      ys = line.get_ydata()
      xs = np.hstack((xs, np.arange(xs[-1] + 1, xs[-1] + len(vals) + 1) ))
      ys = np.hstack((ys, vals))
      line.set_xdata(xs)
      line.set_ydata(ys)
      ylims = min(ylims[0], 1.2*min(ys)), max(ylims[1], 1.2*max(ys))
    self.axs[0][0].set_xbound(upper=xs[-1])
    self.axs[0][0].set_ylim(ylims)
    
    ylims = self.axs[1][0].get_ylim()
    for line, vals in zip(self.line_stds, stds):
      xs = line.get_xdata()
      ys = line.get_ydata()
      xs = np.hstack((xs, np.arange(xs[-1] + 1, xs[-1] + len(vals) + 1) ))
      ys = np.hstack((ys, vals))
      line.set_xdata(xs)
      line.set_ydata(ys)
      ylims = min(ylims[0], 1.2*min(ys)), max(ylims[1], 1.2*max(ys))
    self.axs[1][0].set_xbound(upper=xs[-1])
    self.axs[1][0].set_ylim(ylims)


  def clear_OPB(self, event=None):
    for action in ('offset', 'gain', 'phase'):
      for core in self.ADC_cores:
        self.ADC_write[action](self.fpga, self.zdok_n, core, 0)
    self.update_data()


  def callback_scroll(self, event):
    self.event = event
    print(event)
    action, core, direction = None, None, None
    for axs_row, _action in zip(self.axs[:2], ('offset', 'gain')):
      if event.inaxes in axs_row:
        for _core, ax in zip(self.ADC_cores, axs_row):
          if event.inaxes == ax:
            action, core = _action, _core
            direction = event.button

    if type is not None:  # then we are modifying one of the calibration parameters of one ADC core
      print("Action %s, core %d, direction %s" % (str(action), core, direction))
      old_value = self.ADC_read[action](self.fpga, self.zdok_n, core)
      new_value = old_value - 1 if direction == u'up' else old_value + 1
      self.ADC_write[action](self.fpga, self.zdok_n, core, new_value)
      self.ADC_OGP[action][core] = new_value
      print(self.ADC_OGP)
    
    self.update_data()


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
