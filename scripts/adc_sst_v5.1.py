#!/home/cedric/anaconda3/envs/2point7/bin/python
'''
This code configures the ROACH2 used for NRT spectral backend.
'''

import casperfpga
import time
import numpy as np
import struct
import sys
import logging
import pylab
import matplotlib.pyplot as plt
import signal
import valon_synth
import adc5g


# https://stackoverflow.com/questions/5619685/conversion-from-ip-string-to-integer-and-backward-in-python
import socket
import struct

def ip2int(addr):
    return struct.unpack("!I", socket.inet_aton(addr))[0]

def int2ip(addr):
    return socket.inet_ntoa(struct.pack("!I", addr))
##########


def fix2real(data, n_bits=18, bin_pt=17):
    data = data.view(np.int64).copy()
    neg = data > (2**(n_bits-1)-1)
    data[neg] -= 2**n_bits
    data = data / 2.0**bin_pt
    return data



roach2 = "192.168.40.71"
bitstream = "../bof/adc_sst_v5/bit_files/adc_sst_v5_2022_Apr_02_2303.fpg"

conf_Valon = True
conf_FPGA = True
ADC_cal = True


Fe = 3600000000.0 # Hz
F_valon = Fe / 2
Fsys = F_valon / 8
Fin = 130000000# Hz



S = valon_synth.Synthesizer('/dev/ttyUSB_valon')
if conf_Valon:
    print('Configuring Valon:')
    ext_ref = True
    S.set_ref_select(ext_ref)
    S.set_reference(10000000.0)

    S.set_options(valon_synth.SYNTH_A, double=1, half=0, divider=1, low_spur=0)
    S.set_rf_level(valon_synth.SYNTH_A, -4)
    S.set_frequency(valon_synth.SYNTH_A, F_valon/1e6)

    S.set_options(valon_synth.SYNTH_B, double=1, half=0, divider=1, low_spur=0)
    S.set_rf_level(valon_synth.SYNTH_B, -4)
    S.set_frequency(valon_synth.SYNTH_B, Fin/1e6)

    print('Done\n')

FA = S.get_frequency(valon_synth.SYNTH_A)
PA = S.get_rf_level(valon_synth.SYNTH_A)
FB = S.get_frequency(valon_synth.SYNTH_B)
PB = S.get_rf_level(valon_synth.SYNTH_B)
LA = S.get_phase_lock(valon_synth.SYNTH_A)
LB = S.get_phase_lock(valon_synth.SYNTH_B)


print("  Input clock is %f MHz, %f dBm (%slocked)" % (FA,
                                                     PA,
                                                     "" if LA else "NOT "))
print("    =>  Sampling clock is %f MHz, %f dBm" % (2*FA, PA))
print("  Input tone is %f MHz, %f dBm (%slocked)" % (FB,
                                                    PB,
                                                    "" if LB else "NOT "))


lh = logging.StreamHandler()
logger = logging.getLogger(roach2)
logger.addHandler(lh)
logger.setLevel(10)




class ADC(object):
  def __init__(self, fpga=None, zdok_n=None, Fe=None, adcmode='I'):
    assert fpga is not None
    assert zdok_n is not None
    self.fpga = fpga
    self.zdok_n = zdok_n
    self.Fe = Fe
    self.name = 'ADC%d' % self.zdok_n
    self.snapshot = fpga.snapshots['ADC_wave%d' % self.zdok_n]
    #self.snapshot = fpga.snapshots['adcsnap%d' % self.zdok_n]
    
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

  # define get_snapshot as we don't have it available in our casperfpga lib version
  def _get_snapshot(self, roach, snap_name, bitwidth=8, man_trig=True, wait_period=2):
    """
    Reads a one-channel snapshot off the given 
    ROACH and returns the time-ordered samples.
    USN version
    """
    grab = roach.snapshots[snap_name].read_raw(man_trig=man_trig)[0] 
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

  def get_snapshot(self):
    data = self.snapshot.read_raw(man_valid=True, man_trig=True)
    self.wave = np.frombuffer(data[0]['data'], dtype='int8')

  def dump_snapshot(self):
    if self.wave is not None:
      self.wave.tofile(self.snapshot.name + "_data.bin")

  @property
  def adcmode(self):
    print('getter called')
    self._adcmode = adc5g.spi.get_spi_control(self.fpga,
                                         self.zdok_n)['adcmode']
    return self.adcmode_codes[self._adcmode]

  @adcmode.setter
  def adcmode(self, value):
    if value not in self.adcmodes.keys():
      raise ValueError("Only I or Q inputs implemented on ADC5Gs")
    print('setter called')
    self._adcmode = value
    adc5g.spi.set_spi_control(self.fpga,
                              self.zdok_n,
                              adcmode=self.adcmodes[self._adcmode])



