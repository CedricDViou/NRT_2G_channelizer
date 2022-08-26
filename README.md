# NRT_2G_channelizer



## Requirements

- Fresh Ubuntu 18.04.5 LTS install
- python==2.7


## Installation

### Get sources

```
$ git clone --recurse-submodules https://github.com/CedricDViou/NRT_2G_channelizer.git
```
or
```
$ git clone https://github.com/CedricDViou/NRT_2G_channelizer.git
$ git submodule init
$ git submodule update
```

### Valon synthesizer

Install with:
```
$ sudo pip install pyserial   # NOT serial
$ cd ValonSynth
$ python setup.py build
$ sudo python setup.py install
$ sudo usermod -a -G dialout $USER
```

Test with:
```
$ ipython
In [1]: import valon_synth
In [2]: S = valon_synth.Synthesizer('/dev/ttyUSB0')
In [3]: FA = S.get_frequency(valon_synth.SYNTH_A)
In [4]: print(FA)
2000.0   # or something else...
```

### Power on ROACH2

- Connect USB cable to "FTDI USB" of the ROACH2
- run terminal with 115200 8N1, "Hardware Flow Control" = No
```
$ minicom -D /dev/ttyUSB3
```
- You should see the boot sequence:
```
U-Boot 2011.06-rc2-00000-g2694c9d-dirty (Dec 04 2013 - 20:58:06)

CPU:   AMCC PowerPC 440EPx Rev. A at 533.333 MHz (PLB=133 OPB=66 EBC=66)
       No Security/Kasumi support
       Bootstrap Option C - Boot ROM Location EBC (16 bits)
       32 kB I-Cache 32 kB D-Cache
Board: ROACH2
I2C:   ready
DRAM:  512 MiB
...

```

More docs on:
- https://casper.astro.berkeley.edu/wiki/Getting_Started_with_ROACH2
- https://casper.astro.berkeley.edu/wiki/ROACH_NFS_guide


### casperfpga

Install with:
```
$ git clone https://github.com/casper-astro/casperfpga  # commit 0fed055d1c62a93dff68afec32b0c9ada776b07d
$ cd casperfpga
$ git checkout master
$ sudo apt-get install python-pip
$ sudo pip install -r requirements.txt
$ sudo python setup.py install
```

Test with:
```
$ ipython
In [1]: import casperfpga

In [2]: casperfpga.__version__
Out[2]: '0.0+unknown.202108240911'
```

Little endian detection is broken for ROACH2:

- Add ```fpga.is_little_endian = False``` after programming


### ADC5G drivers

```
$ git clone https://github.com/CedricDViou/adc5g_devel
$ cd adc5g_devel
$ python setup install
```


### Install TFTP+DHCP+NFS server
- Adapt setup instructions for DHCP+TFTP+NFS from https://docs.google.com/a/ska.ac.za/document/d/1tqw4C6uZ6EULl1OykTFL_vQTnK52UBr0aYqTg44E5wg, sections k, l, m.

```
git clone https://github.com/ska-sa/roach2_nfs_uboot
sudo -i
cd /home/cedric/roach2_nfs_uboot
mkdir -p /home/nfs/roach2
cp -r roach2_nfs_uboot/tftpboot/uboot-roach2 /home/nfs/roach2
mv /home/nfs/roach2/uboot-roach2 /home/nfs/roach2/boot
Download https://drive.google.com/file/d/1vdTiA1MazQ7_HBKMc3J9Hbpync2UWM7w/view?usp=sharing
tar xzvf squeeze_root.ppc.20190202.tar.gz -C /home/nfs/roach2
cd /home/nfs/roach2
ln -s squeeze_root.ppc current
exit sudo (ctrl-d)
```


```
root@nanunib:/home/nfs# ls */*
lrwxrwxrwx  1 root root   16 Sep  3 10:59 roach2/current -> squeeze_root.ppc/
lrwxrwxrwx  1 root root   57 Sep 11 15:23 tftpboot/romfs -> uboot-roach2/roach2-root-phyprog-release-2015-04-01.romfs*
lrwxrwxrwx  1 root root   37 Sep 11 15:23 tftpboot/uImage -> uboot-roach2/uImage-roach2-3.16-hwmon*

roach2/squeeze_root.ppc:
total 104
drwxr-xr-x  2 root root  4096 Feb  2  2019 bin/
...
drwxr-xr-x 11 root root  4096 Nov 17  2012 var/


tftpboot/uboot-roach2:
total 26452
-rwxrwxrwx 1 root root 8674304 Sep 11 15:14 roach2-root-phyprog-release-2015-04-01.romfs*
lrwxrwxrwx 1 root root      44 Sep 11 15:17 romfs -> roach2-root-phyprog-release-2015-04-01.romfs*
lrwxrwxrwx 1 root root      24 Sep 11 15:17 uImage -> uImage-roach2-3.16-hwmon*
-rwxrwxrwx 1 root root 3034268 Sep 11 15:14 uImage-roach2-3.16-hwmon*


root@nanunib:/home/nfs# more /etc/dnsmasq.conf
domain-needed
bogus-priv
filterwin2k


domain=acme.pvt
expand-hosts
local=/pvt/ 

interface=eth1
listen-address=192.168.40.1
bind-interfaces
dhcp-range=eth1,192.168.40.50,192.168.40.99,12h
#dhcp-mac=roach1,02:*:00:*:*:*
dhcp-mac=roach2,02:*:01:*:*:*
read-ethers

dhcp-option=option:router,192.168.40.1
dhcp-option=option:dns-server,192.168.40.1
dhcp-option=option:ntp-server,192.168.40.1

#dhcp-option=net:roach1,option:root-path,"192.168.40.1:/home/nfs/roach1/current"
dhcp-option=net:roach2,option:root-path,"192.168.40.1:/home/nfs/roach2/current"

#dhcp-boot=net:roach1,uboot-roach1/uImage,192.168.40.1
dhcp-boot=net:roach2,uboot-roach2/uImage,192.168.40.1

enable-tftp
tftp-root=/home/nfs/tftpboot

dhcp-leasefile=/var/lib/misc/dnsmasq.leases
#dhcp-authoritative


root@nanunib:/home/nfs# more /etc/exports
/home/nfs	192.168.40.0/24(rw,subtree_check,no_root_squash)
```

