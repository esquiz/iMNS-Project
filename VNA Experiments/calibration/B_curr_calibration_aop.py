import time
import numpy as np
import pandas as pd
import pyvisa as pv
import scipy as sc
import os
import datetime
import tqdm

######## USER INPUT ########

file_dir = os.path.dirname(os.path.realpath(__file__))

now = datetime.datetime.now()

SAVE_PATH = f'{file_dir}\\data\\B_curr_calibration_{now.strftime("%d-%m-%Y")}.csv'
# print(SAVE_PATH)

## Teslameter setup
GPIB_ID_MAG = 'GPIB0::1::INSTR'
TIMEOUT_MAG = 2.0
COMMAND_BUFFER_MAG = 0.25 # can read much faster than Hirst
READ_TERM = '\n'
WRITE_TERM = '\r'
MAG_RANGE = 'R0'        # R1 = 0.6 Tesla range
ACDC_MODE = 'GD'        # GD = DC mode
TRIGGER_MODE = 'SM0'    # SM0 = Manual read
UNITS = 'UFT'           # UFT = Tesla, UFG = Gauss
WRITE_UNITS = 'SU0'     # SU0 =  units off
GET_ZERO_OFFSET = 'IZ'
GET_DATA = 'F'
DIGITAL_FILTER = 'D1'

# Sampling
sampling = 10    # number of measurements to average per field
t_sample = 0.5

######################################################################################################

# Magnet Power Supply setup
# GPIB_ID_KEPCO = 'GPIB1::8::INSTR'   #changed GPIB0 to GPIB1 should allow for two connections
# READ_TERM_KEPCO = '\n'
# WRITE_TERM_KEPCO = '\n'
# TIMEOUT_KEPCO = 5000    # in milliseconds CHECK SPECIFICATION


GPIB_ID_DLM = 'GPIB1::7::INSTR'   #changed GPIB0 to GPIB1 should allow for two connections

TIMEOUT_DLM = 5000    # in milliseconds CHECK SPECIFICATION

MAX_VOLTAGE = 80.0
MAX_CURRENT = 37.0
MIN_VOLTAGE = 0.0
MIN_CURRENT = 0.0 

'''The sepcification of DLM power supply is unipolar and such can only have positive voltages and currents.'''


B_DELAY = 3     # seconds
start_current = 0.01


# B_delay = 2 * 1         # time to wait for magnet to settle after setting field - unit is in seconds
input_current_min = 0.01   # check units with manufacturer
input_current_max = 8.0
current_step = 0.01

current_sweep = np.arange(input_current_min, input_current_max + current_step, current_step)    

# Limits for safety. As Listed in specification it is rated for \pm 5 Amps in D.C. 
# MAX_CURRENT = 5     #amps
# MIN_CURRENT = -5     #amps
MIN_CURRENT_STEP = 0.005     # min current step in amps


'''Maximum voltage for power supply is pm 10V 
The output current per channel is 0 to pm 2mA max
I dont know how the per channel might change things.

This may be different than that for the coils'''


# From g3_field_scan.py
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
    telsameter.write('Z')
    time.sleep(COMMAND_BUFFER_MAG)
    telsameter.write(GET_ZERO_OFFSET)
    mag_zero = telsameter.read()
    print(f"\nTeslameter configured. Offset = {mag_zero} T")


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

    





if __name__== "__main__":    
    ''' Main measurement loop '''

    if (max(current_sweep) >= MAX_CURRENT
        or min(current_sweep) <= MIN_CURRENT
        or abs(current_step) <= MIN_CURRENT_STEP):
        raise ValueError("Requested current sweep incompatible with power supply limits. Check min, max and step-size")

    scan_data = [["H(y) (T)", "Error H(y) (T)", "Current (A)","Actual Current (A)"]]

    try:
        rm = pv.ResourceManager()
        cxns = rm.list_resources()
        print(cxns)
        # Check teslameter connection
        if not (GPIB_ID_MAG in cxns):
            raise RuntimeError("Cannot access teslameter. Check connection and address")
        # Check Kepco connection
        if not (GPIB_ID_DLM in cxns):
            raise RuntimeError("Cannot access DLM Magnet Power Supply. Check connection and address")
        
        #### Context manager for hardware connections ####
        with rm.open_resource(GPIB_ID_MAG) as g3, rm.open_resource(GPIB_ID_DLM) as DLM:
            print(f"\nConnection to {GPIB_ID_MAG} established")
            configure_teslameter(g3)
            print(f"\nConnection to {GPIB_ID_DLM} established")
            configure_powersupply(DLM)

            t0 = time.perf_counter()
            for n, B_current in enumerate(current_sweep):
                # Set current                  
                DLM.write(f'SOUR:CURR {B_current:.3f}')        # set current in Amps - assuming 25mT per Amp - TODO CHANGE THIS FACTOR ACCORDING TO CALIBRATION
                time.sleep(B_DELAY)                     # wait for magnet to settle
                actual_current = float(DLM.query("MEAS:CURR?"))           # query actual current
                

                # Read field
                H_val = np.zeros(sampling)
                for k in range(sampling):

                    # Send "take data" command, let command process
                    t1 = time.perf_counter()
                    g3.write(GET_DATA)
                    time.sleep(COMMAND_BUFFER_MAG)

                    # Send "read output" command, let command process
                    t2 = time.perf_counter()
                    H_val_raw = g3.read()
                    H_val[k] = float(H_val_raw)
                    dt = time.perf_counter()-t2
                    if COMMAND_BUFFER_MAG > dt:
                        time.sleep(COMMAND_BUFFER_MAG-dt)
                
                # Calculate sample avg and SE
                H_avg = np.mean(H_val)
                err_H = sc.stats.sem(H_val)
                print(f"Hy: {H_avg:.2e} +/- {err_H:.2e} T")
                
                # Append data
                scan_data.append([H_avg, err_H, B_current, actual_current])  

                print(f'Set Current: {B_current:.2e} A, Reported Current: {actual_current:.2e}, Measured Field: {H_avg:.2e} T')

                t_loop = int(time.perf_counter() - t0)
                print(f"Scan {(100*(n+1)/len(current_sweep)):.1f}% complete. Runtime {t_loop:.0f} s\n")


            print("\nResetting power supply to safe state")
            DLM.write('*RST')             # resets power supply to output off - zero volts, and min current


    except RuntimeError as e1:
        print(f"Error during measurement loop: {e1}")

    except Exception as e2:
        print(f"Error in current sweep loop: Need to debug!")

    finally:
        print("\nWriting data...")
        # Use first list in scan data as headers, use remaining for data
        df_all_data = pd.DataFrame(scan_data[1:], columns=scan_data[0])
        df_all_data.to_csv(SAVE_PATH, index=False)

    

    
