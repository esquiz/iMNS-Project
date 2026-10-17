import time
import numpy as np
import pandas as pd
import pyvisa as pv
import scipy as sc
import os
import datetime
from tqdm import tqdm


######## USER INPUT ########

file_dir = os.path.dirname(os.path.realpath(__file__))

now = datetime.datetime.now()

SAVE_PATH = f'{file_dir}\\data\\B_curr_calibration_{now.strftime("%d-%m-%Y")}.csv'

## Teslameter setup
GPIB_ID_MAG = 'GPIB0::1::INSTR'
TIMEOUT_MAG = 2.0
COMMAND_BUFFER_MAG = 0.25 # can read much faster than Hirst
READ_TERM = '\n'
WRITE_TERM = '\r'
MAG_RANGE = 'R0'        # R1 = 0.6 Tesla range, R0 = 0.3 Tesla range
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

# Magnet Power Supply setup
GPIB_ID_KEPCO = 'GPIB1::6::INSTR'   #changed GPIB0 to GPIB1 should allow for two connections
READ_TERM_KEPCO = '\n'
WRITE_TERM_KEPCO = '\n'
TIMEOUT_KEPCO = 5000    # in milliseconds CHECK SPECIFICATION

B_delay = 2 * 1         # time to wait for magnet to settle after setting field - unit is in seconds
input_current_min = -0.66   # check units with manufacturer
input_current_max = 0.66
current_step = 0.05

current_sweep = np.arange(input_current_min, input_current_max + current_step, current_step)    
# current_sweep = [f'{num:.2e}' for num in current_sweep_num]


# Limits for safety. TODO Check all values with manufacturer
MAX_CURRENT = 2     #amps
MIN_CURRENT = -2     #amps
MIN_CURRENT_STEP = 0.009     # min current step in amps


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
    return mag_zero


def configure_kepco(kepco):
    print("Configuring Kepco Magnet Power Supply...")
    # kepco.write('*RST')
    kepco.read_termination = READ_TERM_KEPCO
    kepco.write_termination = WRITE_TERM_KEPCO
    kepco.timeout = TIMEOUT_KEPCO  # in milliseconds
    print(kepco.query('*IDN?'))

    kepco.write('REMOTE')

    # kepco.write('INIT:CONT ON')
    # kepco.write('VOLT 22')

    # print(kepco.query('*TST?'))

    kepco.write('OUTPut ON') 
    print("Kepco Magnet Power Supply configured and output ON.")




if __name__== "__main__":    
    ''' Main measurement loop '''

    if (max(current_sweep) >= MAX_CURRENT
        or min(current_sweep) <= MIN_CURRENT
        or abs(current_step) <= MIN_CURRENT_STEP):
        raise ValueError("Requested current sweep incompatible with power supply limits. Check min, max and step-size")


    try:
        rm = pv.ResourceManager()
        cxns = rm.list_resources()
        # Check teslameter connection
        if not (GPIB_ID_MAG in cxns):
            raise RuntimeError("Cannot access teslameter. Check connection and address")
        # Check Kepco connection
        if not (GPIB_ID_KEPCO in cxns):
            raise RuntimeError("Cannot access Kepco Magnet Power Supply. Check connection and address")
        
        #### Context manager for hardware connections ####
        with rm.open_resource(GPIB_ID_MAG) as g3, rm.open_resource(GPIB_ID_KEPCO) as kepco:
            print(f"\nConnection to {GPIB_ID_MAG} established")
            offset = configure_teslameter(g3)
            print(f"\nConnection to {GPIB_ID_KEPCO} established")
            configure_kepco(kepco)

            t0 = time.perf_counter()
            kepco.write("FUNC:MODE CURR")
            kepco.write('CURR 0')
            # time.sleep(2)

            scan_data = [["H(y) (T)", "Error H(y) (T)", "Current (A)","Actual Current (A)"]]

            for n, B_current in enumerate(current_sweep):
                # Set current                  
                print(B_current)
                # kepco.write('*CLS')
                # time.sleep(2)
                kepco.write("OUTP OFF")
                if B_current >= 0:
                    kepco.write(f'VOLT 17;CURR {B_current:.3}')  
                elif B_current < 0:
                    kepco.write(f'VOLT -17;CURR {B_current:.3}')
                # time.sleep(2)
                kepco.write('OUTP ON')      # set current in Amps - assuming 0.1 T per Amp - TODO CHANGE THIS FACTOR ACCORDING TO CALIBRATION
                time.sleep(B_delay)                     # wait for magnet to settle
                actual_current = float(kepco.query("MEAS:CURR?"))               # query actual current
                time.sleep(2)
                kepco.write('*WAI')

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
                H_avg = np.mean(H_val)#-float(offset)
                err_H = sc.stats.sem(H_val)
                print(f"Hy: {H_avg:.2e} +/- {err_H:.2e} T")
                
                # Append data
                scan_data.append([H_avg, err_H, B_current, actual_current])   

                print(f"Set Current: {B_current:.3f} A, Reported Current: {actual_current:.3f}, Measured Field: {H_avg:.3f} T\n")

                print(kepco.query('SYST:ERR?'))

                print(f"Scan {(100*(n+1)/len(current_sweep)):.1f}% complete.\n")


            print("\nResetting power supply to safe state")
            kepco.write('*RST')             # resets power supply to output off - zero volts, and min current


    except RuntimeError as e1:
        print(f"Error during measurement loop: {e1}")
    except Exception as e2:
        print(f"Error in current sweep loop: Need to debug!")
        # kepco.write('*RST')

    finally:
        print("\nWriting data...")
        # Use first list in scan data as headers, use remaining for data
        df_all_data = pd.DataFrame(scan_data[1:], columns=scan_data[0])
        df_all_data.to_csv(SAVE_PATH, index=False)

    

    
