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
    self.Nfft = 4096
    self.Nech_to_plot = 16384
    self.f = []
    self.NY_Zone = 1  # 1: default for baseband sampling [0-Fe/2], 2: [Fe/2, Fe], ...
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
    self.ADC_OGP = {'offset': {1: 128, 2: 128, 3: 128, 4: 128},
                      'gain': {1: 128, 2: 128, 3: 128, 4: 128},
                     'phase': {1: 128, 2: 128, 3: 128, 4: 128},
                    }
    self.ADC_read = {'offset': self.get_spi_offset_reg,
                       'gain': self.get_spi_gain_reg,
                      'phase': self.get_spi_phase_reg,
                    }                
    self.ADC_write = {'offset': self.set_spi_offset_reg,
                        'gain': self.set_spi_gain_reg,
                       'phase': self.set_spi_phase_reg,
                      }                
  
    self.ADC_nof_bits = 8
    self.ADC_bins = np.arange(-2**(self.ADC_nof_bits-1), 2**(self.ADC_nof_bits-1)+1) - 0.5

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

  def DVW_calibration(self, event=None):
    self.run_DVW_calibration()
    if event is not None:
      self.update_data()

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
    self.nof_trig = count
    data = self.snapshot.read_raw(man_valid=True, man_trig=True)
    tmp = np.frombuffer(data[0]['data'], dtype='int8')
    self.nof_samples = tmp.shape[0]
    self.wave = np.empty((self.nof_trig, self.nof_samples), dtype='int8')
    self.wave[0] = tmp
    if self.nof_trig > 1:
      for itt in tqdm.tqdm(range(1, self.nof_trig), disable=(self.nof_trig<=10)):
        data = self.snapshot.read_raw(man_valid=True, man_trig=True)
        self.wave[itt] = np.frombuffer(data[0]['data'], dtype='int8')

  def dump_snapshot(self):
    if self.wave is not None:
      self.wave.tofile(self.snapshot.name + "_data.bin", sep = '')

  def set_spi_phase_reg(self, roach, zdok_n, chan, reg_val):
    adc5g.set_spi_register(roach, zdok_n, adc5g.CHANSEL_REG_ADDR, chan)
    adc5g.set_spi_register(roach, zdok_n, adc5g.EXTPHAS_REG_ADDR, reg_val)
    adc5g.set_spi_register(roach, zdok_n, adc5g.CALCTRL_REG_ADDR, 2<<6)

  def get_spi_phase_reg(self, roach, zdok_n, chan):
    adc5g.set_spi_register(roach, zdok_n, adc5g.CHANSEL_REG_ADDR, chan)
    reg_val = adc5g.get_spi_register(roach, zdok_n, adc5g.EXTPHAS_REG_ADDR-0x80)
    return reg_val

  def set_spi_offset_reg(self, roach, zdok_n, chan, reg_val):
    adc5g.set_spi_register(roach, zdok_n, adc5g.CHANSEL_REG_ADDR, chan)
    adc5g.set_spi_register(roach, zdok_n, adc5g.EXTOFFS_REG_ADDR, reg_val)
    adc5g.set_spi_register(roach, zdok_n, adc5g.CALCTRL_REG_ADDR, 2<<2)

  def get_spi_offset_reg(self, roach, zdok_n, chan):
    adc5g.set_spi_register(roach, zdok_n, adc5g.CHANSEL_REG_ADDR, chan)
    reg_val = adc5g.get_spi_register(roach, zdok_n, adc5g.EXTOFFS_REG_ADDR-0x80)
    return reg_val

  def set_spi_gain_reg(self, roach, zdok_n, chan, reg_val):
    adc5g.set_spi_register(roach, zdok_n, adc5g.CHANSEL_REG_ADDR, chan)
    adc5g.set_spi_register(roach, zdok_n, adc5g.EXTGAIN_REG_ADDR, reg_val)
    adc5g.set_spi_register(roach, zdok_n, adc5g.CALCTRL_REG_ADDR, 2<<4)

  def get_spi_gain_reg(self, roach, zdok_n, chan):
    adc5g.set_spi_register(roach, zdok_n, adc5g.CHANSEL_REG_ADDR, chan)
    reg_val = adc5g.get_spi_register(roach, zdok_n, adc5g.EXTGAIN_REG_ADDR-0x80)
    return reg_val

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

    button_axes_pos = ( ([0.01, 0.15, 0.1, 0.05], [0.11, 0.15, 0.1, 0.05]),
                        ([0.01, 0.10, 0.1, 0.05], [0.11, 0.10, 0.1, 0.05]),
                        ([0.01, 0.05, 0.1, 0.05], [0.11, 0.05, 0.1, 0.05]),
                       )

    axclear_data = self.fig.add_axes(button_axes_pos[0][0])
    bclear_data = Button(axclear_data, 'Clear data')
    bclear_data.on_clicked(self.clear_data)

    axupdate_data = self.fig.add_axes(button_axes_pos[0][1])
    bupdate_data = Button(axupdate_data, 'Update')
    bupdate_data.on_clicked(self.update_data)

    axOPB_Scan = self.fig.add_axes(button_axes_pos[1][0])
    bOPB_Scan = Button(axOPB_Scan, 'OPB scan')
    bOPB_Scan.on_clicked(self.OPB_Scan)

    axDVW_cal = self.fig.add_axes(button_axes_pos[1][1])
    bDVW_cal = Button(axDVW_cal, 'DVW calibration')
    bDVW_cal.on_clicked(self.DVW_calibration)

    
    axClear_OPB = self.fig.add_axes(button_axes_pos[2][0])
    bClear_OPB = Button(axClear_OPB, 'Clear OPB')
    bClear_OPB.on_clicked(self.clear_OPB)

    axOPB_Cal = self.fig.add_axes(button_axes_pos[2][1])
    bOPB_Cal = Button(axOPB_Cal, 'OPB calibration')
    bOPB_Cal.on_clicked(self.OPB_Cal)


    self.axsctrl = [axDVW_cal, axupdate_data, axclear_data, axClear_OPB, axOPB_Cal, axOPB_Scan]
    self.buttons = [bDVW_cal, bupdate_data, bclear_data, bClear_OPB, bOPB_Cal, bOPB_Scan]


    self.cidweel = self.fig.canvas.mpl_connect('scroll_event', self.callback_scroll)

    self.get_snapshot(count=10)
    self.plot_interleaved_data(self.axs[-1][1:])
    self.plot_ADC_Core_data(self.axs[:2])

    plt.show(block=False)


  def plot_interleaved_data(self, axs):
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
    if self.NY_Zone % 2 == 0:  # reverse frequency axis
      DATA = DATA[..., ::-1]
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

  def clear_data(self, event=None):
    plt.close(self.fig)
    self.create_calibration_GUI()

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
    if self.NY_Zone % 2 == 0:  # reverse frequency axis
      DATA = DATA[..., ::-1]
    for l, data in zip(self.line_ADC_DSP, DATA):
      l.set_ydata(data)

  def plot_ADC_Core_data(self, axs):
    DCs, stds = self.wave_DCs_stds()
    self.line_DCs = []
    self.line_stds = []
    for DC_ax, vals in zip(axs[0], DCs):
      self.line_DCs.append(*DC_ax.plot(vals, '.'))
    for std_ax, vals in zip(axs[1], stds):
      self.line_stds.append(*std_ax.plot(vals, '.'))
    
    axs[0][0].set_ylabel('DC')
    axs[1][0].set_ylabel('Std')

  def update_ADC_Core_data(self):
    DCs, stds =  self.wave_DCs_stds()
    
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
    reset_val = 128
    for action in ('offset', 'gain', 'phase'):
      for core in self.ADC_cores:
        self.ADC_write[action](self.fpga, self.zdok_n, core, reset_val)
        self.ADC_OGP[action][core] = reset_val
    if event is not None:
      self.update_data()


  def wave_DCs_stds(self, DCs=True, stds=True):
    ADC_wave = self.wave.copy()
    nof_samples = self.nof_samples // self.ADC_nof_cores
    ADC_wave.shape = (self.nof_trig, nof_samples, self.ADC_nof_cores)
    if DCs and not stds:
      DCs = ADC_wave.mean(axis=1).T
      return DCs
    if stds and not DCs:
      stds = ADC_wave.std(axis=1).T
      return stds
    if DCs and stds:
      DCs = ADC_wave.mean(axis=1).T
      stds = ADC_wave.std(axis=1).T
      return DCs , stds


  def OPB_Scan(self, event=None):

    self.clear_OPB()

    reg_vals = np.arange(256)
    trials = 2
    self.DCs_vs_reg_val = np.empty((len(reg_vals), self.ADC_nof_cores, trials), dtype=float)
    action = 'offset'
    for reg in reg_vals:
      for core in self.ADC_cores:
        self.ADC_write[action](self.fpga, self.zdok_n, core, reg)
      self.get_snapshot(count=trials)
      DCs = self.wave_DCs_stds(stds=False)
      print(reg, DCs)
      self.DCs_vs_reg_val[reg] = DCs
    
    for core, ax in zip(self.ADC_cores, self.axs[0]):
      ax.cla()
      for i in range(trials):
        ax.plot(reg_vals, self.DCs_vs_reg_val[:, core-1, i], '.')

    self.clear_OPB()

    reg_vals = np.arange(256)
    trials = 2
    self.stds_vs_reg_val = np.empty((len(reg_vals), self.ADC_nof_cores, trials), dtype=float)
    action = 'gain'
    for reg in reg_vals:
      for core in self.ADC_cores:
        self.ADC_write[action](self.fpga, self.zdok_n, core, reg)
      self.get_snapshot(count=trials)
      stds = self.wave_DCs_stds(DCs=False)
      print(reg, stds)
      self.stds_vs_reg_val[reg] = stds
    
    for core, ax in zip(self.ADC_cores, self.axs[1]):
      ax.cla()
      for i in range(trials):
        ax.plot(reg_vals, self.stds_vs_reg_val[:, core-1, i]**2, '.')   # plot variance in log scale
        ax.set_yscale('log')
    
    self.clear_OPB()


  def OPB_Cal(self, event=None):
    # Automatic offset calibration (preliminary)
    for auto_cal in range(3):   # somehow, calibration on core 4 take several itteration to converge, while 1, 2, 3 are fine on first shot... 
      self.get_snapshot(count=10)
      org_DCs = self.wave_DCs_stds(stds=False)
      org_DC = np.mean(org_DCs, axis=-1)
      print("org_DC= ", org_DC)
      
      action = 'offset'
      dreg = 16
      for core in self.ADC_cores:
        old_reg = self.ADC_read[action](self.fpga, self.zdok_n, core)
        new_reg = old_reg + dreg
        self.ADC_write[action](self.fpga, self.zdok_n, core, new_reg)
        self.ADC_OGP[action][core] = new_reg
      
      self.get_snapshot(count=10)
      self.update_data()
      new_DCs = self.wave_DCs_stds(stds=False)
      new_DC = np.mean(new_DCs, axis=-1)
      print("new_DC= ",new_DC)
      
      dDCs_over_dreg = (new_DC - org_DC) / dreg
      print("dd= ", dDCs_over_dreg)
      
      for core, dd, DC in zip(self.ADC_cores, dDCs_over_dreg, new_DC):
        corr_reg = round(self.ADC_OGP[action][core] + (0 - DC) / dd)
        self.ADC_write[action](self.fpga, self.zdok_n, core, corr_reg)
        self.ADC_OGP[action][core] = corr_reg
      
      self.update_data()
    final_DCs = self.wave_DCs_stds(stds=False)
    final_DC = np.mean(final_DCs, axis=-1)
    print("final_DC= ", final_DC)


    # END of automatic offset calibration (preliminary)

    # Automatic gain calibration (preliminary)
    # END of automatic gain calibration (preliminary)

    # Phase calibration (preliminary)
    self.get_snapshot(count=100)
    ADC_wave=self.wave.copy()
    ADC_wave.shape = ((self.nof_trig, -1, self.ADC_nof_cores))
    TF = np.fft.rfft(self.window[None, :, None] * ADC_wave, axis=-2)
    C=TF[:,:,:,None]*TF[:,:,None,:].conj()
    C = np.mean(C, axis=0)
    fig, axs = plt.subplots(figsize=(8, 8), #   muADC1,   muADC2,    muADC3,   muADC4
                            nrows = 4,       #  stdADC1,  stdADC2,   stdADC3,  stdADC4
                            ncols = 4,       #  phiADC1,  phiADC2,   phiADC3,  phiADC4
                                             # controls,     wave, histogram, spectrum
                            )
    for i in (0,1,2,3):
      for j in (0,1,2,3):
        axs[i][j].plot(np.angle(C[:,i,j]))
        axs[i][j].set_ylim((-np.pi, np.pi))
    plt.show(block=False)
    
    print("do something!")
    self.update_data()
    # END of phase calibration (preliminary)


  def callback_scroll(self, event):
    self.event = event
    # print(event)
    action, core, direction = None, None, None
    for axs_row, _action in zip(self.axs[:2], ('offset', 'gain')):
      if event.inaxes in axs_row:
        for _core, ax in zip(self.ADC_cores, axs_row):
          if event.inaxes == ax:
            action, core = _action, _core
            direction = event.button

    if type is not None:  # then we are modifying one of the calibration parameters of one ADC core
      # print("Action %s, core %d, direction %s" % (str(action), core, direction))
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

  @property
  def NY_Zone(self):
    return self._NY_Zone

  @NY_Zone.setter
  def NY_Zone(self, value):
    if type(value) is not int :
      raise ValueError("Nyquist Zone can only be integer type")
    self._NY_Zone = value
    f = np.arange(0, self.Nfft/2+1, 1, dtype='float') / self.Nfft * (self.Fe/1e6)
    F_offset = float(value-1)/2 * self.Fe/1e6
    self.f = F_offset + f