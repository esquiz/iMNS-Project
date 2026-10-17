import numpy as np
import os
import pyvisa as pv   #PyVisa is required along with NIVisa
from time import sleep
import pandas as pd
# import time
import scipy as sc
from tqdm import tqdm
import matplotlib.pyplot as plt
import datetime
from tqdm import tqdm
import time


from sadevice.sa_api import *


start_freq = 6.9e9
stop_freq = 7.1e9

center_freq = (start_freq + stop_freq)/2
span_freq = stop_freq - start_freq

rbw = 6.5e3       # Resolution bandwidth in Hz (bin size)
vbw = 6.5e3       # Video bandwidth in Hz (averaging filter bandwidth)

sweep_time = 0.5


##############################################################################################

'''Find directory for file, create new folder in results/d-m-Y/H-M-S for each new experiment'''

# get the directory where this python script is located
file_path = os.path.dirname(os.path.realpath(__file__))

now = datetime.datetime.now()


try:
    dir_path = f'{file_path}\\data\\{now.strftime("%d-%m-%Y")}\\{now.strftime("%H-%M-%S")}'
    os.makedirs(dir_path)
    print(f"Directory '{dir_path}' created successfully.")
except FileExistsError:
    print(f"Directory '{dir_path}' already exists.")
except PermissionError:
    print(f"Permission denied: Unable to create '{dir_path}'.")
except Exception as e:
    print(f"An error occurred: {e}")


SAVE_PATH = f'{dir_path}'

sample = 'hot_noise'



#############################################################################################

def configure_SA_API():
    '''Configures the spectrum analyser with the settings we want for our experiment.'''
    handle = sa_open_device()["handle"]

    # Configure device
    sa_config_center_span(handle, center_freq, span_freq)       # sets the center frequency and span of the sweep
    sa_config_level(handle, -30.0)                              # The reference level is -30 dBm - should be set around the peak power we expect to see. (sets gain of -30 similar to siegl et al paper)
    sa_config_sweep_coupling(handle, rbw, vbw, 0)               # sets up sweep, band width, averaging, sweep time
    sa_config_acquisition(handle, SA_AVERAGE, SA_LOG_SCALE)     # data is returned as average (where the max and min values are equal) and in log scale (dBm)

    return handle
    


def get_SA_sweep(handle):
    sa_initiate(handle, SA_SWEEPING, 0)  # initiates sweep, 0 means it will block until sweep is complete
    query = sa_query_sweep_info(handle)
    sweep_length = query["sweep_length"]
    start_freq = query["start_freq"]
    bin_size = query["bin_size"]

    # Get sweep
    sweep_max = sa_get_sweep_32f(handle)["min"]


    freqs = [start_freq + i * bin_size for i in range(sweep_length)]


    # pd.DataFrame({'Frequency (Hz)': freqs, 'Amplitude (dBm)': sweep_max}).to_csv(name_of_test, index=False)
    
    sweep_data = pd.DataFrame({'Frequency (Hz)': freqs, 'Amplitude (dBm)': sweep_max})

    return sweep_data, bin_size

if __name__== "__main__":


    t0 = time.perf_counter()

    SA_handle = configure_SA_API()
    print(f'Connection to SA configured')

    sweep_data, bandwidth = get_SA_sweep(SA_handle)

    name_of_test = f'{SAVE_PATH}\\{sample}.csv'


    t1 = time.perf_counter()

    with open(name_of_test, 'w') as f:
        f.write(f'! Bandwidth: {bandwidth} Hz\n')
        f.write(f'! Sweep time: {t1-t0} seconds\n')
    
    sweep_data.to_csv(name_of_test, index=False, mode='a')

    sa_close_device(SA_handle)

