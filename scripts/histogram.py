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

class histogram(object):
    def __init__(self, fpga=None, basename='histogram_'):
        assert fpga is not None
        self.fpga = fpga
        self.basename = basename
        self.buses = None
        self.init_dict(self.fpga.listdev())
  
    def init_dict(self, dev):
        # list buses processed by histogram module
        dev = [d for d in dev if d.startswith(self.basename)]
        
        # Extract bus names and bit list
        buses = {}
        for d in dev:
            _, bus_name, bit_num = d.split('_')
            bit_num = int(bit_num.replace('b', ''))
            if bus_name in buses.keys():
                buses[bus_name].add(bit_num)
            else:
                buses[bus_name] = {bit_num, }

        # Check that buses are full
        for bus_name in buses.keys():
            bits = sorted(buses[bus_name])
            nof_bits = bits[-1]+1
            assert bits == range(nof_bits)
            buses[bus_name] = {'width' : nof_bits,
                               'counts': np.zeros(nof_bits, dtype=np.uint64),
                               }
        self.buses = buses

    def get_counts(self):
        for bus in self.buses.keys():
            for bit in range(self.buses[bus]['width']):
                self.buses[bus]['counts'][bit] = self.fpga.read_uint(self.basename + bus + ('_b%d' % bit))

    def plot_counts(self):
        self.fig, self.axs = plt.subplots(nrows=len(self.buses.keys()),
                                          ncols=1,
                                          sharey='col'
                                          )
        self.bars = []
        for ax, bus in zip(self.axs, self.buses.keys()):
            bit_num = range(self.buses[bus]['width'])
            bar = ax.bar(bit_num,
                         self.buses[bus]['counts'],
                         log=True)
            self.bars.append(bar)
            ax.set_xticks(bit_num)
            ax.set_xticklabels(bit_num)
        ax.set_ybound(lower=1)
        plt.show(block=False)

    def update_plot(self):
        for bar, bus in zip(self.bars, self.buses.keys()):
            for patch, count in zip(bar.get_children(), self.buses[bus]['counts']):
                patch.set_height(count)
        self.fig.canvas.draw() 
        self.fig.canvas.flush_events() 

    
# my_hist = histogram(mydesign.fpga)
# my_hist.get_counts()
# my_hist.plot_counts()
# while True:
#     time.sleep(1.1)
#     my_hist.get_counts()
#     my_hist.update_plot()

