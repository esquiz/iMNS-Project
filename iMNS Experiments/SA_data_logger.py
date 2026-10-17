import pyvisa as pv    #PyVisa is required along with NIVisa
from time import sleep
import os 
import numpy as np
import pandas as pd
import datetime
from tqdm import tqdm
from sadevice.sa_api import *
import time
import scipy as sc



###############################################################################################################

GPIB_ID_DLM = 'GPIB1::7::INSTR'   #changed GPIB0 to GPIB1 should allow for two connections

TIMEOUT_DLM = 5000    # in milliseconds CHECK SPECIFICATION

MAX_VOLTAGE = 80.0
MAX_CURRENT = 37.0
MIN_VOLTAGE = 0.0
MIN_CURRENT = 0.0 

###############################

TCPIP_ID_SA = 'TCPIP0::192.168.1.100::5025::SOCKET'

READ_TERM_SA = '\n'
WRITE_TERM_SA = '\n'
TIMEOUT_SA = 20000    # in milliseconds CHECK SPECIFICATION

start_freq = 6.85e9
stop_freq = 7.15e9

# center_freq = (start_freq + stop_freq)/2
# span_freq = stop_freq - start_freq

span_freq = 50e6 #maximum span for narrowband radio bandwidth (1kHz) 

rbw = 1e3       # Resolution bandwidth in Hz (bin size)
vbw = 625     # Video bandwidth in Hz (averaging filter bandwidth)

sweep_time = 0.5



###############################


B_max = 0.2                   # maximum field in Tesla
B_min = 0.001                   # minimum field in Tesla
B_step = 0.001                # step field in Tesla

B_fields = np.arange(B_min, B_max, B_step)  # list of B fields to loop through


MAX_B = 0.201           #tesla (200mT)
MIN_B = 0
MIN_B_STEP = 0.0002


B_DELAY = 3     # seconds
start_current = 0.1


##############################################################################################

'''Find directory for file, create new folder in results/d-m-Y/H-M-S for each new experiment'''

# get the directory where this python script is located
file_path = os.path.dirname(os.path.realpath(__file__))

now = datetime.datetime.now()


try:
    dir_path = f'{file_path}\\Results\\{now.strftime("%d-%m-%Y")}\\{now.strftime("%H-%M-%S")}'
    os.makedirs(dir_path)
    print(f"Directory '{dir_path}' created successfully.")
except FileExistsError:
    print(f"Directory '{dir_path}' already exists.")
except PermissionError:
    print(f"Permission denied: Unable to create '{dir_path}'.")
except Exception as e:
    print(f"An error occurred: {e}")


SAVE_PATH = f'{dir_path}'

# sample = 'PY'
sample = 'YIG'
# sample = 'None'

# noise_used = 'keysight'
# noise_used = 'off'
# noise_used = 'RT'
# noise_used = 'resistor'
noise_used = 'LN2'
# noise_used = 'LN2_nosamp'
# noise_used = 'keysight_nosamp'


scan_mode = SA_AVERAGE
# scan_mode = SA_MIN_MAX

ref = -40 #dBm


sampling = 2

#############################################################################################
'''Functions'''

def dB_to_linear(x_dB):

    return 10**(x_dB/10)

def linear_to_dB(x_lin):

    return 10*np.log10(x_lin)


def configure_powersupply(DLM):
    print("Configuring Magnet Power Supply...")
    
    DLM.timeout = TIMEOUT_DLM   # in milliseconds
    print(DLM.query('*IDN?'))   # identify
    DLM.write('*CLS')           # clear status
    DLM.write('*RST')           # reset 
    print(DLM.query('*TST?'))   # check for issues
    
    DLM.write("SOUR:VOLT 30")                   # set voltage to low level but high enough for current control
    DLM.write(f'SOUR:CURR {start_current}')     # sets low current before enabling output to ensure no large changes
    # DLM.write('OUTPut ON') 


    # DLM.write('OUTP 1') 
    print("Magnet Power Supply configured and output ON.")