class sefram(object):
  def __init__(self, fpga=None, Fe=None):
    assert fpga is not None
    self.fpga = fpga
    self.Fe = int(Fe)
    self.F_valon = self.Fe / 2
    self.Fsys = self.F_valon / 8
    self.ID = 0xcece
    self.Nfft = 2**12

  @property
  def acc_len(self):
    return self.fpga.read_uint('vacc_n_frmr_acc_len')

  @acc_len.setter 
  def acc_len(self, value): 
    if (value < 0) : 
      raise ValueError("acc_len can't be negative") 
    self.fpga.write_int('vacc_n_frmr_acc_len', value)

  @property
  def Fe(self):
    return self.fpga.read_uint('vacc_n_frmr_pcktizer_ADC_freq')

  @Fe.setter 
  def Fe(self, value):
    assert type(value) is int
    self.fpga.write_int('vacc_n_frmr_pcktizer_ADC_freq', value, blindwrite=True)

  @property
  def ID(self):
    return self.fpga.read_uint('vacc_n_frmr_pcktizer_framer_id')

  @ID.setter 
  def ID(self, value):
    self.fpga.write_int('vacc_n_frmr_pcktizer_framer_id', value)


  @property
  def acc_cnt(self):
    return self.fpga.read_uint('vacc_n_frmr_acc_cnt')

  @property
  def fft_shift(self):
    self._fft_shift = self.fpga.read_uint('SEFRAM_fft_shift')
    return self._fft_shift

  @fft_shift.setter 
  def fft_shift(self, value):
    self._fft_shift = value
    self.fpga.write_int('SEFRAM_fft_shift', self._fft_shift)

  @property
  def fft_gain(self):
    return 2**(bin(self._fft_shift)[2:].count('1'))

  @property
  def dst_addr(self):
    """
    Read IP/UDP_port from FPGA, convert and return ("xxx.xxx.xxx.xxx", UDP_port)
    """
    ip = self.fpga.read_uint('OneGbE_tx_ip')
    port = self.fpga.read_uint('OneGbE_tx_port')
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
    self.fpga.write_int('OneGbE_tx_ip', ip, blindwrite=True)
    self.fpga.write_int('OneGbE_tx_port', port)

  def disable(self):
    self.fpga.write_int('OneGbE_rst', 1)
    self.fpga.write_int('vacc_n_frmr_rst', 1)
    self.fpga.write_int('vacc_n_frmr_en', 0)

  def arm(self):
    self.fpga.write_int('OneGbE_rst', 0)
    self.fpga.write_int('vacc_n_frmr_rst', 0)

  def enable(self):
    self.fpga.write_int('vacc_n_frmr_en', 1)

  @property
  def time(self):
    ts         = self.fpga.read_uint('vacc_n_frmr_pcktizer_cur_timestamp')
    sample_cnt = self.fpga.read_uint('vacc_n_frmr_pcktizer_cur_smpl_cnt')
    sysfreq    = self.fpga.read_uint('vacc_n_frmr_pcktizer_cur_smpl_per_sec')
    return ts + float(sample_cnt) / (sysfreq+1)
                   
  @time.setter 
  def time(self, value):
    """
    Set timestamp for framer.
    if time == "now", set timestamp to next int(time.time())
    """
    self.fpga.write_int('vacc_n_frmr_pcktizer_timestamp_load', 0)
    if value == "now":
      now = time.time()
      timestamp = int(now) + 1
    else:
      timestamp = value
    before_half_second = 0.5 - (now-timestamp)
    if before_half_second < 0:
       before_half_second += 1
    time.sleep(before_half_second)
    self.fpga.write_int('vacc_n_frmr_pcktizer_timestamp_init', timestamp, blindwrite=True)
    self.fpga.write_int('vacc_n_frmr_pcktizer_timestamp_load', 1)

  @property
  def IFG(self):
    """
    Set Inter Frame Gap used to send data by framer
    """
    return self.fpga.read_uint('vacc_n_frmr_pcktizer_IFG')

  @IFG.setter 
  def IFG(self, value):
    self._IFG = value
    self.fpga.write_int('vacc_n_frmr_pcktizer_IFG', self._IFG)

  def print_datarate(self):
    bytes_per_chunks = 4096+32
    nof_chunks = 16
    time_per_frame = (bytes_per_chunks + self._IFG) * nof_chunks * (1.0/self.Fsys)
    Nspec_per_sec = float(self.Fe) / self.Nfft
    frame_period = self.acc_len / Nspec_per_sec
    print("Average datarate: %f kiB/s" % (1/frame_period * (bytes_per_chunks * nof_chunks) / 1024))
    print("Peak datarate   : %f MiB/s" % ((bytes_per_chunks * nof_chunks) / time_per_frame / 1024**2))


