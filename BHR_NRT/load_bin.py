#!/usr/bin/env python

import numpy as np
import BHR_NRT
import matplotlib.pyplot as plt
from pathlib import Path
from tqdm import tqdm

dump = Path('./chan1_1-70MHz.bin')
dump = Path('./chan2_15-140MHz.bin')
dump = Path('./chan51_1200-1600MHz.bin')
dump = Path('./1648310964.8352778.bin')

header_size = 64    # bytes
CEP_FRAME_MAX_SIZE    = 8192 + header_size

with dump.open('rb') as fid:
  dat = fid.read(CEP_FRAME_MAX_SIZE)
  header = BHR_NRT.parse_header(dat)

Fe = header['Fe']
assert len(header['conf']['chans']) == 1, "only supporting 1 channel for now" 
chan_idx = header['conf']['chans'][0]

nof_beamlets_per_bank = 2048
RF_BW = Fe/2 // 1e6
nof_chans = 64
RF_BW_chan = 1800 / nof_chans
df = np.arange(-nof_beamlets_per_bank/2, nof_beamlets_per_bank/2) / nof_beamlets_per_bank * RF_BW_chan
f0 = RF_BW_chan * chan_idx
f = df + f0
nof_ticks = 16
tick_space = nof_beamlets_per_bank // nof_ticks
f_ticks = f[::tick_space]
w = np.hamming(nof_beamlets_per_bank)

dat = np.memmap(dump, dtype=BHR_NRT.dt_packet)
data = dat['PAYLOAD'].copy()
data = data.astype('float32').view('complex64').squeeze()

DATA = np.fft.fft(w[None, :, None] * data, axis=1)
P_DATA = 10 * np.log10( DATA.real**2 + DATA.imag**2 )
P_DATA = np.fft.fftshift(P_DATA, axes=1)


fig, axs = plt.subplots(2, 2, figsize=(20,20))
axs[0,0].imshow(P_DATA[:,:,0], extent=(f[0], f[-1], 1, 0))
axs[0,1].imshow(P_DATA[:,:,1], extent=(f[0], f[-1], 1, 0))
axs[0,0].axis('tight')
axs[0,1].axis('tight')
axs[0,0].set_xlabel('Frequency (MHz) of chan %d' % chan_idx)
axs[0,1].set_xlabel('Frequency (MHz) of chan %d' % chan_idx)
axs[0,0].set_ylabel('Time during frequency scan')
axs[0,1].set_ylabel('Time during frequency scan')


# Find and compute enveloppe

# Save center channel
center_chans = slice(1022, 1027)
DC = P_DATA[:, center_chans, :].copy()
# Set center channel to 0 to get all max not related to it
P_DATA[:, center_chans, :] = 0

fmax0 = np.argmax(P_DATA[:,:,0], axis=1)
fmax1 = np.argmax(P_DATA[:,:,1], axis=1)
Amax0 = P_DATA[np.arange(len(fmax0)), fmax0, 0]
Amax1 = P_DATA[np.arange(len(fmax1)), fmax1, 1]

# restore DC for display
P_DATA[:, center_chans, :] = DC

# Substract max to get "dBc"
G_max = P_DATA.flatten().max()

axs[1,0].plot(f, P_DATA[:10,:,0].T-G_max, 'k')
axs[1,0].plot(f[fmax0], Amax0-G_max, '.')
axs[1,1].plot(f, P_DATA[:10,:,1].T-G_max, 'k')
axs[1,1].plot(f[fmax1], Amax1-G_max, '.')
axs[1,0].set_xlabel('Frequency (MHz) of chan %d' % chan_idx)
axs[1,1].set_xlabel('Frequency (MHz) of chan %d' % chan_idx)
axs[1,0].set_ylabel('PFB gain (dB)')
axs[1,1].set_ylabel('PFB gain (dB)')
axs[1,0].grid('on')
axs[1,1].grid('on')

fig.suptitle(dump.as_posix())
fig.savefig(dump.with_suffix('.png'))

plt.show()


