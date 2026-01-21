import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import resample, butter, filtfilt
from scipy.io import loadmat
import mne

class BCIDataLoader:
    def __init__(self, data_path, channels=22, target_length=1000, cutoff_frequency=30, sample_rate=250):
        """
        Initialize BCI IV 2a data loader
        :param data_path: Root path of BCI IV 2a dataset
        :param channels: Number of EEG channels to keep
        :param target_length: Resampled time points per trial
        :param cutoff_frequency: Low-pass filter cutoff frequency
        :param sample_rate: Original sampling rate (BCI IV 2a is 250Hz)
        """
        self.data_path = data_path
        self.channels = channels
        self.target_length = target_length
        self.cutoff_frequency = cutoff_frequency
        self.sample_rate = sample_rate

    def _butter_lowpass_filter(self, data, cutoff, fs, order=4):
        """Butterworth low-pass filter (required by _load_single_subject_data)"""
        nyq = 0.5 * fs
        normal_cutoff = cutoff / nyq
        b, a = butter(order, normal_cutoff, btype='low', analog=False)
        filtered_data = filtfilt(b, a, data, axis=2)
        return filtered_data

    def _load_single_subject_data(self, subject_id):
        """【内部方法】加载单个被试的所有数据（原方法保持不变）"""
        subject_all_data = []
        subject_all_labels = []

        if isinstance(subject_id, int):
            subject_str = f"A0{subject_id}"
            subject_num = str(subject_id)
        else:
            subject_str = subject_id
            subject_num = subject_id.replace("A0", "")

        stimcodes = ('769', '770', '771', '772')
        channels_to_remove = ['EOG-left', 'EOG-central', 'EOG-right']
        win_sel = (0, 3)
        true_label_path = os.path.join(self.data_path, "Data sets 2a_true_labels")

        # Load training set
        train_file = os.path.join(self.data_path, f"{subject_str}T.gdf")
        if os.path.exists(train_file):
            raw_data = mne.io.read_raw_gdf(train_file, preload=True, verbose=False)
            events, event_ids = mne.events_from_annotations(raw_data, verbose=False)
            stims = [v for k, v in event_ids.items() if k in stimcodes]
            epochs = mne.Epochs(
                raw_data, events, event_id=stims,
                tmin=win_sel[0], tmax=win_sel[1],
                event_repeated='drop', baseline=None, preload=True, verbose=False
            )
            epochs = epochs.drop_channels(channels_to_remove)
            if epochs.info['nchan'] > self.channels:
                epochs = epochs.pick_channels(epochs.ch_names[:self.channels])

            train_data = epochs.get_data() * 1e6
            train_labels = epochs.events[:, -1] - min(epochs.events[:, -1])

            for trial in train_data:
                trial_resampled = resample(trial, self.target_length, axis=1)
                subject_all_data.append(trial_resampled)
            subject_all_labels.extend(train_labels.tolist())

        # Load test set
        test_file = os.path.join(self.data_path, f"{subject_str}E.gdf")
        if os.path.exists(test_file):
            raw_data_test = mne.io.read_raw_gdf(test_file, preload=True, verbose=False)
            label_file = os.path.join(true_label_path, f"{subject_str}E.mat")
            if os.path.exists(label_file):
                labels_mat = loadmat(label_file)
                test_labels_all = labels_mat['classlabel'][:, 0]

                events_test, event_ids_test = mne.events_from_annotations(raw_data_test, verbose=False)
                index_type = [v for k, v in event_ids_test.items() if k == '783']
                if index_type:
                    events_index = np.where(events_test[:, 2] == index_type[0])[0]
                    events_test = events_test[events_index, :]
                    events_test[:, 2] = test_labels_all

                    stims_test = list(np.unique(test_labels_all))
                    epochs_test = mne.Epochs(
                        raw_data_test, events_test, event_id=stims_test,
                        tmin=win_sel[0], tmax=win_sel[1],
                        event_repeated='drop', baseline=None, preload=True, verbose=False
                    )
                    epochs_test = epochs_test.drop_channels(channels_to_remove)
                    if epochs_test.info['nchan'] > self.channels:
                        epochs_test = epochs_test.pick_channels(epochs_test.ch_names[:self.channels])

                    test_data = epochs_test.get_data() * 1e6
                    test_labels = epochs_test.events[:, -1] - min(epochs_test.events[:, -1])

                    for trial in test_data:
                        trial_resampled = resample(trial, self.target_length, axis=1)
                        subject_all_data.append(trial_resampled)
                    subject_all_labels.extend(test_labels.tolist())

        subject_all_data = np.array(subject_all_data)
        subject_all_labels = np.array(subject_all_labels)
        subject_all_data = self._butter_lowpass_filter(subject_all_data, self.cutoff_frequency, self.sample_rate)

        print(f"Loaded subject {subject_str}: {len(subject_all_data)} samples, shape {subject_all_data.shape}")
        return subject_all_data, subject_all_labels