# make class to control CASPER FPGA design for NRT channelizer
class adc_sst_v5(object):
  def __init__(self, name, bitstream=None, Fe=None, feed='BF'):
    self.name = name
    self.fpga = casperfpga.CasperFpga(self.name)
    time.sleep(0.2)
    self.Fe = Fe
    self.F_valon = self.Fe / 2
    self.Fsys = self.F_valon / 8
    self._feed = feed

    assert self.fpga.is_connected(), 'ERROR connecting to server %s.\n' % (self.name)
    if bitstream is not None:
      print('------------------------')
      print('Programming FPGA with %s...' % bitstream)
      sys.stdout.flush()
      self.fpga.upload_to_ram_and_program(bitstream)
      print('done')

    self.monitoring_regs = (
                   'vacc_n_frmr_pcktizer_cur_timestamp',
                   'vacc_n_frmr_pcktizer_cur_smpl_cnt',
                   'vacc_n_frmr_pcktizer_cur_smpl_per_sec',
                   'vacc_n_frmr_acc_cnt',
                   #'eof_cnt',
                   'OneGbE_tx_full',
                   )
    # Add peripherals and submodules
    self.ADCs = (ADC(fpga=self.fpga, zdok_n=0, Fe=self.Fe),
                 ADC(fpga=self.fpga, zdok_n=1, Fe=self.Fe))
    self.SEFRAM = sefram(fpga=self.fpga, Fe=self.Fe)

    # init modules
    self.SEFRAM.disable()


  def cnt_rst(self):
    self.fpga.write_int('cnt_rst', 1)
    self.fpga.write_int('cnt_rst', 0)

  def arm_PPS(self):
    self.fpga.write_int('reg_arm', 0)
    now = time.time()
    before_half_second = 0.5 - (now-int(now))
    if before_half_second < 0:
      before_half_second += 1
    time.sleep(before_half_second)
    self.fpga.write_int('reg_arm', 1)

  def listdev(self):
    return self.fpga.listdev()

  def monitor(self):
    for reg in self.monitoring_regs:
        print(reg, self.fpga.read_uint(reg))

  @property
  def feed(self):
    return self._feed

  @feed.setter
  def feed(self, value):
    if value not in ('BF', 'HF'):
      raise ValueError('NRT feeds are BF (1-1.8GHz, connected on ADC_I) or HF (1.7-3.5GHz, conected on ADC_Q)')
    self._feed = value
    adcmode = {'BF': 'I',
               'HF': 'Q',
               }
    for ADC in self.ADCs:
      ADC.adcmode=adcmode[self._feed]
      ADC.adcmode=adcmode[self._feed]



mydesign = adc_sst_v5(roach2, bitstream=bitstream, Fe=Fe)



dev = mydesign.listdev()
for d in dev:
    print(d)
