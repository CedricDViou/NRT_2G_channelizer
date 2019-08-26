import corr, struct, time

time.sleep(5)

# connect to roach2 named devenvr2-1
fpga=corr.katcp_wrapper.FpgaClient('devenvr2-1',7147)
time.sleep(0.5)

# load the 512 ch version of the bof file
#fpga.progdev('c1500x0512_x14_7_2016_Feb_24_1437.bof')

# Cedric's RFI detection versions
# has bin offset problem
#fpga.progdev('ced_c1500x0512_8bits_2018_Feb_27_2119.bof')
# has bin offset problem
#fpga.progdev('ced_c1500x0512_18bits_2018_Mar_04_0315.bof')

# spectrum offset fixed, but has small timing errors
#fpga.progdev('ced_c1500x0512_18bits_2018_Mar_19_2200.bof')

# spectrum offset fixed, no timing errors
#fpga.progdev('c1500x0512_x14_7_18bits_2018_Apr_06_1843.bof')

# Cedric's bof, built on 08/22/19
# 1024channels, 640MHz BW
fpga.progdev('nrt_spectro_2019_Aug_22_1240.bof')

# first 64 channel version  07/16/18
#fpga.progdev('c1500x0064_x14_7_18bits_2018_Jul_15_1444.bof')

time.sleep(5)

# 10GbE destination IP for HPC machine devenv-hpc1 
#fpga.write_int('ip_0', 10*(2**24)+17*(2**16)+1*(2**8)+46)
fpga.write_int('TenGbE0_dst_ip', 10*(2**24)+17*(2**16)+1*(2**8)+46)

time.sleep(0.5)

# 10GbE port
#fpga.write_int('pt_0', 60000)
fpga.write_int('TenGbE0_dst_port', 60000)
time.sleep(0.5)

fpga.write_int('TenGbE0_hdr_pkt_len_words', 1024)

# 10GbE IP for devenvr2-1
SOURCE_IP=10*(2**24)+17*(2**16)+1*(2**8)+64
time.sleep(0.5)

# roach2 10Gbe configuration stuff
FABRIC_PORT=52000
time.sleep(0.5)
MAC_BASE=(2<<32)+(2<<40)
time.sleep(0.5)

# configure 10GbE transmission for port 0
#fpga.tap_start('tap1','gbe0',MAC_BASE,SOURCE_IP,FABRIC_PORT)
fpga.tap_start('tap1','TenGbE0_ten_Gbe_v2',MAC_BASE,SOURCE_IP,FABRIC_PORT)

time.sleep(0.5)

# interacting with software registers
#fpga.write_int('fftshift',0xAAAAAAAA)
fpga.write_int('fft_shift',0x2AA)

time.sleep(0.5)
#fpga.write_int('scale_p0',0x40000)
fpga.write_int('rescale_pol0_bitselect',0x40000)

time.sleep(0.5)
#fpga.write_int('scale_p1',0x40000)
fpga.write_int('rescale_pol1_bitselect',0x40000)

time.sleep(0.5)
#fpga.write_int('n_chan',9)
time.sleep(0.5)

# configuration for RFI modules

#RFI_modules_ON = False  # data are not processed, 
#but pass through the RFI modules with no modification

#RFI_modules_ON = True
#fpga.write_int('RFI_modules_ON', 0x00000001 if RFI_modules_ON else 0x00000000)
#time.sleep(0.5)


#RFI_modules_mode = 1 # RFI modules replace RFI by 0's
#RFI_modules_mode = 0  # RFI modules replace RFI by random data
#fpga.write_int('RFI_modules_mode', RFI_modules_mode)
#time.sleep(0.5)


#fpga.write_int('RFI_modules_clear', 0x00000001)  # raise clear bit to force power 
						 # estimators to converge on system noise level 
#time.sleep(0.1)                                  
#fpga.write_int('RFI_modules_clear', 0x00000000)  # lower clear bit to let power estimators 
						 # adapt to slow RF power variations

#time.sleep(0.5)                                  # wait for the estimators to converge.  
						 # A few thousands samples is needed.  In a 6.25-MHz 
						 #channels, a few milliseconds are more than enough.  
						 #0.5s is not a problem either.
                                                 # at this point, strong variations in RF levels 
						 #(calibration noise diode, severe telescope 
						 #re-pointing, ...) are not an option.


# arm the system to begin 10GbE transmission
fpga.write_int('reset', 1)
time.sleep(0.5)
fpga.write_int('reset', 0)
time.sleep(0.5)

fpga.write_int('pps_arm', 1)
time.sleep(0.5)
fpga.write_int('pps_arm', 0)
time.sleep(0.5)