def plot_eeg_fft_spectrum(loader, subject_id, sample_idx=0, channel_idx=0, time_slice=None, save_path="eeg_fft_spectrum.png"):
    """
    Load EEG data, extract single channel segment, compute FFT and plot spectrum
    :param loader: BCIDataLoader instance
    :param subject_id: Subject ID (int or str like 1/"A01")
    :param sample_idx: Index of trial/sample to analyze (default: 0)
    :param channel_idx: Index of EEG channel to analyze (default: 0)
    :param time_slice: Time slice range (tuple: start, end in indices, e.g., (0, 500))
    :param save_path: Path to save the spectrum plot
    """
    data, labels = loader._load_single_subject_data(subject_id)
    
    if sample_idx >= len(data):
        raise ValueError(f"Sample index {sample_idx} out of range (total samples: {len(data)})")
    if channel_idx >= data.shape[1]:
        raise ValueError(f"Channel index {channel_idx} out of range (total channels: {data.shape[1]})")
    
    single_channel_data = data[sample_idx, channel_idx, :]
    
    if time_slice is not None:
        start, end = time_slice
        if start < 0 or end > len(single_channel_data) or start >= end:
            raise ValueError(f"Invalid time slice: {time_slice}. Must be 0 ≤ start < end ≤ {len(single_channel_data)}")
        single_channel_data = single_channel_data[start:end]
        segment_label = f"Time segment: {start}-{end} points"
    else:
        segment_label = "Full time segment"
    
    n_samples = len(single_channel_data)
    fft_vals = np.fft.fft(single_channel_data)
    fft_amp = 2.0 / n_samples * np.abs(fft_vals[:n_samples//2])
    freq_axis = np.fft.fftfreq(n_samples, 1/loader.sample_rate)[:n_samples//2]
    
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(freq_axis, fft_amp, color='navy', linewidth=1.5, label='Amplitude Spectrum')
    
    peak_freq_idx = np.argmax(fft_amp)
    peak_freq = freq_axis[peak_freq_idx]
    peak_amp = fft_amp[peak_freq_idx]
    # ax.annotate(f'Peak: {peak_freq:.2f} Hz\nAmplitude: {peak_amp:.2f} μV',
    #             xy=(peak_freq, peak_amp), xytext=(peak_freq+2, peak_amp),
    #             arrowprops=dict(arrowstyle='->', color='red', lw=1),
    #             fontsize=10, color='red', fontweight='bold')
    
    ax.set_title(f'EEG FFT Spectrum - Subject {subject_id} (Sample {sample_idx}, Channel {channel_idx})', 
                 fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel('Frequency (Hz)', fontsize=12, labelpad=10)
    ax.set_ylabel('Amplitude (μV)', fontsize=12, labelpad=10)
    ax.set_xlim(0, loader.cutoff_frequency)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"FFT spectrum plot saved to: {save_path}")
    
    return {
        'frequency_axis': freq_axis,
        'amplitude_spectrum': fft_amp,
        'peak_frequency': peak_freq,
        'peak_amplitude': peak_amp
    }

def plot_average_fft_10_channels(loader, subject_id, sample_idx=0, channel_indices=None, time_slice=None, save_path="average_10ch_fft_spectrum.png"):
    """
    Compute FFT for 10 arbitrary EEG channels, calculate average spectrum, and plot all channels + average
    :param loader: BCIDataLoader instance
    :param subject_id: Subject ID (int or str like 1/"A01")
    :param sample_idx: Index of trial/sample to analyze (default: 0)
    :param channel_indices: List of 10 channel indices (if None, random select 10 valid channels)
    :param time_slice: Time slice range (tuple: start, end in indices, e.g., (0, 500))
    :param save_path: Path to save the average spectrum plot
    :return: Dictionary with frequency axis, individual channel spectra, and average spectrum
    """
    # Step 1: Load subject data
    data, labels = loader._load_single_subject_data(subject_id)
    n_total_channels = data.shape[1]
    
    # Step 2: Validate sample index
    if sample_idx >= len(data):
        raise ValueError(f"Sample index {sample_idx} out of range (total samples: {len(data)})")
    
    # Step 3: Handle channel indices (ensure 10 valid channels)
    if channel_indices is None:
        # Random select 10 unique valid channels if not specified
        if n_total_channels < 10:
            raise ValueError(f"Only {n_total_channels} channels available, need at least 10")
        channel_indices = np.random.choice(n_total_channels, size=10, replace=False)
        channel_indices = sorted(channel_indices)  # Sort for readability
    else:
        # Validate user-specified channel indices
        if len(channel_indices) != 10:
            raise ValueError(f"Channel indices must be length 10 (got {len(channel_indices)})")
        for idx in channel_indices:
            if idx < 0 or idx >= n_total_channels:
                raise ValueError(f"Channel index {idx} out of range (total channels: {n_total_channels})")
        # Remove duplicates and recheck length (if user input duplicates)
        channel_indices = sorted(list(set(channel_indices)))
        if len(channel_indices) != 10:
            raise ValueError(f"Channel indices contain duplicates (only {len(channel_indices)} unique channels)")
    
    # Step 4: Extract time segment and compute FFT for each channel
    fft_results = {
        'frequency_axis': None,
        'individual_spectra': [],
        'channel_indices': channel_indices,
        'average_spectrum': None
    }
    
    for ch_idx in channel_indices:
        # Extract single channel data
        ch_data = data[sample_idx, ch_idx, :]
        
        # Apply time slice
        if time_slice is not None:
            start, end = time_slice
            if start < 0 or end > len(ch_data) or start >= end:
                raise ValueError(f"Invalid time slice: {time_slice}. Must be 0 ≤ start < end ≤ {len(ch_data)}")
            ch_data = ch_data[start:end]
        
        # Compute FFT
        n_samples = len(ch_data)
        fft_vals = np.fft.fft(ch_data)
        fft_amp = 2.0 / n_samples * np.abs(fft_vals[:n_samples//2])
        
        # Store frequency axis (only once, same for all channels)
        if fft_results['frequency_axis'] is None:
            fft_results['frequency_axis'] = np.fft.fftfreq(n_samples, 1/loader.sample_rate)[:n_samples//2]
        
        fft_results['individual_spectra'].append(fft_amp)
    
    # Step 5: Calculate average spectrum
    fft_results['individual_spectra'] = np.array(fft_results['individual_spectra'])  # Shape: (10, n_freq)
    fft_results['average_spectrum'] = np.mean(fft_results['individual_spectra'], axis=0)
    
    # Step 6: Plot individual channels + average spectrum
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Plot individual channels (light color, low alpha for visibility)
    for i, (ch_idx, spectrum) in enumerate(zip(channel_indices, fft_results['individual_spectra'])):
        ax.plot(fft_results['frequency_axis'], spectrum, 
                color='lightblue', alpha=0.5, linewidth=1, 
                label=f'Channel {ch_idx}' if i == 0 else "")  # Only show first channel in legend to avoid clutter
    
    # Plot average spectrum (bold, dark color)
    ax.plot(fft_results['frequency_axis'], fft_results['average_spectrum'], 
            color='navy', linewidth=2.5, label='Average of 10 Channels', zorder=5)
    
    # Annotate average peak frequency
    avg_peak_idx = np.argmax(fft_results['average_spectrum'])
    avg_peak_freq = fft_results['frequency_axis'][avg_peak_idx]
    avg_peak_amp = fft_results['average_spectrum'][avg_peak_idx]
    # ax.annotate(f'Average Peak: {avg_peak_freq:.2f} Hz\nAmplitude: {avg_peak_amp:.2f} μV',
    #             xy=(avg_peak_freq, avg_peak_amp), xytext=(avg_peak_freq+3, avg_peak_amp),
    #             arrowprops=dict(arrowstyle='->', color='red', lw=1.5),
    #             fontsize=11, color='red', fontweight='bold', zorder=6)
    
    # Plot settings (all English)
    time_slice_label = f"Time segment: {time_slice[0]}-{time_slice[1]} points" if time_slice else "Full time segment"
    ax.set_title(f'EEG FFT Spectrum - Average of 10 Channels (Subject {subject_id}, Sample {sample_idx})\n{time_slice_label}', 
                 fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel('Frequency (Hz)', fontsize=12, labelpad=10)
    ax.set_ylabel('Amplitude (μV)', fontsize=12, labelpad=10)
    ax.set_xlim(0, loader.cutoff_frequency)  # Limit to low-pass cutoff
    
    # Legend: combine "Individual Channels" (single entry) + "Average"
    handles, labels = ax.get_legend_handles_labels()
    new_handles = [handles[0], handles[-1]]
    new_labels = ['Individual Channels (10)', 'Average of 10 Channels']
    ax.legend(new_handles, new_labels, fontsize=11, loc='upper right')
    
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    
    # Step 7: Save plot
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Average FFT spectrum plot (10 channels) saved to: {save_path}")
    
    # Return detailed results
    return {
        'frequency_axis': fft_results['frequency_axis'],
        'channel_indices': channel_indices,
        'individual_spectra': fft_results['individual_spectra'],
        'average_spectrum': fft_results['average_spectrum'],
        'average_peak_frequency': avg_peak_freq,
        'average_peak_amplitude': avg_peak_amp
    }

# -------------------------- Example Usage --------------------------
if __name__ == "__main__":
    # 1. Initialize data loader
    DATA_PATH = "/home/zengkai/model_compare/data/BNCI2014_001"  # Replace with your actual data path
    loader = BCIDataLoader(
        data_path=DATA_PATH,
        channels=22,
        target_length=1000,
        cutoff_frequency=30,
        sample_rate=250
    )
    
    # 2. Example 1: Single channel FFT (original function)
    single_ch_results = plot_eeg_fft_spectrum(
        loader=loader,
        subject_id="A01",
        sample_idx=0,
        channel_idx=0,
        time_slice=(0, 800),
        save_path="A01_channel0_fft.png"
    )
    
    # 3. Example 2: 10 channels average FFT (new function)
    # Option A: Use randomly selected 10 channels
    avg_10ch_results = plot_average_fft_10_channels(
        loader=loader,
        subject_id="A01",
        sample_idx=0,
        channel_indices=None,  # Random 10 channels
        time_slice=(0, 800),
        save_path="A01_avg_10ch_fft_random.png"
    )
    
    # Option B: Use user-specified 10 channels
    specified_channels = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]  # First 10 channels
    avg_10ch_spec_results = plot_average_fft_10_channels(
        loader=loader,
        subject_id="A01",
        sample_idx=0,
        channel_indices=specified_channels,
        time_slice=(0, 800),
        save_path="A01_avg_10ch_fft_specified.png"
    )
    
    # Print key results
    print("\n=== Single Channel FFT Results ===")
    print(f"Peak Frequency: {single_ch_results['peak_frequency']:.2f} Hz")
    
    print("\n=== 10 Channels Average FFT Results ===")
    print(f"Selected Channels: {avg_10ch_results['channel_indices']}")
    print(f"Average Peak Frequency: {avg_10ch_results['average_peak_frequency']:.2f} Hz")
    print(f"Average Peak Amplitude: {avg_10ch_results['average_peak_amplitude']:.2f} μV")