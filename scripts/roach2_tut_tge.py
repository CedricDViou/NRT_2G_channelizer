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


roach2 = "192.168.40.71"
bitstream = "../bof/roach2_tut_tge/bit_files/roach2_tut_tge_2023_Jul_03_1641.fpg"

katcp_port = 7147
dst_ip_base = 192*(2**24) + 168*(2**16) + 5*(2**8) + 180*(2**0)
dst_udp_port_base = 0xcece

conf_Valon = True
conf_FPGA = True
ADC_cal = False
plot_ADC = False


Fe = 3600000000.0 # Hz
F_valon = Fe / 2
Fsys = F_valon / 8
Fin = 130000000# Hz



S = valon_synth.Synthesizer('/dev/ttyUSB_valon')
if conf_Valon:
    print('\nConfiguring Valon:')
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

print('\nConnecting to server %s on port %i... ' % (roach2, katcp_port))
fpga = casperfpga.CasperFpga(roach2)
time.sleep(0.2)


assert fpga.is_connected(), 'ERROR connecting to server %s on port %i.\n' % (roach2, katcp_port)

if conf_FPGA:
    print('------------------------')
    print('Programming FPGA with %s...' % bitstream)
    sys.stdout.flush()
    fpga.upload_to_ram_and_program(bitstream)
    print('done')


dev = fpga.listdev()
for d in dev:
    print(d)


monitoring_regs = (
                   'gbe0_linkup',
                   'gbe1_linkup',
                   'gbe0_rxbadctr',
                   'gbe1_rxbadctr',
                   'gbe0_rxctr',
                   'gbe1_rxctr',
                   'gbe0_rxeofctr',
                   'gbe1_rxeofctr',
                   'gbe0_rxofctr',
                   'gbe1_rxofctr',
                   'gbe0_rxvldctr',
                   'gbe1_rxvldctr',
                   'gbe0_tx_cnt',
                   'gbe1_tx_cnt',
                   'gbe0_txctr',
                   'gbe1_txctr',
                   'gbe0_txfullctr',
                   'gbe1_txfullctr',
                   'gbe0_txofctr',
                   'gbe1_txofctr',
                   'gbe0_txvldctr',
                   'gbe1_txvldctr',
                   'gbe0_rx_frame_cnt',
                   'gbe1_rx_frame_cnt',
                   'tx_afull0',
                   'tx_overflow0',
                   'tx_afull1',
                   'tx_overflow1',
                   )

def monitor():
    for reg in monitoring_regs:
        print(reg, fpga.read_uint(reg))

if ADC_cal:
    # Calibrate ADC DVW
    # from https://github.com/Smithsonian/adc_tests
    # forked here https://github.com/CedricDViou/adc_tests
    print('\nCalibrating ADCs')
    # define get_snapshot as we don't have it available in our casperfpga lib version
    def get_snapshot(roach, snap_name, bitwidth=8, man_trig=True, wait_period=2):
        """
        Reads a one-channel snapshot off the given 
        ROACH and returns the time-ordered samples.
        USN version
        """
    
        grab = roach.snapshots[snap_name].read_raw(man_trig=True)[0] 
        data = struct.unpack('%ib' %grab['length'], grab['data'])
    
        return data

    # overload adc5g get_snapshot
    adc5g.tools.get_snapshot = get_snapshot
    
    adc5g.tools.set_test_mode(fpga, 0)
    adc5g.tools.set_test_mode(fpga, 1)
    opt0, glitches0 = adc5g.tools.calibrate_mmcm_phase(fpga, 0, ['ADC_wave0',])
    opt1, glitches1 = adc5g.tools.calibrate_mmcm_phase(fpga, 1, ['ADC_wave1',])
    adc5g.tools.unset_test_mode(fpga, 0)
    adc5g.tools.unset_test_mode(fpga, 1)
    
    print(adc5g.tools.pretty_glitch_profile(opt0, glitches0))
    print(adc5g.tools.pretty_glitch_profile(opt1, glitches1))
    print('Done')


