#!/usr/bin/env python3.8

###############################################################################
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
###############################################################################
# Author: Cedric Viou (Cedric.Viou@obs-nancay.fr)
#
# Description:
# Random capture of packets from ROACH2 and display
#
###############################################################################


import pcapy
import impacket.ImpactDecoder as Decoders
import impacket.ImpactPacket as Packets
import BHR_NRT
import numpy as np
import matplotlib.pyplot as plt
import tqdm



pcap_file = "/home/cedric/nancay/Spectro_NRT/NRT_2G_spectrometer/BHR_NRT/carri/ens7f0np0_2024-10-14T08:24:04+0000.pcap"
pcap_file = "/home/cedric/nancay/Spectro_NRT/NRT_2G_spectrometer/BHR_NRT/carri/ens7f1np1_2024-10-14T08:24:40+0000.pcap"
#pcap_file = "/home/cedric/nancay/Spectro_NRT/NRT_2G_spectrometer/BHR_NRT/carri/tcpdump_ens7f1np0_counter.pcap"


eth_decoder = Decoders.EthDecoder()
ip_decoder = Decoders.IPDecoder()
udp_decoder = Decoders.UDPDecoder()

TenGbE_id = 4
src_addr = [( "192.168.5.20", 10000),
            ( "192.168.5.21", 10001),
            ( "192.168.5.22", 10002),
            ( "192.168.5.23", 10003),
            ( "192.168.5.24", 10004),
            ( "192.168.5.25", 10005),
            ( "192.168.5.26", 10006),
            ( "192.168.5.27", 10007),
            ]


def extract_UDP(payload, verbose=False):
    ethernet = eth_decoder.decode(payload)
    if ethernet.get_ether_type() == Packets.IP.ethertype:
        ip = ip_decoder.decode(payload[ethernet.get_header_size():])
        if ip.get_ip_p() == Packets.UDP.protocol: 
            udp = udp_decoder.decode(
                payload[ethernet.get_header_size()+ip.get_header_size():])
            if verbose:
                print("IPv4 UDP packet %s:%d->%s:%d" % (ip.get_ip_src(),
                                                        udp.get_uh_sport(),
                                                        ip.get_ip_dst(),
                                                        udp.get_uh_dport()))
            if ((ip.get_ip_src(), udp.get_uh_sport()) == src_addr[TenGbE_id]):
              return (ethernet, ip, udp)
    return (None,)*3
    
pkt_dtype = 'int8'
nof_samples_per_packet = 16
nof_chans_per_packet = 128
nof_pols = 2
ReIm = 2
def extract_samples(payload, verbose=False):
    (ethernet, ip, udp) = extract_UDP(payload, verbose=verbose)
    if udp is not None:
        spead = payload[  ethernet.get_header_size()
                        + ip.get_header_size()
                        + udp.get_header_size():]
        spead_header = BHR_NRT.parse_header(spead)
        spead_payload = payload[  ethernet.get_header_size()
                                + ip.get_header_size()
                                + udp.get_header_size()
                                + BHR_NRT.dt_SPEAD_header.itemsize:]
        
        dat = np.frombuffer(spead_payload, dtype=pkt_dtype)
        dat.shape = (nof_samples_per_packet,
                     nof_chans_per_packet,
                     nof_pols,
                     ReIm)
        return dat
    return None


def extract_SPEAD_header(payload, verbose=False):
    (ethernet, ip, udp) = extract_UDP(payload, verbose=verbose)
    if udp is not None:
        spead = payload[  ethernet.get_header_size()
                        + ip.get_header_size()
                        + udp.get_header_size():]
        return BHR_NRT.parse_header(spead)
    return None


# get data stream content to compute array sizes
reader = pcapy.open_offline(pcap_file)

dat = None
while dat is None:
    (header, payload) = reader.next()
    dat = extract_samples(payload)
    SPEAD_header = extract_SPEAD_header(payload)
smpl_per_frm, nof_chan, nof_pols, ReIm = dat.shape


