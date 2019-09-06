# NRT_2G_channelizer



## Requirements

python==2.7


## Installation

### Valon synthesizer

```
$ cd ValonSynth
$ python setup.py build
$ python setup.py install
```

### casperfpga

```
$ source activate 2point7
$ git clone https://github.com/casper-astro/casperfpga/tree/tutorial2019 # (git hash: 08f8f7b17b)
$ cd casperfpga
$ pip install -r requirements.txt
$ python setup.py install
```

### Install TFTP+DHCP+NFS server
- Adapt setup instructions for DHCP+TFTP+NFS from https://docs.google.com/a/ska.ac.za/document/d/1tqw4C6uZ6EULl1OykTFL_vQTnK52UBr0aYqTg44E5wg, sections k, l, m.

```
git clone https://github.com/casper-astro/roach2_nfs_uboot
cd roach2_nfs_uboot
sudo -i
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
roach2/current:
bin  boffiles  boot  dev  etc  home  initrd  lib  lib64  media  mnt  opt  persistent  proc  root  sbin  selinux  srv  sys  tmp  usr  var

roach2/squeeze_root.ppc:
bin  boffiles  boot  dev  etc  home  initrd  lib  lib64  media  mnt  opt  persistent  proc  root  sbin  selinux  srv  sys  tmp  usr  var

tftpboot/uboot-roach1:
uboot-2010-07-15-r3231-dram  uboot.bin  uImage  uImage-jiffy  uImage.OK

tftpboot/uboot-roach2:
roach2-root-2012-10-18.romfs  romfs  u-boot.bin  u-boot-r2-rev1.bin  u-boot-r2-rev2.bin  uImage-r2borph3  uImage-r2borph3-ga8da6b6  uImage-r2borph3-gca140cd


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

#dhcp-option=net:roach1,option:root-path,"192.168.40.1:/home/nfs/roach1/current,nolock"
dhcp-option=net:roach2,option:root-path,"192.168.40.1:/home/nfs/roach2/current,nolock"

#dhcp-boot=net:roach1,uboot-roach1/uImage,192.168.40.1
dhcp-boot=net:roach2,uboot-roach2/uImage-r2borph3,192.168.40.1

enable-tftp
tftp-root=/home/nfs/tftpboot

dhcp-leasefile=/var/lib/misc/dnsmasq.leases
#dhcp-authoritative


root@nanunib:/home/nfs# more /etc/exports
/home/nfs	192.168.40.0/24(rw,subtree_check,no_root_squash)
```



## Configure ROACH2

```
$ source activate 2point7
$ cd scripts
$ ./NRT_2G_config.py
```
