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
# Configure Valon to clock ROACH2 ADCs for NRT
################################################################################



from valon_synth import Synthesizer, SYNTH_A, SYNTH_B


class ADC_clock(Synthesizer):
  def __init__(self, dev='/dev/ttyUSB_valon'):
    Synthesizer.__init__(self, dev)

  def set_config(self, FA=None, PA=None, FB=None, PB=None):
    self.set_ref_config(ref_freq=10e6, ext_ref = True)
    if (FA is not None and PA is not None):
        self.set_chan_config(SYNTH_A, rf_level=PA, freq=FA)
    if (FB is not None and PB is not None):
        self.set_chan_config(SYNTH_B, rf_level=PB, freq=FB)

  def print_config(self):
    FA, PA, LA = self.get_chan_config(SYNTH_A)
    FB, PB, LB = self.get_chan_config(SYNTH_B)
    print("  Input clock is %f MHz, %f dBm (%slocked)" % (FA,
                                                          PA,
                                                          "" if LA else "NOT "))
    print("    =>  Sampling clock is %f MHz, %f dBm" % (2*FA, PA))
    print("  Input tone is %f MHz, %f dBm (%slocked)" % (FB,
                                                         PB,
                                                         "" if LB else "NOT "))
    
  def set_ref_config(self, ref_freq=10e6, ext_ref = True):
    self.set_ref_select(ext_ref)
    self.set_reference(ref_freq)

  def set_chan_config(self, chan=None, rf_level=-4, freq=10e6):
    self.set_options(chan, double=1, half=0, divider=1, low_spur=0)
    self.set_rf_level(chan, rf_level)
    self.set_frequency(chan, freq)

  def get_chan_config(self, chan):
    freq = self.get_frequency(chan)
    rf_level = self.get_rf_level(chan)
    locked = self.get_phase_lock(chan)
    return freq, rf_level, locked