- Start dhcp server:
```
cedric@cedric-HP-ZBook-15-G2:~$ sudo /etc/init.d/dnsmasq restart
[sudo] password for cedric: 
[ ok ] Restarting dnsmasq (via systemctl): dnsmasq.service.
```



## Update ROACH2 ROMFS and Image
From https://github.com/ska-sa/roach2_nfs_uboot

- uboot-roach2/roach2-root-phyprog-release-2015-04-01.romfs
- uboot-roach2/uImage-roach2-3.16-hwmon

From roach2 serial console:

- No attemp to update U-Boot
- run tftpkernel
- run tftproot

Versions after upgrade:

- U-Boot 2011.06-rc2-00000-g2694c9d-dirty (Dec 04 2013 - 20:58:06)
- Linux version 3.16.0-saska-03675-g1c70ffc (rijandn@r2d2) (gcc version 4.6.1 20110627 (prerelease) (GCC) ) #3 Tue Aug 26 08:52:14 SAST 2014
- tcpborphserver3 #version 62baddd-dirty #build-state 2015-03-25T11:27:47




## Configure ROACH2

```
$ source activate 2point7
$ cd scripts
$ ./NRT_2G_config.py
```



## Firmware developpement

Start Matlab/Simulink
```
cedric@nanunib:/FAN/HDD2/CASPER$ ./startsg14_7
```

Open project /home/cedric/NRT_channelizer/nrt_spectro.slx

Make your modifications, save.

In transcript, call casper_xps, and click "Run XPS".



## ADC / clocks firmware configuration

- Production
  - MSSGE ROACH2 User IP Rate (MHz) : 256
  - adc5g ADC clock rate (MHz) : 2048
- Test (24/08/2020)
  - MSSGE ROACH2 User IP Rate (MHz) : 64
  - adc5g ADC clock rate (MHz) : 512
- adc_and_regs
  - MSSGE ROACH2 User IP Rate (MHz) : 187.5
  - adc5g ADC clock rate (MHz) : 1500


## RF-10M-PPS input signals


### RF inputs
ADC1x5000-8 ADC boards requires:

- Clock: 2.5GHz (Max) 50Ohm 0dBm into SMA socket 
- Signals: each is single-ended into SMA socket 

Input pathes produce no gain.  Only a pair of baluns are on the way the the ADC chip (symetrification of the signal?).
The ADC chip [documentation](https://casper.ssl.berkeley.edu/wiki/images/1/19/Ev8aq160.pdf) states that Analog input voltages should :

- Common mode within -0.3 - 4.3 V
- Diff mode under 4 Vpp


As a start, for clock and line, we configured Valon 4008 to produce -4 dBm RF levels.
```
Input clock is 2000.000000 MHz, -4.000000 dB (locked)
 =>  Sampling clock is 4000.000000 MHz, -4.000000 dB
Input tone is 250.000000 MHz, -4.000000 dB (locked)
```

An extra 20 dB attenuator is inserted on the ADC input path.


### 10 MHz
Valon 4008 requires 0.2 to 1 Vpk-pk input level.

WR-LEN used for tests produces 2 Vpk-pk input level.

A 3 dB SAM attenuator was inserted on the connection to adapt levels.


### PPS
ADC1x5000-8 ADC boards requires:

- Sync: LVTTL, 5V tolerant, terminated with 50 ohm load, into SMA socket 

WR-LEN generates 1.8V into 50 ohms load.
We connect directly.


## Known issues
netboot fails when claiming access to root dir NFS:
```
[    4.052708] IP-Config: Got DHCP answer from 192.168.40.1, my address is 192.168.40.96
[    4.060868] IP-Config: Complete:
[    4.064129]      device=eth0, hwaddr=02:44:01:02:0e:28, ipaddr=192.168.40.96, mask=255.255.255.0, gw=192.168.40.1
[    4.074429]      host=roach2, domain=acme.pvt, nis-domain=(none)
[    4.080440]      bootserver=192.168.40.1, rootserver=192.168.40.1, rootpath=/home/nfs/roach2/current
[    4.089375]      nameserver0=192.168.40.1
[    4.109532] VFS: Mounted root (nfs filesystem) readonly on device 0:11.
[    4.117171] Freeing unused kernel memory: 300K (805a8000 - 805f3000)
[   19.168478] nfs: server 192.168.40.1 not responding, still trying
[   21.376556] nfs: server 192.168.40.1 not responding, still trying
```

Even if server seems fine with it:
```
Sep 11 15:32:55 nanunib rpc.mountd[15418]: authenticated mount request from 192.168.40.96:741 for /home/nfs/roach2/squeeze_root.ppc (/home/nfs)
```
