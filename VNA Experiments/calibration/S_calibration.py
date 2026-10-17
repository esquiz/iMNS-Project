import numpy as np
import os
import pyvisa as pv   #PyVisa is required along with NIVisa
from time import sleep
import pandas as pd
import time
import datetime



##########


'''  A 2 millisecond delay between the Write and Read 
functions will be sufficient to insure that there is enough time to receive a response for all valid 
queries.   From specification '''





TCPIP_ID_S2VNA = 'TCPIP0::127.0.0.1::5025::SOCKET'      # had to change to 5026 instead of 5025 port for some reason (VNA would not connect to 5025)
TERMINATION_VNA = '\n'
TIMEOUT_VNA = 10000



#################################################################################################################

##### Definitions #####


delay = 1 * 1               # unit is in seconds - delay between measurements

start_freq = 0*1e9          # Frequency centre in Hz
end_freq = 16*1e9           # Frequency Range in Hz
num_points = 4001           # Number of points

num_measurements = 10        # number of measurements to take (each makes a new csv file)



# get the directory where this python script is located
file_path = os.path.dirname(os.path.realpath(__file__))

now = datetime.datetime.now()

# name of sample being measured - used for saving csv file
sample_name = "YIG" 
# sample_name = "PY"

experiment_temp = 'RT'


try:
    dir_path = f'{file_path}\\data\\{now.strftime("%d-%m-%Y")}'
    os.mkdir(dir_path)


    print(f"Directory '{dir_path}' created successfully.")
except FileExistsError:
    print(f"Directory '{dir_path}' already exists.")
except PermissionError:
    print(f"Permission denied: Unable to create '{dir_path}'.")
except Exception as e:
    print(f"An error occurred: {e}")


SAVE_PATH = f'{file_path}\\data\\{now.strftime("%d-%m-%Y")}\\S_calibration_{sample_name}_{now.strftime("%H-%M-%S")}.csv'


MAX_B = 1           #tesla


# # Magnet Power Supply setup
# GPIB_ID_KEPCO = 'GPIB0::8::INSTR'   #changed GPIB0 to GPIB1 should allow for two connections
# READ_TERM_KEPCO = '\n'
# WRITE_TERM_KEPCO = '\n'
# TIMEOUT_KEPCO = 5000    # in milliseconds CHECK SPECIFICATION



GPIB_ID_DLM = 'GPIB0::7::INSTR'   #changed GPIB0 to GPIB1 should allow for two connections

TIMEOUT_DLM = 5000    # in milliseconds CHECK SPECIFICATION

MAX_VOLTAGE = 80.0
MAX_CURRENT = 37.0
MIN_VOLTAGE = 0.0
MIN_CURRENT = 0.0 

start_current = 0.01



B_delay = 3     # seconds

B_current = 8.0   # amps needed to fully saturate sample



#################################################################################################################



## VNA Setup ####################################################################################################



#################################################################################################################

def write_S_params(S_param_choice):
    '''Returns S21 as an array for each of the frequencies scanned through
    could be updated to include S11 as well for full calibration.
    
    The function assumes the VNA has been set up to have trace 1 as S11 log mag and trace 2 as S21 log mag.
    '''


    CMT.write("TRIG:SOUR BUS")
    CMT.write("TRIG:SING")
    CMT.query("*OPC?")
    
    # save a csv file of all traces - according to set up above, there are 2 traces: S11 log mag and S11 log mag
    CMT.write("MMEM:STOR:FDAT:SCOP ALL")
    # command = f'MMEM:STOR:FDAT  {file_name}' # saves files to folder measurement in the same directory as this script

    if S_param_choice == 'S11':

        CMT.write('CALC1:PAR1:SEL') #selectrs trace 1 which is set up to be S11

    if S_param_choice == 'S21':

        CMT.write('CALC1:PAR2:SEL') # Selects trace 2 which is set up to be S21

    S_values = CMT.query_ascii_values("CALC1:DATA:FDAT?") #PAR1 = S11; PAR2 = S21
    # print(S_values)
    S_values = S_values[::2]



    # print("S21 Log mag=")
    # print(S21)

    # CMT.write(command)
    
    # set trigger source back to internal to keep the VNA sweeping and warm
    CMT.write("TRIG:SOUR INT")

    CMT.write("DISP:WIND:TRAC1:Y:AUTO") # auto scale the trace1 (S11) after each measurement
    CMT.write("DISP:WIND:TRAC2:Y:AUTO") # auto scale the trace2 (S21) after each measurement

    return S_values


# def configure_kepco(kepco):
#     print("Configuring Kepco Magnet Power Supply...")
#     kepco.read_termination = READ_TERM_KEPCO
#     kepco.write_termination = WRITE_TERM_KEPCO
#     kepco.timeout = TIMEOUT_KEPCO  # in milliseconds
#     print(kepco.query('*IDN?'))
#     kepco.write('OUTPut ON') 
#     print("Kepco Magnet Power Supply configured and output ON.")


