# -*- coding: utf-8 -*-
'''
Created on 10/1/2020
Modified on 5/29/2024

OVERVIEW:
    This script saves csv/touchstone/screenshot files periodically under the same directory as this script.
    The VNA software has to be running always when automating the VNA. The VNA software
    is the driver for the VNA

Before running the code:
    1. Make sure S2VNA software is running
    2. Go to system -> Misc setup -> network remote settings -> turn on socket server
    3. make sure socket server is 5025
'''



'''I'd like to clarify, I wrote this code first, before having the try loops inside main. I could change it, but we will see'''

import pyvisa as pv    #PyVisa is required along with NIVisa
from time import sleep
import os 
import numpy as np
import pandas as pd
import datetime
from tqdm import tqdm


## INIT #########################################################################################################


## Connect to Magnet Power Supply via GPIB ################


'''  A 2 millisecond delay between the Write and Read 
functions will be sufficient to insure that there is enough time to receive a response for all valid 
queries.   From specification '''



###############################################################################################################
# sample = 'PY'
sample = 'YIG'


###############################################################################################################






GPIB_ID_DLM = 'GPIB0::7::INSTR'   #changed GPIB0 to GPIB1 should allow for two connections

TIMEOUT_DLM = 5000    # in milliseconds CHECK SPECIFICATION

MAX_VOLTAGE = 80.0
MAX_CURRENT = 37.0
MIN_VOLTAGE = 0.0
MIN_CURRENT = 0.0 

###############################


TCPIP_ID_S2VNA = 'TCPIP0::127.0.0.1::5025::SOCKET'      # had to change to 5026 instead of 5025 port for some reason (VNA would not connect to 5025)
TERMINATION_VNA = '\n'
TIMEOUT_VNA = 10000



#################################################################################################################

##### Definitions #####


delay = 1 * 1               # unit is in seconds - delay between measurements

start_freq = 0*1e9          # Frequency centre in Hz
end_freq = 16*1e9           # Frequency Range in Hz
num_points = 4001           # Number of points

# num_measurements = 1        # number of measurements to take (each makes a new csv file)

B_max = 0.2                   # maximum field in Tesla
B_min = 0.001                   # minimum field in Tesla
B_step = 0.002                 # step field in Tesla

B_fields = np.arange(B_min, B_max, B_step)  # list of B fields to loop through


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


# os.makedirs(f'{file_path}\\Results\\{now.strftime("%d-%m-%Y")}')

SAVE_PATH = f'{dir_path}'


MAX_B = 0.201           #tesla (200mT)
MIN_B = 0
MIN_B_STEP = 0.0005



B_DELAY = 3     # seconds
start_current = 0.1

#################################################################################################################


#################################################################################################################


##  Functions  ##################################################


def configure_VNA(CMT):
    print("Configuring CMT VNA Magnet Power Supply...")

    CMT.read_termination = TERMINATION_VNA
    CMT.timeout = TIMEOUT_VNA


    print("VNA Configured.")



    ## Configure display ##############################
        
    CMT.write('DISP:WIND:SPL 2')    # allocate 2 trace windows 
    CMT.write('CALC1:PAR:COUN 2')   # 2 Traces in channel 1

    CMT.write('CALC1:PAR1:DEF S11') #Choose S11 for trace 1
    CMT.write('CALC1:PAR2:DEF S21') #Choose S21 for trace 2

    CMT.write('CALC1:PAR1:SEL')     # select trace 1
    CMT.write('CALC1:FORM MLOG')    #log Mag format


    CMT.write('CALC1:PAR2:SEL')     # select trace 2
    CMT.write('CALC1:FORM MLOG')    # Log mag format


    ############# Frequency Setup ##################

    CMT.write(f'SENS:FREQ:STAR {start_freq}')   # set start frequency
    CMT.write(f'SENS:FREQ:STOP {end_freq}')     # set stop frequency
    CMT.write(f'SENS:SWE:POIN {num_points}')    # set number of points

    ###############################################

    CMT.write('TRIG:SOUR BUS')

    # Always end an *OPC? command after all the VNA setups to make sure the setups are 
    # complete before making measurement
    CMT.query('*OPC?')



    print("\nVNA display configured")


def configure_powersupply(DLM):
    print("Configuring Magnet Power Supply...")
    
    DLM.timeout = TIMEOUT_DLM   # in milliseconds
    print(DLM.query('*IDN?'))   # identify
    DLM.write('*CLS')           # clear status
    DLM.write('*RST')           # reset 
    print(DLM.query('*TST?'))   # check for issues
    
    DLM.write("SOUR:VOLT 20")                   # set voltage to low level but high enough for current control
    DLM.write(f'SOUR:CURR {start_current}')     # sets low current before enabling output to ensure no large changes

    # DLM.write('OUTP 1') 
    print("Magnet Power Supply configured and output ON.")



def write_S_params(file_name: str):
    '''Saves S11 and S21 (or simply trace 1 and 2) to csv file named on the field strength given by file_name
    The file is saved in the measurement folder located in the same directory as this script.
    
    The function assumes the VNA has been set up to have trace 1 as S11 log mag and trace 2 as S21 log mag.
    '''


    CMT.write("TRIG:SOUR BUS")
    CMT.write("TRIG:SING")
    CMT.query("*OPC?")
    
    # save a csv file of all traces - according to set up above, there are 2 traces: S11 log mag and S11 log mag
    CMT.write("MMEM:STOR:FDAT:SCOP ALL")
    command = f'MMEM:STOR:FDAT  {file_name}' # saves files to folder measurement in the same directory as this script

    CMT.write(command)

    # S21 = CMT.query_ascii_values("CALC1:DATA:FDAT?")
    # S21 = S21[::2]

    # print("S21 Log mag=")
    # print(S21)


    # set trigger source back to internal to keep the VNA sweeping and warm
    CMT.write("TRIG:SOUR INT")

    CMT.write("DISP:WIND:TRAC1:Y:AUTO") # auto scale the trace1 (S11) after each measurement
    CMT.write("DISP:WIND:TRAC2:Y:AUTO") # auto scale the trace2 (S21) after each measurement


    return


