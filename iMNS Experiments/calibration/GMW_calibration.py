import numpy as np
import os
import pyvisa as pv   #PyVisa is required along with NIVisa
from time import sleep
import pandas as pd
import time
import scipy as sc
from tqdm import tqdm



#################################################################
#   DLM commands    #


GPIB_ID_DLM = 'GPIB0::7::INSTR'   #changed GPIB0 to GPIB1 should allow for two connections

TIMEOUT_DLM = 5000    # in milliseconds CHECK SPECIFICATION

MAX_VOLTAGE = 80.0
MAX_CURRENT = 37.0
MIN_VOLTAGE = 0.0
MIN_CURRENT = 0.0 



#################################################################
#   kepco commands  #

GPIB_ID_KEPCO = 'GPIB1::6::INSTR'   #changed GPIB0 to GPIB1 should allow for two connections
READ_TERM_KEPCO = '\n'
WRITE_TERM_KEPCO = '\n'
TIMEOUT_KEPCO = 5000    # in milliseconds CHECK SPECIFICATION


################################################################
#   teslameter comands  #

GPIB_ID_MAG = 'GPIB2::1::INSTR'
TIMEOUT_MAG = 2.0
COMMAND_BUFFER_MAG = 0.25 # can read much faster than Hirst
READ_TERM = '\n'
WRITE_TERM = '\r'
MAG_RANGE = 'R1'        # R1 = 0.6 Tesla range
ACDC_MODE = 'GD'        # GD = DC mode
TRIGGER_MODE = 'SM0'    # SM0 = Manual read
UNITS = 'UFT'           # UFT = Tesla, UFG = Gauss
WRITE_UNITS = 'SU0'     # SU0 =  units off
GET_ZERO_OFFSET = 'IZ'
GET_DATA = 'F'
DIGITAL_FILTER = 'D1'




################################################################
#   test parameters #

B_DELAY = 3     # seconds


start_current = 0.1

# Sampling
sampling = 10    # number of measurements to average per field
t_sample = 0.5


MAX_FIELD = 0.2

min_curr_sweep = 0.0
max_curr_sweep = 8.0
curr_sweep_step = 0.0001

curr_sweep = np.arange(min_curr_sweep, max_curr_sweep + curr_sweep_step, curr_sweep_step)









################################################################
#   functions   #

#config kepco

def configure_kepco(kepco):
    print("Configuring Kepco Magnet Power Supply...")
    kepco.read_termination = READ_TERM_KEPCO
    kepco.write_termination = WRITE_TERM_KEPCO
    kepco.timeout = TIMEOUT_KEPCO  # in milliseconds
    print(kepco.query('*IDN?'))
    kepco.write('SYST:REM')
    kepco.write('SYST:PASS:CEN DEFAULT')
    # kepco.write('DIAG:PST 20,5')
    print(kepco.query('*TST?'))
    
    kepco.write('OUTPut ON') 
    print("Kepco Magnet Power Supply configured and output ON.")

    

#config dlm

def configure_powersupply(DLM):
    print("Configuring Kepco Magnet Power Supply...")
    
    DLM.timeout = TIMEOUT_DLM   # in milliseconds
    print(DLM.query('*IDN?'))   # identify
    DLM.write('*CLS')           # clear status
    DLM.write('*RST')           # reset 
    print(DLM.query('*TST?'))   # check for issues
    
    DLM.write("SOUR:VOLT 15")                   # set voltage to low level but high enough for current control
    DLM.write(f'SOUR:CURR {start_current}')     # sets low current before enabling output to ensure no large changes

    DLM.write('OUTPut ON') 
    print("Kepco Magnet Power Supply configured and output ON.")

#config teslameter

def configure_teslameter(telsameter):
    print(f"Configuring...")
    # Set configuration
    telsameter.read_termination = READ_TERM
    telsameter.write_termination = WRITE_TERM
    telsameter.write(MAG_RANGE)
    time.sleep(COMMAND_BUFFER_MAG)
    telsameter.write(ACDC_MODE)
    time.sleep(COMMAND_BUFFER_MAG)
    telsameter.write(TRIGGER_MODE)
    time.sleep(COMMAND_BUFFER_MAG)
    telsameter.write(WRITE_UNITS)
    time.sleep(COMMAND_BUFFER_MAG)
    telsameter.write(GET_ZERO_OFFSET)
    mag_zero = telsameter.read()
    print(f"\nTeslameter configured. Offset = {mag_zero} T")
    return mag_zero