def configure_powersupply(DLM):
    print("Configuring Magnet Power Supply...")
    
    DLM.timeout = TIMEOUT_DLM   # in milliseconds
    print(DLM.query('*IDN?'))   # identify
    DLM.write('*CLS')           # clear status
    DLM.write('*RST')           # reset 
    print(DLM.query('*TST?'))   # check for issues
    
    DLM.write("SOUR:VOLT 15")                   # set voltage to low level but high enough for current control
    DLM.write(f'SOUR:CURR {start_current}')     # sets low current before enabling output to ensure no large changes

    # DLM.write('OUTP 1') 
    print("Magnet Power Supply configured and output ON.")


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

def dB_to_linear(x_dB):

    return 10**(x_dB/10)

def linear_to_dB(x_lin):

    return 10*np.log10(x_lin)



if __name__== "__main__":


    try:
        rm = pv.ResourceManager()
        cxns = rm.list_resources()
        print(cxns)
        # Check VNA connection
        
        # if not (TCPIP_ID_S2VNA in cxns):
        #     raise RuntimeError("Cannot access VNA. Check connection and address")

        # removed because pyvisa does not have usb resources added to it

        # Check Kepco connection
        # if not (GPIB_ID_DLM in cxns):
        #     raise RuntimeError("Cannot access Kepco Magnet Power Supply. Check connection and address")
            # pass
        # DLM = rm.open_resource(GPIB_ID_DLM)

        # with rm.open_resource(TCPIP_ID_S2VNA) as CMT:
        CMT = rm.open_resource(TCPIP_ID_S2VNA)
        configure_VNA(CMT)


        if CMT.query('*TST?') != '0':     #TST is the self test command for the CMT and I thought might be the most appropriate considering cxns does not work TODO - this might have been fixed since updating drivers, check.
            print(CMT.query('SYST:TEST?'))
            raise RuntimeError("one or more failure conditions found in CMT VNA")
        

            
        # print(f'Connection to {GPIB_ID_DLM} configured')
        # configure_powersupply(DLM)

        print(f'Connection to {TCPIP_ID_S2VNA} configured')
        

            # set field to beyond sample saturation

        # DLM.write('SOUR:VOLT 20')
        # time.sleep(B_delay)

        # DLM.write(f'SOUR:CURR {B_current}')        # set current in Amps - assuming 0.1 T per Amp - TODO CHANGE THIS FACTOR ACCORDING TO CALIBRATION
        # time.sleep(5)                     # wait for magnet to settle
        # actual_current = float(DLM.query('MEAS:CURR?'))
        # print(actual_current)

            # take measurements 

        S21_vals = pd.DataFrame()
        S11_vals = pd.DataFrame()
        # print(S21_vals)

        for n in range(num_measurements):
            # write_S_params(f'{file_path}\\S_calibration\\measurement_{n}')
            S21_raw = write_S_params("S21")
            S11_raw = write_S_params("S11")

            S21_vals[f'{n}'] = S21_raw
            S21_vals[f'{n}'] = S21_vals[f'{n}'].apply(dB_to_linear)
            S11_vals[f'{n}'] = S11_raw
            S11_vals[f'{n}'] = S11_vals[f'{n}'].apply(dB_to_linear)


        S21_vals['Average'] = S21_vals.mean(axis=1)
        S21_vals['Average'] = S21_vals['Average'].apply(linear_to_dB)
        S11_vals['Average'] = S11_vals.mean(axis=1)
        S11_vals['Average'] = S11_vals['Average'].apply(linear_to_dB)
    

        print("\nResetting power supply to safe state")
        # kepco.write('*RST')             # resets power supply to output off - zero volts, and min current


    except RuntimeError as e1:
        print(f"Error during measurement loop: {e1}")
    except Exception as e2:
        print(f"Error in current sweep loop: Need to debug!")

    finally:
        print(f'\nPrinting Average values to dataframe in calibration folder:{SAVE_PATH}')


        with open(SAVE_PATH, 'w') as f:
            f.write(f'! S21 and S11 {sample_name} at {experiment_temp} for LN2 experiment set up\n')
            f.write(f'! Amplifiers = off\n')
            f.write(f'! number of points averaged: {num_measurements}\n')
            

        S21_vals = S21_vals.reset_index()

        # print(S21_vals.head())

        df_data = pd.DataFrame()
        df_data['!Frequency (Hz)'] = np.linspace(start=3e5, stop=end_freq, num=num_points)
        df_data[['S21 (dB)']] = S21_vals.loc[:,['Average']]
        df_data['S11 (dB)'] = S11_vals.loc[:,'Average']
 

        # print(df_data)

        df_data.to_csv(SAVE_PATH, index=False, mode='a')