def set_magnetic_field(B_field: float):
    '''Sets the magnetic field to B_field in Tesla.
    
    This has not yet been finished, still figuring out the magnet.
    '''

    # Look up current needed for B field from calibration data. (could open the csv file pre-emptively and interpolate)

    B_current = calibration_interpolation[calibration_interpolation["B"]==B_field]["Current"].values[0]

    # set power to give expected B

    err = DLM.query("SYST:ERR?")
    print(err)
    DLM.write("*CLS")

    # DLM.write(f'VOLT {voltage}')      # set voltage in Volts - CHANGE THIS ACCORDING TO CALIBRATION
    DLM.write(f'SOUR:CURR {B_current:.3f};*OPC?')    # set current in Amps - assuming 0.1 T per Amp - CHANGE THIS FACTOR ACCORDING TO CALIBRATION
    sleep(2*B_DELAY)

    # query actual current to calculate real field used
    actual_current = float(DLM.query('MEAS:CURR?'))
    

    sleep(B_DELAY)  # time delay for setting the field


    return actual_current, B_current


def import_data(file_path):

    data = pd.read_csv(file_path, comment='!', sep=',')
    data = data.rename(columns=lambda x: x.strip())
    headers = data.columns.tolist()


    return data, headers


#borrowed from old code of mine
def calculate_trendline(x, y, fit_type='linear'):
    """
    Function to calculate the trendline for the given data.
    Args:
        x (pd.Series): X-axis data.
        y (pd.Series): Y-axis data.
    Returns:
        slope and intercept to generate trendline.
    """
    if fit_type == 'linear':
        slope, intercept = np.polyfit(x, y, 1)
        # trendline = slope * x + intercept
        print(f'slope:{slope} and y intercept:{intercept}')
        return slope, intercept



def get_calibrated_B_curr():
    '''Opens the directory and looks in the /calibration/data folder for past calibrations
    These should be named ending in the date of the calibration, and containing B_curr for this type of calibration

    Returns a boolean has calibration to prevent error
    returns dataframe with calibration otherwise.'''


    files = os.listdir(f'{file_path}\\calibration\\data')

    file_names = []

    all_B_calibrations = []

    has_calibration = False
    

    # Print the files
    for file in files:
        # Check if item is a file, not a directory
        if not os.path.isdir(os.path.join(file_path, file)):
            
            file_names.append(file)
        
    for calibration_data in file_names:
        if 'B_curr' in calibration_data:
            all_B_calibrations.append(calibration_data)

    

    # If there is no files in the folder, then it returns a data frame of the correct size of zeroes. and prompts to check directory.

    if not all_B_calibrations:
        print(f'no B-current calibrations found in {file_path}')
        print("\nCheck file directory if unexpectected, returning 0s...")

        interpolated_B_current = pd.DataFrame({'B': B_fields, 'Applied Current': B_fields*0})

        has_calibration = False


    # If there is calibration data, it returns the most up to date one.
    else:
        latest_calibration = max(all_B_calibrations, key=lambda p: datetime.datetime.strptime(p, "B_curr_calibration_%d-%m-%Y.csv"))
        print(f'using calibration data from {latest_calibration}')

        calibrated_B_data, calibrated_headers = import_data(f'{file_path}\\calibration\\data\\{latest_calibration}')

        B_current_slope , B_current_intercept = calculate_trendline(calibrated_B_data[calibrated_headers[0]], calibrated_B_data[calibrated_headers[3]])

        interpolated_B_current = pd.DataFrame({'B': B_fields, 'Current': B_current_slope*B_fields + B_current_intercept})

        has_calibration = True

    return has_calibration, interpolated_B_current, B_current_slope, B_current_intercept