def set_magnetic_field(B_field: float):
    '''Sets the magnetic field to B_field in Tesla.
    
    This has not yet been finished, still figuring out the magnet.
    '''

    # Look up current needed for B field from calibration data. (could open the csv file pre-emptively and interpolate)

    B_current = calibration_interpolation[calibration_interpolation["B"]==B_field]["Current"].values[0]

    # voltage = 2 # placeholder

    # set power to give expected B

    err = DLM.query("SYST:ERR?")
    print(err)
    DLM.write("*CLS")

    # DLM.write(f'VOLT {voltage}')      # set voltage in Volts - CHANGE THIS ACCORDING TO CALIBRATION
    DLM.write(f'SOUR:CURR {B_current}')    # set current in Amps - assuming 0.1 T per Amp - CHANGE THIS FACTOR ACCORDING TO CALIBRATION
    sleep(B_DELAY)


    # current_step = 0.01

    # Write current and loop until the actual current is within 0.005 of the requested current - ensure the field is as close to the calibration

    actual_current = float(DLM.query('MEAS:CURR?'))
    # while abs(actual_current - B_current) >= 0.05:
    #     if actual_current > B_current:
    #         update_current = B_current - current_step

    #     elif actual_current < B_current:
    #         update_current = B_current + current_step

    #     DLM.write(f'SOUR:CURR {update_current}')
    #     sleep(B_DELAY)

    #     actual_current = float(DLM.query('MEAS:CURR?'))
    #     sleep(B_DELAY)
    #     print(f'requested current:{B_current}, actual current:{actual_current}, difference:{actual_current - B_current}')

    #     if abs(MAX_CURRENT - actual_current) < 5:
    #         raise ValueError("Current too high")


    sleep(B_DELAY)  # time delay for setting the field


    return actual_current


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




## Main #############

if __name__== "__main__":

    

    # imports calibrated data, extrapolates current needed for fields in experiment.

    try:
        if (max(B_fields) >= MAX_B
        or min(B_fields) < MIN_B
        or abs(B_step) <= MIN_B_STEP):
            raise ValueError("Requested current sweep incompatible with power supply limits. Check min, max and step-size")
    

        rm = pv.ResourceManager()
        cxns = rm.list_resources()
        print(cxns)
        # Check VNA connection
        
        # if not (TCPIP_ID_S2VNA in cxns):
            # raise RuntimeError("Cannot access VNA. Check connection and address")


        # Check power supply connection
        if not (GPIB_ID_DLM in cxns):
            raise RuntimeError("Cannot access Magnet Power Supply. Check connection and address")
            # pass
        # DLM = rm.open_resource(GPIB_ID_DLM)

        
        with rm.open_resource(TCPIP_ID_S2VNA) as CMT, rm.open_resource(GPIB_ID_DLM) as DLM:

        # with rm.open_resource(TCPIP_ID_S2VNA) as CMT:
        # CMT = rm.open_resource(TCPIP_ID_S2VNA)
            configure_VNA(CMT)
            print(f'Connection to {TCPIP_ID_S2VNA} configured')

            if CMT.query('*TST?') != '0':     #TST is the self test command for the CMT and I thought might be the most appropriate considering cxns does not work TODO - this might have been fixed since updating drivers, check.
                print(CMT.query('SYST:TEST?'))
                raise RuntimeError("one or more failure conditions found in CMT VNA")

            configure_powersupply(DLM)
            print(f'Connection to {GPIB_ID_DLM} configured')


            # if CMT.query('*TST?') != '0':     #TST is the self test command for the CMT and I thought might be the most appropriate considering cxns does not work TODO - this might have been fixed since updating drivers, check.
            #     print(CMT.query('SYST:TEST?'))
            #     raise RuntimeError("one or more failure conditions found in CMT VNA")
            
                

            calibrated, calibration_interpolation, calibration_slope, calibration_intercept = get_calibrated_B_curr()

            if calibrated == False:
                raise RuntimeError("There is no calibration data, needed to control magnet")


            fields_current = [['Field (T)', 'Current (A)']]

            for B0 in tqdm(B_fields):


                current_used = set_magnetic_field(B0)

                field_used = (current_used - calibration_intercept)/calibration_slope

                fields_current.append([{field_used}, {current_used}])

                name_of_test = f'{SAVE_PATH}\\{sample}_B_field_{field_used:.4f}.csv'


                write_S_params(name_of_test)

                sleep(delay)   # unit is in seconds
            
            # before the program finishes, set trigger source back to internal
            CMT.write("TRIG:SOUR INT\n")

            DLM.write('*RST')    # resets GMW magnet power supply to safe state


    except RuntimeError as e1:
        print(f"There is an error within the set up: {e1}")

    except Exception as e2:
        print(f"Error in current sweep loop: Need to debug!")

    except ValueError as e3:
        print("Unsafe values entered, check definitions")

    finally:    
        df_fields = pd.DataFrame(fields_current[1:], columns=fields_current[0])
        df_fields.to_csv(f'{SAVE_PATH}\\currents_used.csv', index=False)

    print("Done")


