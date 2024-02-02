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
# Readback ADC samples saved with adc_c9r_sst_v5
#  [ ADC.get_snapshot(count=100) for ADC in mydesign.ADCs ]
#  [ ADC.dump_snapshot() for ADC in mydesign.ADCs ]

################################################################################


import numpy as np

nof_samples = 16384
wave0 = np.fromfile('ADC_wave0_data.bin', dtype='int8', sep='').reshape((-1, nof_samples))
wave1 = np.fromfile('ADC_wave1_data.bin', dtype='int8', sep='').reshape((-1, nof_samples))

wave = np.stack((wave0, wave1))
del wave0
del wave1

nof_chan, nof_trig, nof_samples = wave.shape
nof_ADC = 4
wave.shape = (nof_chan, nof_trig, nof_samples//nof_ADC, nof_ADC)
nof_chan, nof_trig, nof_samples, nof_ADC = wave.shape