# Count the number of recorded frames (for an estimation of the full processing)
reader = pcapy.open_offline(pcap_file)
pkt_cnt = 0
heap_ids = []
header = True
while True:
    (header, payload) = reader.next()
    if header is None:
        break
    SPEAD_header = extract_SPEAD_header(payload)
    if SPEAD_header is not None:
        heap_ids.append(SPEAD_header['heap_id'])
        pkt_cnt += 1
heap_ids = np.array(heap_ids, dtype=np.uint64)
heap_ids.sort()
first_pck = heap_ids.min()
last_pck = heap_ids.max()
# limit processing to first pkt_cnt packets
#last_pck = first_pck + 1000

pck_range = int(last_pck - first_pck + np.uint64(1))

# allocate buffer to reorder and store incoming packets
ingest_buffer = np.zeros((pck_range, smpl_per_frm, nof_chan, nof_pols, ReIm), dtype=pkt_dtype)

reader = pcapy.open_offline(pcap_file)
header = True
while True:
    (header, payload) = reader.next()
    if header is None:
        break
    SPEAD_header = extract_SPEAD_header(payload)
    if SPEAD_header is not None:
        dat = extract_samples(payload)
        pck_idx = SPEAD_header['heap_id'] - first_pck
        ingest_buffer[pck_idx] = dat

nof_samples = pck_range * smpl_per_frm
ingest_buffer.shape = (nof_samples, nof_chan, nof_pols, ReIm)

#plt.figure()
#plt.hist(dat.flatten())
#
#plt.figure()
#plt.plot(ingest_buffer[:10000,0,0,0])


#plt.figure()
#plt.imshow(ingest_buffer[:,:,0,0], aspect='auto', interpolation='nearest')
#plt.figure()
#plt.imshow(ingest_buffer[:,:,0,1], aspect='auto', interpolation='nearest')
#plt.figure()
#plt.imshow(ingest_buffer[:,:,1,0], aspect='auto', interpolation='nearest')
#plt.figure()
#plt.imshow(ingest_buffer[:,:,1,1], aspect='auto', interpolation='nearest')
#
#spec = (ingest_buffer.astype(np.float32)**2).sum(axis=-1)
#plt.figure()
#plt.imshow(spec[:,:,0], aspect='auto', interpolation='nearest')
#plt.figure()
#plt.imshow(spec[:,:,1], aspect='auto', interpolation='nearest')
#
#accumulated_spec = spec.sum(axis=0)
#plt.figure()
#plt.plot(accumulated_spec[:,0])
#plt.plot(accumulated_spec[:,1])

# tcpdump periodically loose data block (about 10 in a row) and then data is contiguous for almost 58 packets
# So, after each data loss try to get 16 packets in a row to get 16*16=256 samples for FFT
ingest_buffer.shape = (pck_range, smpl_per_frm, nof_chan, nof_pols, ReIm)


def detect_blocks(arr, block_length=16):
    block_starts = []
    start = None

    for i in np.arange(1, len(arr)):
        if arr[i] == arr[i-1] + 1:
            if start is None:
                start = arr[i-1]  # Mark the start of the range
        else:
            if start is not None:
                length = arr[i-1] - start + 1
                # Add blocks of exactly 16 values
                while length >= block_length:
                    block_starts.append(start)
                    start += block_length  # Move to the next block
                    length -= block_length
                start = None

    # Check for the last sequence
    if start is not None:
        length = arr[-1] - start + 1
        while length >= block_length:
            block_starts.append(start)
            start += block_length
            length -= block_length

    return block_starts


