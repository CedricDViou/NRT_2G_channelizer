"""
Channelizer class.
"""


import numpy as np
import scipy.signal
import scipy.fft
import matplotlib.pyplot as plt
from matplotlib.ticker import LinearLocator
from matplotlib import cm


class Channelizer(object):
    """
    Channelizer object.
    \param filter_coeffs: Filter coefficient array.
    """

    _nof_branch: int
    _nof_taps: int
    _filter_coeffs: np.ndarray

    _L0: np.ndarray
    _L0_nof_substeps: int

    def __init__(
            self, 
            filter_coeffs: np.ndarray,
            nof_branch: int = 8,
            nof_taps: int = 5,
            nof_substeps: int = 4,
            ):

        assert  isinstance(nof_branch, int)
        assert  isinstance(nof_taps, int)
        assert len(filter_coeffs) == nof_branch * nof_taps
        
        self._nof_branch = nof_branch
        self._nof_taps = nof_taps

        self._filter_coeffs = filter_coeffs
        #self._filter_branches = np.reshape(filter_coeffs, (self._nof_taps, self._nof_branch)).T
        self._filter_branches = self._filter_coeffs.copy()
        self._filter_branches.shape = (self._nof_taps, self._nof_branch)
        self._filter_branches = self._filter_branches.T

        self._L0_nof_substeps = nof_substeps


    def generate_L0(self, k, with_index=False):
        decimate_by = self._nof_branch
        nof_substeps = self._L0_nof_substeps
        assert 0 <= k < decimate_by, f"k should be in [0, {decimate_by}["

        n = np.arange(decimate_by*nof_substeps).reshape((nof_substeps, -1))
        self._L0 = np.exp(2j*np.pi*k*n/decimate_by).reshape((nof_substeps, -1))
        if with_index:
            return n


    def plot_L0(self, nof_steps_to_plot = 6):
        decimate_by = self._nof_branch
        nof_substeps = self._L0_nof_substeps
        nof_steps = decimate_by * nof_substeps

        colors = (('b','r'),('g','k'))
        fig, axs = plt.subplots(nof_steps_to_plot, sharex=True, sharey=True, figsize=(6,12))
        fig.tight_layout()
        for idx, k in enumerate(np.arange(0, decimate_by, 1/nof_substeps)):
            if idx == nof_steps_to_plot:
                break
            n_table = self.generate_L0(k, with_index=True)
            for substep_idx in range(nof_substeps):
                n = n_table[substep_idx]
                L0 = self._L0[substep_idx]
                axs[idx].plot(n, L0.real, 'o' + colors[substep_idx%2][0],
                              n, L0.imag, '+' + colors[substep_idx%2][1],
                              )
            axs[idx].set_xlim(0, decimate_by * nof_substeps)
            axs[idx].set_ylim(-1.2, 1.2)
            axs[idx].grid('on')
            axs[idx].set_xticks(np.arange(0, nof_steps+1, decimate_by))
            axs[idx].set_ylabel(f"{k=}")


    def freqz(self, N: int = -1) -> np.ndarray:
        """
        Compute the frequency response of the prototype filter.
        """

        if N == -1:
            N = self._filter_coeffs.size * 100
        
        w, H = scipy.signal.freqz(self._filter_coeffs,
                                  worN=N,
                                  whole=True)
        return w, H


    def filterbank_freqz(self, N: int = -1) -> np.ndarray:
        """
        Compute the frequency response of each channel.

        Parameters:
        ----------

        N : the number of sample point.

        Return:
        -------
            a: Amplitude in dB.
            f: Digital frequence point.

        """
        assert isinstance(N, int)

        if N == -1:
            N = self._filter_coeffs.size * 100
        
        w, H = self.freqz(N=N)
        H_k = np.empty((self._nof_branch, len(H)), dtype=H.dtype)
        chan_spacing = N // self._nof_branch
        for k in range(self._nof_branch):
            H_k[k, ...] = np.roll(H, k * chan_spacing)
        return w, H_k
    

    def basic_single_filter(self, input_data):
        filtered_data = scipy.signal.lfilter(self._filter_coeffs, 1, input_data)
        return filtered_data


    def polyphase_single_filter(self, input_data, k=0):
        decimate_by = self._nof_branch
        nof_substeps = self._L0_nof_substeps
        assert 0 <= k < decimate_by, f"k should be in [0, {decimate_by}["
        assert nof_substeps == 1, "only integer channels supported here"

        round_factor = decimate_by * nof_substeps
        input_data = input_data[:len(input_data) // round_factor * round_factor] # truncate data to multiple number of samples used for processing
        parallel_data = input_data.reshape((-1, decimate_by))                    # distribute input samples to the decimate_by branches
        parallel_data = np.transpose(parallel_data, axes=(1, 0))
        parallel_data = np.flip(parallel_data, axis=(0))                         # first sample goes to the last branch
        filtered_data = np.asarray(                                              # filter each branch by own sub-filter
            [scipy.signal.lfilter(self._filter_branches[branch, :], 1, parallel_data[branch,:])
                for branch in range(decimate_by) ]
                )
        self.generate_L0(k)
        L0 = self._L0.T
        filtered_data *= L0                                                      # apply phasors
        filtered_data = np.sum(filtered_data, axis=0)                            # sum to get channel k
        return filtered_data


    def polyphase_substep_filter(self, input_data, k=0):
        decimate_by = self._nof_branch
        nof_substeps = self._L0_nof_substeps
        assert 0 <= k < decimate_by, f"k should be in [0, {decimate_by}["

        round_factor = decimate_by * nof_substeps
        input_data = input_data[:len(input_data) // round_factor * round_factor] # truncate data to multiple number of samples used for processing
        parallel_data = input_data.reshape((-1, nof_substeps, decimate_by))      # distribute input samples to the decimate_by branches
        parallel_data = np.transpose(parallel_data, axes=(1, 2, 0))
        parallel_data = np.flip(parallel_data, axis=(1))                         # first sample goes to the last branch
        filtered_data = np.asarray(                                              # filter each branch by own sub-filter
            [ [scipy.signal.lfilter(self._filter_branches[branch, :], 1, parallel_data[substep, branch,:])
                for branch in range(decimate_by) ]
              for substep in range(nof_substeps)]
                )
        self.generate_L0(k)
        L0 = self._L0
        filtered_data *= L0[:,:,None]
        filtered_data = np.transpose(filtered_data, axes=(2, 0, 1))
        filtered_data = np.sum(filtered_data, axis=(-1))                       # sum to get channel k
        filtered_data = filtered_data.reshape((-1))
        return filtered_data


    def polyphase_analysis(self, input_data):
        decimate_by = self._nof_branch
        input_data = input_data[:len(input_data) // decimate_by * decimate_by]
        parallel_data = input_data.reshape((-1, decimate_by)).T                  # distribute input samples to the decimate_by branches
        parallel_data = np.flipud(parallel_data)                                 # first sample goes to the last branch
        filtered_data = np.asarray(                                              # filter each branch by own sub-filter
            [scipy.signal.lfilter(self._filter_branches[branch, :], 1, parallel_data[branch,:])
                for branch in range(decimate_by) ]
                )
        out = np.fft.ifft(filtered_data, n=decimate_by, axis=0)
        return out



def dB(x):
    return 10*np.log10(abs(x))


def gen_complex_chirp(fs=44100):
    Ts = 1 / float(fs)
    f0=-fs/2.1
    f1=fs/2.1
    t1 = 1e-4
    n_samples = t1 / Ts
    beta = (f1-f0)/float(t1)
    t = np.arange(n_samples) * Ts
    return np.exp(2j*np.pi*(.5*beta*(t**2) + f0*t))


if __name__ == "__main__":

    import scipy
    import matplotlib.pyplot as plt

    # Design FIR Filter
    channel_num = 8
    cutoff = 1 / channel_num / 2    # Desired cutoff digital frequency
    trans_width = cutoff / 10  # Width of transition from pass band to stop band
    numtaps = 20      # Size of the FIR filter.
    nof_substeps = 4

    #proto_filter = scipy.signal.remez(numtaps * channel_num, [0, cutoff - trans_width, cutoff + trans_width, 0.5],[1, 0])
    
    DECIMATE_BY = channel_num
    normalized_cutoff = 1./(DECIMATE_BY+.1*DECIMATE_BY)
    proto_filter = scipy.signal.firwin(numtaps * channel_num, normalized_cutoff)
    
    channelizer = Channelizer(proto_filter,
                              nof_branch=channel_num,
                              nof_taps=numtaps,
                              nof_substeps=nof_substeps,
                              )

    plt.figure()
    plt.plot(channelizer._filter_coeffs)
    plt.title('Prototype filter impulse response')
    plt.xlabel('#')
    plt.ylabel('Amplitude')
    plt.show(block=False)

    w, H = channelizer.freqz()
    plt.figure()
    plt.plot(w, dB(H).T)
    plt.title('Prototype filter frequency response')
    plt.xlabel('Frequency [*rad/sample]')
    plt.ylabel('Amplitude [dB]')
    plt.show(block=False)

    plt.figure()
    plt.plot(channelizer._filter_branches.T)
    plt.title('PFB branches impulse responses')
    plt.xlabel('#')
    plt.ylabel('Amplitude')
    plt.show(block=False)

    w, H_k = channelizer.filterbank_freqz()
    plt.figure()
    plt.plot(w, dB(H_k.T))
    plt.title('Channelizer frequency response')
    plt.xlabel('Frequency [*rad/sample]')
    plt.ylabel('Amplitude [dB]')
    plt.show(block=False)


    NFFT=512
    SIDES="twosided"
    ASPECT="auto"
    CMAP=cm.gray
    ORIGIN="lower"
    INTERPOLATION="bicubic"
    NOVERLAP=1
    XAXIS="Time (seconds)"
    YAXIS="Normalized Frequency"
    NXTICKS = 5
    NYTICKS = 5
    FS = 3.8e9


    def format_axes(ax, freq_zoom=1, freq_bank=None):
        ax.set_xlabel(XAXIS)
        xmin, xmax = ax.get_xlim()
        xlabels = [x for x in np.linspace(0,1,NXTICKS)]
        ax.set_xlim(0, xmax)
        ax.xaxis.set_major_locator(LinearLocator(NXTICKS))
        ax.set_xticklabels(xlabels)

        ax.set_ylabel(YAXIS)
        ymin, ymax = ax.get_ylim()
        #-.49999 to keep it from displaying as -0.00
        #All other if statement values are to compensate for filter bank ordering
        ylabels = [float(y)/freq_zoom + (0 if freq_bank == None else freq_bank*(float(1.)/freq_zoom) - (1. if freq_bank > DECIMATE_BY/2 else 0))
                   for y in np.linspace(-.5,.5,NYTICKS)]
        ax.set_ylim(0, ymax)
        ylabels = ["%.2f" % y for y in ylabels]
        ax.yaxis.set_major_locator(LinearLocator(NYTICKS))
        ax.set_yticklabels(ylabels)

    def show_filter_response(filt, axarr, title=None):
        w,h = scipy.signal.freqz(filt,
                                 worN=np.linspace(-np.pi, np.pi,512),
                                 )
        axarr.plot(w/max(w)/2, np.abs(h))
        if title != None:
            axarr.set_title(title)
        axarr.set_xlabel("Normalized frequency")
        axarr.set_ylabel("Gain")

    #Generate chirp and add noise - fully synthetic chirp has strange looking plots
    data = gen_complex_chirp(fs = FS)
    data += .01*np.random.randn(len(data))


    f1, axarr1 = plt.subplots(6)
    plt.tight_layout()
    pxx, freqs, bins, im = axarr1[0].specgram(data, NFFT, noverlap=NOVERLAP)
    #This specgram, imshow runaround seems to be necessary to eliminate blank space at the end of regular matplotlib specgram calls?
    #If anyone knows a better fix, let me know
    axarr1[0].imshow(np.ma.log(abs(pxx)), aspect=ASPECT, cmap=CMAP, origin=ORIGIN, interpolation=INTERPOLATION)
    axarr1[0].set_title("Specgram of original data")
    format_axes(axarr1[0])

    basic = channelizer.basic_single_filter(data)
    show_filter_response(channelizer._filter_coeffs, axarr1[1], title="Lowpass filter response")

    pxx, freqs, bins, im = axarr1[2].specgram(basic, NFFT, noverlap=NOVERLAP)
    axarr1[2].imshow(np.ma.log(abs(pxx)), aspect=ASPECT, cmap=CMAP, origin=ORIGIN, interpolation=INTERPOLATION)
    axarr1[2].set_title("Filtered")
    format_axes(axarr1[2])

    decimated = basic[::DECIMATE_BY]
    pxx, freqs, bins, im = axarr1[3].specgram(decimated, NFFT, noverlap=NOVERLAP)
    axarr1[3].imshow(np.ma.log(abs(pxx)), aspect=ASPECT, cmap=CMAP, origin=ORIGIN, interpolation=INTERPOLATION)
    axarr1[3].set_title("Filtered, then decimated")
    format_axes(axarr1[3], freq_zoom=DECIMATE_BY)
    
    if nof_substeps == 1:
        decimated_filtered = channelizer.polyphase_single_filter(data, k=0)
        pxx, freqs, bins, im = axarr1[4].specgram(decimated_filtered, NFFT, noverlap=NOVERLAP)
        axarr1[4].imshow(np.ma.log(abs(pxx)), aspect=ASPECT, cmap=CMAP, origin=ORIGIN, interpolation=INTERPOLATION)
        axarr1[4].set_title("Polyphase filtered data for channel 0")
        format_axes(axarr1[4], freq_zoom=DECIMATE_BY)

    if nof_substeps != 1:
        decimated_filtered = channelizer.polyphase_substep_filter(data, k=1.25)
        pxx, freqs, bins, im = axarr1[5].specgram(decimated_filtered, NFFT, noverlap=NOVERLAP)
        axarr1[5].imshow(np.ma.log(abs(pxx)), aspect=ASPECT, cmap=CMAP, origin=ORIGIN, interpolation=INTERPOLATION)
        axarr1[5].set_title("Polyphase filtered data for channel 1.25")
        format_axes(axarr1[5], freq_zoom=DECIMATE_BY)

    plt.show(block=False)


    f2, axarr2 = plt.subplots(DECIMATE_BY)
    plt.tight_layout()
    decimated_filterbank = channelizer.polyphase_analysis(data)
    for i in range(decimated_filterbank.shape[0]):
        pxx, freqs, bins, im = axarr2[i].specgram(decimated_filterbank[i], NFFT)
        axarr2[i].imshow(np.ma.log(abs(pxx)), aspect=ASPECT, cmap=CMAP, origin=ORIGIN, interpolation=INTERPOLATION)
        axarr2[i].set_title(f"Filterbank output {i}")
        format_axes(axarr2[i], freq_zoom=DECIMATE_BY, freq_bank=i)
    plt.show(block=False)


    channelizer.plot_L0(nof_steps_to_plot = 9)
    plt.show()