# Write and read currents

def write_kepco(kepco, curr):

    kepco.write(f'CURR {curr}')
    time.sleep(B_DELAY)

    actual_curr = kepco.query(f'MEAS:CURR?')

    return actual_curr

def write_DLM(DLM, curr):

    DLM.write("SOUR:VOLT 20")
    DLM.write(f'SOUR:CURR {curr}')    # set current in Amps - assuming 0.1 T per Amp - CHANGE THIS FACTOR ACCORDING TO CALIBRATION
    time.sleep(B_DELAY)

    actual_curr = DLM.query("MEAS:CURR?")            
    
    return actual_curr


def meas_ave_field(B_current, actual_current):
        
    # scan_data = [["H(y) (T)", "Error H(y) (T)", "Current (A)","Actual Current (A)"]]
    scan_data = [[]]

    # Read field
    H_val = np.zeros(sampling)
    for k in range(sampling):

        # Send "take data" command, let command process
        g3.write(GET_DATA)
        time.sleep(COMMAND_BUFFER_MAG)

        # Send "read output" command, let command process
        H_val_raw = g3.read()
        H_val[k] = float(H_val_raw) - magnet_offset

    
    # Calculate sample avg and SE
    H_avg = np.mean(H_val)
    err_H = sc.stats.sem(H_val)
    print(f"Hy: {H_avg:.3e} +/- {err_H:.3e} T")
    
    # Append data
    scan_data.append([H_avg, err_H, B_current, actual_current])  

    print(f'Set Current: {B_current:.4e} A, Reported Current: {actual_current:.4e}, Measured Field: {H_avg:.4e} T')

    return scan_data



#check resolution (only run once?)

def check_res_powersupply(handle, current_range: list):
    print(f'Finding {handle} field resolution...')





    












##############################################################
#   main    #


if __name__== "__main__":    
    ''' Main measurement loop '''

    try:
        rm = pv.ResourceManager()
        cxns = rm.list_resources()

        # Check teslameter connection
        if not (GPIB_ID_MAG in cxns):
            raise RuntimeError("Cannot access teslameter. Check connection and address")
        
        # Check Kepco connection
        if not (GPIB_ID_DLM in cxns):
            raise RuntimeError("Cannot access DLM Magnet Power Supply. Check connection and address")
        
        # Check DLM
        if not (GPIB_ID_KEPCO in cxns):
            raise RuntimeError("Cannot access Kepco power supply. Check connection and address")
        
        #### Context manager for hardware connections ####
        with rm.open_resource(GPIB_ID_MAG) as g3, rm.open_resource(GPIB_ID_DLM) as DLM, rm.open_resource(GPIB_ID_KEPCO) as kepco:
            
            #   setups
            print(f'Configured {GPIB_ID_DLM}')
            configure_powersupply(DLM)

            print(f'Configured {GPIB_ID_KEPCO}')
            configure_kepco(kepco)

            print(f'Configured {GPIB_ID_MAG}')
            magnet_offset = configure_teslameter(g3)

            #   resolution for kepco
            kepco_currents = []
            resolution_kepco = check_res_powersupply(kepco, kepco_currents)

            #   resolution for dlm
            DLM_currents = []
            resolution_DLM = check_res_powersupply(DLM, DLM_currents)

            #   run full calibration
            
            cal_data = [["H(y) (T)", "Error H(y) (T)", "Current (A)","Actual Current (A)"]]

            for current in tqdm(curr_sweep):
                rough_curr = current // resolution_DLM

                fine_curr = current % resolution_DLM

                actual_DLM_curr = write_DLM(DLM, rough_curr)
                actual_kepco_curr = write_kepco(kepco, fine_curr)

                field_measured = meas_ave_field(current, actual_DLM_curr+actual_kepco_curr)

                cal_data.append(field_measured)


    except RuntimeError as e1:
        print(f"Error during measurement loop: {e1}")

    except Exception as e2:
        print(f"Error in current sweep loop: Need to debug!")

    finally:

        df_all_data = pd.DataFrame(cal_data[1:], columns=cal_data[0])

        print('Done')