nof_contiguous_pck = 16
starts_of_contiguous_area = detect_blocks(heap_ids, block_length=nof_contiguous_pck)
contiguous_data = np.zeros((len(starts_of_contiguous_area), nof_contiguous_pck, smpl_per_frm, nof_chan, nof_pols, ReIm), dtype=pkt_dtype)
# plt.figure()
# plt.plot(heap_ids, np.zeros_like(heap_ids), '.k')
for idx, start in enumerate( starts_of_contiguous_area):
    first_packet_of_block = np.where(heap_ids == start)[0][0]
    # print(idx, start-first_pck, start-first_pck+nof_contiguous_pck, first_packet_of_block, first_packet_of_block+nof_contiguous_pck)
    contiguous_data[idx, ...] = ingest_buffer[first_packet_of_block:first_packet_of_block+nof_contiguous_pck, ...]
    pkt_range = np.arange(start-first_pck, start-first_pck+nof_contiguous_pck, dtype=int)
    # plt.plot(heap_ids[first_packet_of_block:first_packet_of_block+nof_contiguous_pck], np.zeros(nof_contiguous_pck), 'o')
# plt.show(block=False)
Nfft = int(nof_contiguous_pck) * smpl_per_frm
contiguous_data.shape = (-1, Nfft, nof_chan, nof_pols, ReIm)
contiguous_data = contiguous_data.astype(np.float32)
contiguous_data = contiguous_data.view('complex64').squeeze()

# Faire TF dans chaque canal pour observer la forme du PFB
DAT = np.fft.fft(contiguous_data, axis=1)
DD = (DAT.real**2 + DAT.imag**2)
DD = DD.sum(axis=0)
DD = np.fft.fftshift(DD, axes=0)
DD = DD.transpose((1,0,2))
DD = DD.reshape((Nfft * nof_chan, nof_pols))

Fe = 3700
nof_TenGbE = 8
nof_chans = 1024
# center frequency of subbands
K0 = np.arange(nof_chans / nof_TenGbE) + TenGbE_id*nof_chans/nof_TenGbE
F0 = K0 / nof_chans * Fe/2
# relative frequency within the subbands
k0 = (np.arange(Nfft) - Nfft/2)
f0 = k0 / Nfft * Fe/2/nof_chans
f = F0[:, None] + f0[None, :]
f.shape = (-1)

plt.figure()
plt.plot(f, 10*np.log10(DD))
plt.xlim((f[0], f[-1]))
plt.ylim((70, 120))
plt.gca().set_position([0, 0.1, 1, 0.9])
plt.show(block=False)
1/0

nof_chans = 64
Fe = SPEAD_header['Fe']
RF_BW_chan = Fe/2/1e6 / nof_chans
df = np.arange(-smpl_per_frm/2, smpl_per_frm/2) / smpl_per_frm * RF_BW_chan
f0 = np.array(SPEAD_header['conf']['chans']) * RF_BW_chan
f = df[None, :] + f0[:, None]
nof_ticks = 14
tick_space = smpl_per_frm // nof_ticks


w = np.hamming(smpl_per_frm)[None,:,None]
acced_DAT = np.zeros((nof_chan, smpl_per_frm, nof_pols), dtype='float64')


# extract and accumulate spectrae
reader = pcapy.open_offline(pcap_file)
header = True
for pkt in tqdm.tqdm(range(pkt_cnt)):
    try:
        (header, payload) = reader.next()
        dat = extract_samples(payload)
        if dat is not None:
            DAT = numpy.fft.fft(w * dat, axis=1)
            acced_DAT += (DAT.real**2 + DAT.imag**2)

    except pcapy.PcapError:
        break


# make dB and plot
acced_DAT_dB = 10 * np.log10( acced_DAT)
acced_DAT_dB = np.fft.fftshift(acced_DAT_dB, axes=1)

for chan in range(nof_chan):
    plt.figure()
    dat = acced_DAT_dB[chan, ...]
    med_value = np.median(dat.flatten())
    plt.plot(f[chan], dat[:,0])
    plt.plot(f[chan], dat[:,1])
    f_ticks = list(f[chan,::tick_space])
    f_ticks.append(f[chan,-1])
    plt.xlim((f[chan,0], f[chan,-1] + (f[chan,-1]-f[chan,-2])))
    plt.xticks(f_ticks)
    plt.ylim((med_value-2, med_value+2))
    plt.xlabel('Freq (MHz)')
    plt.ylabel('Power (dB)')
    

plt.show()