if plot_ADC:
    Nfft = 4096
    nof_lanes = 8
    
    adc_wave_snapshots = [v for v in fpga.snapshots if 'adc_wave' in v.name.lower()]
    adc_wave_snapshots.sort(key=lambda x:x.name)
    for snapshot in adc_wave_snapshots:
        data = snapshot.read_raw(man_valid=True, man_trig=True)
        data = np.frombuffer(data[0]['data'], dtype='int8')
    
        plt.figure(1)
        Nech_to_plot = 1000
        plt.plot(np.arange(Nech_to_plot) / Fe,
                 data[:Nech_to_plot],
                 label=snapshot.name)
    
        plt.figure(2)
        nof_samples = len(data)
        f = np.arange(Nfft/2+1, dtype='float') / Nfft * Fe /1e6 
        w = np.blackman(Nfft)
        data.shape = ((-1, Nfft))
        DATA = np.fft.rfft(w * data, axis=-1)
        DATA = DATA.real**2 + DATA.imag**2
        DATA = DATA.mean(axis=0)
        plt.plot(f,
                 10*np.log10(DATA),
                 label=snapshot.name)
    
        data.tofile(snapshot.name + "_adc_data.bin")
    
    plt.figure(1)
    plt.legend()
    plt.figure(2)
    plt.legend()
    plt.show()



print('Resetting cores and counters...')
fpga.write_int('pkt_sim0_enable', 0)
fpga.write_int('pkt_sim1_enable', 0)
fpga.write_int('rst', 3)
fpga.write_int('rst', 0)



# configure frame generator
pkt_period = 2048  #how often to send another packet in FPGA clocks (225MHz)
payload_len = 1024   #how big to make each packet in 64-bit words.  MTU should be set to 9000 for large frames

fpga.write_int('pkt_sim0_period',pkt_period)
fpga.write_int('pkt_sim0_payload_len',payload_len)
fpga.write_int('pkt_sim1_period',pkt_period)
fpga.write_int('pkt_sim1_payload_len',payload_len)

fabric_port= 60000         
mac_base= 0x192168005000
ip_base = 192*(2**24) + 168*(2**16) + 5*(2**8)


gbe0, gbe1 = fpga.gbes
# This is not working -> still using the MAC/IP defined during synthesys
# gbe0.setup(mac_base+13, ip_base+13, fabric_port)
# gbe1.setup(mac_base+16, ip_base+16, fabric_port)

macs = list(mac_base+np.arange(256))
macs_pack = struct.pack('>%dQ' % (len(macs)), *macs)
# Read back for verification fails
# gbe0.set_arp_table(macs)
# gbe1.set_arp_table(macs)
# -> perform blind write instead
fpga.blindwrite('gbe0', macs_pack, 0x3000)
fpga.blindwrite('gbe1', macs_pack, 0x3000)


if False:    # configure 10G to stream gbe0 toward gbe1 and gbe1 toward gbe0
    fpga.write_int('dst_ip0', ip_base+2, blindwrite=True)
    fpga.write_int('dst_ip1', ip_base+1, blindwrite=True)
    fpga.write_int('dst_port0',10052)
    fpga.write_int('dst_port1',10051)

if True:    # configure 10G to have gbe0 and gbe1 stream data to themselves
    fpga.write_int('dst_ip0', ip_base+1, blindwrite=True)
    fpga.write_int('dst_ip1', ip_base+2, blindwrite=True)
    fpga.write_int('dst_port0',10051)
    fpga.write_int('dst_port1',10052)



fpga.write_int('rst', 3)
fpga.write_int('rst', 0)

# start frame generator
fpga.write_int('pkt_sim0_enable', 1)
fpga.write_int('pkt_sim1_enable', 1)



monitor()
print('Started!!!')
for i in range(10):
    time.sleep(0.1)
    monitor()



print("          param: gbe0, gbe1")
for k in gbe0.block_info.keys():
    print("%15s: %5s, %5s" % (k, gbe0.block_info[k], gbe1.block_info[k]))

gbe0_core_details = gbe0.get_gbe_core_details()
gbe1_core_details = gbe1.get_gbe_core_details()
print("          param: gbe0, gbe1")
for k in gbe0_core_details:
    print("%15s: %5s, %5s" % (k, gbe0_core_details[k], gbe1_core_details[k]))

if False:
    print(gbe0.print_gbe_core_details())
    print(gbe1.print_gbe_core_details())
    
    print(gbe0.get_arp_details())
    print(gbe1.get_arp_details())
    print(gbe0.get_cpu_details())
    print(gbe1.get_cpu_details())
    
    
    fpga.snapshots['gbe0_rxs_ss'].read(timeout=10)
    fpga.snapshots['gbe1_rxs_ss'].read(timeout=10)
    
    gbe0.read_counters()
    gbe0.rx_okay()
  