def configure_SA_API(center_freq, span_freq, scan_type):
    '''Configures the spectrum analyser with the settings we want for our experiment.
    scan_type take 'SA_AVERAGE' or '''
    handle = sa_open_device()["handle"]


    # Configure device
    sa_config_center_span(handle, center_freq, span_freq)       # sets the center frequency and span of the sweep
    sa_config_level(handle, ref)                              # The reference level is -60dB
    sa_config_sweep_coupling(handle, rbw, vbw, 0)               # sets up sweep, band width, averaging, sweep time
    sa_config_acquisition(handle, scan_type, SA_LOG_SCALE)     # data is returned as average (where the max and min values are equal) and in log scale (dBm)
    sa_config_gain_atten(handle, 0, 0, 0)                          # sets attenuation to 0, and 16dB attenuation in the gain, and preamplifier always on for SA124B
    # sa_config_proc_units(handle, SA_BYPASS)                     # removes video filtering

    return handle
    


def get_SA_sweep(handle):
    

    sa_initiate(handle, SA_SWEEPING, 0)  # initiates sweep, 0 means it will block until sweep is complete
    query = sa_query_sweep_info(handle)
    sweep_length = query["sweep_length"]
    start_freq = query["start_freq"]
    bin_size = query["bin_size"]


    # Get sweep
    sweep = sa_get_sweep_32f(handle)["min"]


    freqs = [start_freq + i * bin_size for i in range(sweep_length)]


    # pd.DataFrame({'Frequency (Hz)': freqs, 'Amplitude (dBm)': sweep_max}).to_csv(name_of_test, index=False)
    
    # sweep_data = pd.DataFrame({'Frequency (Hz)': freqs, 'Amplitude (dBm)': sweep_max})

    return freqs, sweep, bin_size



########################################################################################################################
#Main


