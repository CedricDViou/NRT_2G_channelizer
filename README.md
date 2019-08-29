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

### Update ROACH-2 system
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

## Configure ROACH2

```
$ source activate 2point7
$ cd scripts
$ ./NRT_2G_config.py
```