print()


if ADC_cal:
  print('Calibrating ADCs')
  [ ADC.run_DVW_calibration() for ADC in mydesign.ADCs ]
  [ ADC.print_DVW_calibration() for ADC in mydesign.ADCs ]
  print('Done')



Nfft = 4096
nof_lanes = 8

mydesign.feed = 'BF'
# mydesign.feed = 'HF'

[ ADC.get_snapshot() for ADC in mydesign.ADCs ]
fig, axs = plt.subplots(nrows = len(mydesign.ADCs), 
                        ncols = 3,
                        sharex='col', sharey='col',
                        )

for ADC_axs, ADC in zip(axs, mydesign.ADCs):
    ADC_wave = ADC.wave.copy()

    Nech_to_plot = 16384
    ADC_axs[0].plot(np.arange(Nech_to_plot) / Fe * 1e6,
                    ADC_wave[:Nech_to_plot],
                    label=ADC.name)

    cnt, bins, _ = ADC_axs[1].hist(ADC.wave, bins=np.arange(-128, 129) - 0.5)

    nof_samples = len(ADC_wave)
    f = np.arange(Nfft/2+1, dtype='float') / Nfft * Fe /1e6 
    w = np.blackman(Nfft)
    ADC_wave.shape = ((-1, Nfft))
    DATA = np.fft.rfft(w * ADC_wave, axis=-1)
    DATA = DATA.real**2 + DATA.imag**2
    DATA = DATA.mean(axis=0)
    ADC_axs[2].plot(f,
                    10*np.log10(DATA),
                    label=ADC.name)

ADC_axs[0].set_xlabel(u"Time (us)")
ADC_axs[0].set_xlim((0, (Nech_to_plot-1) / Fe * 1e6))
ADC_axs[1].set_xlabel("ADC code")
ADC_axs[1].set_xlim(bins[[0, -1]])
ADC_axs[2].set_xlabel("Frequency (MHz)")
ADC_axs[2].set_xlim((0, f[-1]))

[ ADC_axs[0].set_ylabel("ADC code\nin [-128, 128[") for ADC_axs in axs ]
[ ADC_axs[1].set_ylabel("Counts") for ADC_axs in axs ]
[ ADC_axs[2].set_ylabel("Power (dB)") for ADC_axs in axs ]

plt.tight_layout()
plt.show(block=False)


print('SEFRAM Configuration')

mydesign.SEFRAM.disable()
mydesign.cnt_rst()
time.sleep(0.2)



Nspec_per_sec = mydesign.SEFRAM.Fe / mydesign.SEFRAM.Nfft
acc_len = int(Nspec_per_sec // 10)
mydesign.SEFRAM.acc_len = acc_len

print('vacc_n_frmr_acc_cnt = ', mydesign.SEFRAM.acc_cnt)

fft_shift_reg = 0xfff
mydesign.SEFRAM.fft_shift = fft_shift_reg
print('FFT gain =  = ', mydesign.SEFRAM.fft_gain)

mydesign.SEFRAM.dst_addr = ("192.168.41.1", 0xcece)
mydesign.SEFRAM.IFG = 100000
mydesign.SEFRAM.print_datarate()

# fpga.write_int('vacc_n_frmr_pcktizer_ADC_freq', int(Fe), blindwrite=True)
# set during SEFRAM instanciation

# mydesign.SEFRAM.ID = 0xcece
# set in SEFRAM constructor


mydesign.SEFRAM.arm()



print('Wait for half second and arm PPS_trigger')
mydesign.arm_PPS()
mydesign.monitor()

print('Started!!!')
time.sleep(1)
mydesign.monitor()
time.sleep(1)
mydesign.monitor()


mydesign.monitor()

# after dummy frame, allow outputing data and starting framer 
mydesign.SEFRAM.enable()

mydesign.SEFRAM.time = "now"  # set time to current UNIX timestamp
print(mydesign.SEFRAM.time)


time.sleep(1)
mydesign.monitor()
time.sleep(1)
mydesign.monitor()
time.sleep(1)
mydesign.monitor()
time.sleep(1)


plt.show()