if __name__== "__main__":

    

    # imports calibrated data, extrapolates current needed for fields in experiment.

    try:
        # Might be better to change this to the limits of the SA in frequency
        if (max(B_fields) >= MAX_B
        or min(B_fields) < MIN_B
        or abs(B_step) < MIN_B_STEP):
            raise ValueError("Requested current sweep incompatible with power supply limits. Check min, max and step-size")
    

        rm = pv.ResourceManager()
        cxns = rm.list_resources()
        print(cxns)
        # Check VNA connection
        
        # Make list of values to export at the end of experiments
        scan_data = [['Frequency (Hz)', 'Average Amplitude (dBm)', 'Amplitude Error']]

        with rm.open_resource(GPIB_ID_DLM) as DLM:

            # configure magnet power supply
            
            configure_powersupply(DLM)
            print(f'Connection to {GPIB_ID_DLM} configured')
            
            # Check if it is necessary to do multiple experiments for frequency range
            if stop_freq - start_freq > span_freq:
                center_frequencies = np.arange(start_freq + span_freq/2, stop_freq, span_freq)
            else:
                center_frequencies = [(start_freq + span_freq)/2]


            # Redefine the B-fields to plot according to the expected resonance of the frequencies specified, from VNA FMR file.

            # Sets global field range for calibration
            kittel_data = pd.read_csv(f'C:/Users/nicoe/OneDrive - Imperial College London/Documents/A Univeristy/Year 4/Masters Project/Results/Experiments/VNA_FMR/Results/Data_analysis/kittel_data_points_{sample}.csv')

            #drop values corresponding to frequencies outside the range of the SA
            kittel_data = kittel_data[(kittel_data['freq(Hz)'] >= start_freq-span_freq) & (kittel_data['freq(Hz)'] <= stop_freq+span_freq)]
            kittel_B_fields = kittel_data['B(T)'].values

            B_fields = np.arange(kittel_B_fields.min()-3*B_step, kittel_B_fields.max()+3*B_step, B_step)

            print(B_fields)

            # get calibration data for B field - current 
            calibrated, calibration_interpolation, calibration_slope, calibration_intercept = get_calibrated_B_curr()

            if calibrated == False:
                raise RuntimeError("There is no calibration data, needed to control magnet")


            for center_freq in tqdm(center_frequencies):

                #Get fields for the experiment according to the center frequency of this experiment
                # print(f'\n{center_freq/1e9:.4f}, {kittel_data} ')
                # kittel_data_slice = kittel_data[(kittel_data['freq(Hz)'] >= (center_freq - (span_freq))) & (kittel_data['freq(Hz)'] <= (center_freq + (span_freq)))].copy()
                # fields_from_kittel = kittel_data_slice['B(T)'].values

                # B_fields = np.arange(fields_from_kittel.min()-1*B_step, fields_from_kittel.max()+1*B_step, B_step)
                # print(f'B fields to sweep for center frequency {center_freq/1e9:.4f} GHz: {B_fields}')

                #Configure SA for this center frequency and span
                SA_handle = configure_SA_API(center_freq, span_freq, scan_mode)
                print(f'Connection to SA configured with center frequency {center_freq/1e9:.4f} GHz and span {span_freq/1e6:.4f} MHz')

                
                #Loop through B0 fields according to calibration
                for B0 in B_fields:

                    temp_df = pd.DataFrame()

                    #Time used to meta data of experiment
                    t0 = time.perf_counter()

                    current_used, I_requested = set_magnetic_field(B0)

                    field_used = (current_used - calibration_intercept)/calibration_slope

                    name_of_test = f'{SAVE_PATH}\\{sample}_{noise_used}_B_field_{field_used:.4f}_start_{(center_freq-span_freq/2)/1e9:.3f}.csv'

                    '''here goes the function which obtains the spectra from the SA and saves it to the name of test path'''
                    for k in range(sampling):

                        freqs, amplitudes, bandwidth = get_SA_sweep(SA_handle)
                        temp_df[f'amplitude_{k}'] = amplitudes            
                        temp_df[f'amplitude_{k}'] = temp_df[f'amplitude_{k}'].apply(dB_to_linear)


                    temp_df['Average Amplitude (dBm)'] = temp_df.mean(axis=1)
                    temp_df['Average Amplitude (dBm)'] = temp_df['Average Amplitude (dBm)'].apply(linear_to_dB)

                    temp_df['Amplitude Error'] = temp_df[[f'amplitude_{k}' for k in range(sampling)]].std(axis=1)

                    temp_df[f'Frequency(Hz)'] = freqs
                    # temp_df.set_index('Frequency(Hz)', inplace=True)


                    # print('3')

                    sweep_data = temp_df[['Frequency(Hz)', 'Average Amplitude (dBm)', 'Amplitude Error']].copy()
                    
                    print(f'Saving to {name_of_test}\n')

                    t1 = time.perf_counter()

                    with open(name_of_test, 'w') as f:
                        f.write(f'! Actual B field: {field_used} T\n')
                        f.write(f'! Current used: {current_used} A\n')
                        f.write(f'! Requested current: {I_requested} A\n')
                        f.write(f'! Bin size: {bandwidth} Hz\n')
                        f.write(f'! Scan mode used: {str(scan_mode)}\n')
                        f.write(f'! Reference level: {ref}\n')
                        f.write(f'! Attenuation: 0, gain: 16dB\n')
                        f.write(f'! Number of averages: {sampling}\n')
                        f.write(f'! Sweep time: {t1-t0} seconds\n')
                    
                    sweep_data.to_csv(name_of_test, index=False, mode='a')
                
                # reset SA 

                sa_close_device(SA_handle)

            DLM.write('*RST')    # resets GMW magnet power supply to safe state

    except RuntimeError as e1:
        print(f"There is an error within the set up: {e1}")

    except Exception as e2:
        print(f"Error in current sweep loop: Need to debug!\n {e2}")

    except ValueError as e3:
        print("Unsafe values entered, check definitions")


    print(f'\nSaving to {SAVE_PATH}')
    print("Done")