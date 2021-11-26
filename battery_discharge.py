"""
Script: battery_discharge.py
Writen by: Mike Fikes
Original TSP version written by: Keithley Applications Engineering (Al Ivons)

***********************************************************
*** Copyright 2017 Tektronix, Inc.                      ***
*** See www.tek.com/sample-license for licensing terms. ***
***********************************************************

Revision History:
        * This Python port originally released Nov 2021.

This script is example code designed to discharge a battery and create a battery model for use
in a Keithley Model 2281S-20-6 Battery Simulator and Precision DC Power Supply.  It will drive
any of the following Keithley instruments:

        * Model 2400 SourceMeter

WARNING:        This script presently does not include any safeguards to prevent the user from 
                discharging a LITHIUM ION battery beyond safe limits.  It is the user's responsibility 
                to follow all manufacturer's guidelines when setting the discharge current and cut-off 
                voltage for a LITHIUM ION battery to ensure safe operation of the test setup and program.

"""

from pymeasure.instruments.keithley import Keithley2400
from pymeasure.adapters import PrologixAdapter
from datetime import datetime
import time
import inquirer

# ********** Instrument communication **********

# Revise to set smu variable for your particular GPIB / Serial Setup

# Prologix USB to GPIB

adapter = PrologixAdapter('/dev/cu.usbserial-PXEFMYB9', serial_timeout=0.2)
smu = Keithley2400(adapter.gpib(26))

# USB to RS-232 cable

#smu = Keithley2400('ASRL/dev/cu.usbserial-FTCGVYZA::INSTR',
#                   baud_rate=9600, write_termination='\r', read_termination='\r')

# ********** Declare global tables **********

TEST_PARAM = {}   # Global table to hold various test parameters and share them among different functions

BATT_MODEL_RAW = {}	             # Global table to hold "raw" measured and calculated data for battery model
BATT_MODEL_RAW["voc"] = []           # Global table to hold all measured open-circuit voltage values
BATT_MODEL_RAW["vload"] = []         # Global table to hold all voltage values measured at load (i.e. discharge) current
BATT_MODEL_RAW["esr"] = []           # Global table to hold all measured/calculated internal resistance values
BATT_MODEL_RAW["tstamp"] = []        # Global table to hold all timestamp values

BATT_MODEL = {}	                     # Global table to hold final model values extracted from BATT_MODEL_RAW
BATT_MODEL["voc"] = [None] * 101     # Global table to hold final open-circuit voltage values extracted from BATT_MODEL_RAW["voc"]
BATT_MODEL["vload"] = [None] * 101   # Global table to hold final voltage-at-load values extracted from BATT_MODEL_RAW["vload"]
BATT_MODEL["esr"] = [None] * 101     # Global table to hold final internal resistance values extracted from BATT_MODEL_RAW["esr"]
BATT_MODEL["tstamp"] = [None] * 101  # Global table to hold final timestamp values extracted from BATT_MODEL_RAW["tstamp"]
BATT_MODEL["soc"] = [None] * 101     # Global table to hold state-of-charge values (0 to 100%, in 1% increments)

# ********** Define Utility Functions **********

def delay(interval):
    time.sleep(interval)

def prompt_choice(prompt, choices):
    questions = [
        inquirer.List('choice',
                      message=prompt,
                      choices=choices,
                      ),
        ]
    answers = inquirer.prompt(questions)
    return answers["choice"]

def Dround(v,d):
    return round(v,d)

def meas_esr(test_curr, settle_time):

    # load_curr and test_curr are load currents, which are drawn from the battery.
    # To draw current FROM the battery, the programmed current level must be negative (or zero).
    
    test_curr = -abs(test_curr)           # Ensure test_curr has proper sense
    load_curr = smu.source_current        # Will be negative
    vload = smu.voltage                   # Battery voltage at load_curr
    smu.source_current = -abs(test_curr)  # test_curr equal to zero corresponds to an open circuit
    if settle_time > 0:
        delay(settle_time)
    vtest = smu.voltage                   # Battery voltage at test_curr; vtest is Voc if test_curr = 0
    smu.source_current = load_curr
    esr = abs((vtest - vload) / (test_curr - load_curr)) # (V2-V1)/(I2-I1); ensure positive resistance
    return vload, vtest, esr

# ********** Define Primary Test Functions **********

def config_system(do_beeps, debug):

    smu.reset()

    # Cofigure terminals
    if do_beeps:
        smu.beep(2400, 0.08)

    terminals = prompt_choice("Select TERMINALS you want to use:", ["Front", "Rear"])

    if terminals == "Front":
        smu.use_front_terminals()
    else:
        smu.use_rear_terminals()

    TEST_PARAM["terminals"] = terminals

    # Configure source settings
    smu.source_mode = "current"
    smu.output_off_state = 'HIMP'      # SMU is disconnected from output terminals when SMU output is OFF

    smu.source_current = 0.0           # Amps; zero is default value
    smu.source_current_range = 0.001   # Amps; automatically disables source autorange.
    smu.source_delay = 0.0             # Seconds; automatically disables source autodelay

    # Configure measure setting
    smu.measure_voltage()

    smu.wires = 4

    smu.compliance_voltage = 210       # Volts
    smu.voltage_range = 200            # Volts

    smu.auto_range_source()
    smu.voltage_nplc = 1

    print("Make 4-wire connections to your battery at the SMU " + terminals + " terminals\nand choose OK.")
    if do_beeps:
        smu.beep(2400, 0.08)

    prompt_choice("Proceed?", ["OK"])

    smu.source_enabled = True

    scrap_reading = smu.voltage   # Measure voltage to set range

    if debug:
        print("\nIn ConfigSystem()...")
        print("\nterminals = "+ terminals)
        print("\nsmu.voltage_range (before ranging) = " + str(smu.voltage_range))
        print("\nsmu.compliance_voltage = " + str(smu.compliance_voltage))
        print("\nscrap_reading = " + str(scrap_reading))

    smu.voltage_range = scrap_reading   # Automatically disables measure autoranging
    smu.compliance_voltage = 1.05 * smu.voltage_range   # When forcing current, the source voltage limit MUST ALWAYS be kept greater than the DUT voltage
                                                        # Both real and range compliance should be avoided

    TEST_PARAM["initial_voc"] = smu.voltage      # Capture an initial voltage measurement for system check

    smu.source_enabled = False

    if debug:
        print("\nsmu.voltage_range (after raning) = " + str(smu.voltage_range))
        print("\nsmu.compliance_voltage = " + str(smu.compliance_voltage))
        print("\nTEST_PARAM[\"initial_voc\"] = " + str(TEST_PARAM["initial_voc"]))

    if TEST_PARAM["initial_voc"] < 0.1:
        raise ValueError("Initial Voc below 0.1 V; config_system aborted")

    print("Measured battery voltage = " + "{0:.3f}".format(TEST_PARAM["initial_voc"]) + "V.\nChoose OK to continue or Cancel to quit.")
    if do_beeps:
        smu.beep(2400, 0.08)
    choice = prompt_choice("Proceed?", ["OK", "Cancel"])
    if choice == "Cancel":
        raise Exception("config_system aborted by user")

def config_test(do_beeps, debug):

    max_allowed_current = None

    if smu.voltage_range == 200:         # Volts
        max_allowed_current = 0.105      # Amps
    else:
        max_allowed_current = 1.05       # Amps

    if do_beeps:
        smu.beep(2400, 0.08)

    comment = input("Enter Comment (64 char max): ")
    if comment == "":
        comment = "NO COMMENT"
    TEST_PARAM["comment"] = comment

    if do_beeps:
        smu.beep(2400, 0.08)

    discharge_type = prompt_choice("Select Discharge Type:", ["Constant Curr", "Current List"])

    if debug:
        print("\nIn config_test()...")
        print("\nsmu.voltage_range = " + str(smu.voltage_range))
        print("\nmax_allowed_current = " + str(max_allowed_current))
        print("\ncomment = " + comment)
        print("\ndischarge_type = " + discharge_type)

    if discharge_type == "Constant Curr":
        
        TEST_PARAM["discharge_type"] = "CONSTANT"
        
        dialog_text = "Discharge Curr (1E-6 to " + str(max_allowed_current) + "A): "
        TEST_PARAM["discharge_current"] = float(input(dialog_text))
        if TEST_PARAM["discharge_current"] < 1e-6 or TEST_PARAM["discharge_current"] > max_allowed_current:
            raise ValueError("Unallowed discharge current: " + str(TEST_PARAM["discharge_current"]))

        TEST_PARAM["discharge_curr_list"] = None   # If discharge_type is CONSTANT, then there is no current list
        TEST_PARAM["max_discharge_current"] = TEST_PARAM["discharge_current"] # and discharge_current is the max_discharge_current

        if debug:
            print("\nTEST_PARAM[\"discharge_type\"] = " + TEST_PARAM["discharge_type"])
            print("\nTEST_PARAM[\"discharge_current\"] = " + str(TEST_PARAM["discharge_current"]))
            print("\nTEST_PARAM[\"discharge_curr_list\"] = " + str(TEST_PARAM["discharge_curr_list"]))
            print("\nTEST_PARAM[\"max_discharge_current\"] = " + str(TEST_PARAM["max_discharge_current"]))

    else:  # If Current List selected

        TEST_PARAM["discharge_type"] = "LIST"
        TEST_PARAM["discharge_current"] = None	 # If discharge_type is LIST, then there is no constant discharge_current

        npoints = int(input("Number of Pts in List (2 to 10): "))
        if npoints < 2 or npoints > 10:
            raise ValueError("Unallowed number of points: " + str(npoints))

        TEST_PARAM["discharge_curr_list"] = [None] * npoints   # Create array to hold current list values
        
        if debug:
            print("\nTEST_PARAM[\"discharge_type\"] = " + TEST_PARAM["discharge_type"])
            print("\nTEST_PARAM[\"discharge_current\"] = " + str(TEST_PARAM["discharge_current"]))
            print("\nTEST_PARAM[\"discharge_curr_list\"] = " + str(TEST_PARAM["discharge_curr_list"]))
            print("\nnpoints = " + str(npoints))

        average_curr = 0
        list_duration = 0

        for i in range(0,npoints):

            TEST_PARAM["discharge_curr_list"][i] = {} # Create dictionary to hold current level and duration for list point i

            dialog_text = "Dischrg Curr #" + str(i+1) + " (1E-6 to " + str(max_allowed_current) + "A): "
            TEST_PARAM["discharge_curr_list"][i]["current"] = float(input(dialog_text))
            if TEST_PARAM["discharge_curr_list"][i]["current"] < 1e-6 or TEST_PARAM["discharge_curr_list"][i]["current"] > max_allowed_current:
                raise ValueError("Unallowed discharge current: " + str(TEST_PARAM["discharge_curr_list"][i]["current"]))

            TEST_PARAM["discharge_curr_list"][i]["duration"] = float(input("Curr #" + str(i+1) + " Duration (s, 1s min): "))
            if TEST_PARAM["discharge_curr_list"][i]["duration"] < 1:
                raise ValueError("Unallowed discharge duration: " + str(TEST_PARAM["discharge_curr_list"][i]["duration"]))

            average_curr = average_curr + TEST_PARAM["discharge_curr_list"][i]["current"] * TEST_PARAM["discharge_curr_list"][i]["duration"]
            list_duration = list_duration + TEST_PARAM["discharge_curr_list"][i]["duration"]

            if debug:
                print("\nTEST_PARAM[\"discharge_curr_list\"][" + str(i) + "][\"current\"] = " + str(TEST_PARAM["discharge_curr_list"][i]["current"]))
                print("\nTEST_PARAM[\"discharge_curr_list\"][" + str(i) + "][\"duration\"] = " + str(TEST_PARAM["discharge_curr_list"][i]["duration"]))

        average_curr = average_curr / list_duration
        TEST_PARAM["discharge_curr_list_average_curr"] = average_curr
        TEST_PARAM["discharge_curr_list_duration"] = list_duration

        max_specified_current = TEST_PARAM["discharge_curr_list"][0]["current"]
        for i in range(1,npoints):
            if TEST_PARAM["discharge_curr_list"][i]["current"] > max_specified_current:
                max_specified_current = TEST_PARAM["discharge_curr_list"][i]["current"]
        TEST_PARAM["max_discharge_current"] = max_specified_current

        
        maxdur = TEST_PARAM["discharge_curr_list"][0]["duration"]
        for i in range(1,npoints):
            if TEST_PARAM["discharge_curr_list"][i]["duration"] > maxdur:
                maxdur = TEST_PARAM["discharge_curr_list"][i]["duration"]
	
        # Create array of list points with duration equal to maxdur
        maxdur_indices = []
        for i in range(0, npoints):
            if TEST_PARAM["discharge_curr_list"][i]["duration"] == maxdur:
                maxdur_indices.append(i)

        # Determine the primary step in the sweep where ESR will be measured
        max_dur_index = None
        if len(maxdur_indices) == 1:
            max_dur_index = maxdur_indices[0]
        else:
            maxcurr = TEST_PARAM["discharge_curr_list"][maxdur_indices[0]]["current"]
            for i in range(1,len(maxdur_indices)):
                if TEST_PARAM["discharge_curr_list"][maxdur_indices[i]]["current"] > maxcurr:
                    maxcurr = TEST_PARAM["discharge_curr_list"][maxdur_indices[i]]["current"]
                    max_dur_index = maxdur_indices[i]

        TEST_PARAM["discharge_curr_list_max_dur_index"] = max_dur_index

        if debug:
            print("\nTEST_PARAM[\"discharge_curr_list_average_curr\"] = " + str(TEST_PARAM["discharge_curr_list_average_curr"]))
            print("\nTEST_PARAM[\"discharge_curr_list_duration\"] = " + str(TEST_PARAM["discharge_curr_list_duration"]))
            print("\nTEST_PARAM[\"max_discharge_current\"] = " + str(TEST_PARAM["max_discharge_current"]))
            print("\nmaxdur = " + str(maxdur))
            print("\nlen(maxdur_indices) = " + str(len(maxdur_indices)))

    # Set maximum cut-off voltage to 98% of TEST_PARAM["initial_voltage"]   
    cov_max = Dround(0.98 * TEST_PARAM["initial_voc"], 2)

    # Set default cut-off voltage to 50% of TEST_PARAM["initial_voltage"].
    cov_default = Dround(0.5 * TEST_PARAM["initial_voc"], 2)

    dialog_text = "Cut-off Voltage (0.1 to " + str(cov_max) + "V): " # 100mV is arbitrary minimum
    TEST_PARAM["vcutoff"] = float(input(dialog_text))
    if TEST_PARAM["vcutoff"] < 0.1 or TEST_PARAM["vcutoff"] > cov_max:
        raise ValueError("Unallowed cutoff voltage: " + str(TEST_PARAM["vcutoff"]))

    if debug:
        print("\ncov_max = "+ str(cov_max))
        print("\ncov_default = "+ str(cov_default))
        print("TEST_PARAM[\"vcutoff\"] = "+ str(TEST_PARAM["vcutoff"]))

    TEST_PARAM["measure_interval"] = float(input("ESR Meas Interval (1 to 600s): "))
    if TEST_PARAM["measure_interval"] < 1 or TEST_PARAM["measure_interval"] > 600:
        raise ValueError("Unalllowed measure interval: " + str(TEST_PARAM["measure_interval"]))

    if debug:
        print("\nTEST_PARAM[\"measure_interval\"] = " + str(TEST_PARAM["measure_interval"]))

    filename = input("Enter battery model filename: ")
    if filename == "":
        filename = "unnamed"
        print("No name given, using \"unnamed\"")

    TEST_PARAM["batt_model_filename"] = filename + ".csv"

    choice = prompt_choice("Do you want to save setup info and raw data?", ["YES", "NO"])
    TEST_PARAM["save_setup_and_raw_data"] = choice == "YES"

def do_constant_curr_discharge(debug):

    # Create local aliases for global tables
    voc_tbl = BATT_MODEL_RAW["voc"]
    vload_tbl = BATT_MODEL_RAW["vload"]
    esr_tbl = BATT_MODEL_RAW["esr"]
    tstamp_tbl = BATT_MODEL_RAW["tstamp"]

    # Declare other local variables
    dialog_text = None

    azero_overhead = 0.00133 # Execution overhead associated with autozero; appears to vary slightly with NPLC value.
                             # Includes execution overhead for timer.cleartime() y=timer.gettime(), which is approx 10us.
			     # Values determined using 2461 with Rev 1.6.1a FW

    azero_duration = 2 * smu.voltage_nplc / smu.line_frequency + azero_overhead  # Approximate execution time of autozero

    meas_intrvl = TEST_PARAM["measure_interval"]
    loop_delay = max(meas_intrvl / 10000, 0.001)
    tstart_meas_intrvl = None

    counter = 0
    quit = False

    # Initialize SMU output
    smu.source_current_range = TEST_PARAM["max_discharge_current"]  # Use fixed source range
    smu.source_current = -1*TEST_PARAM["discharge_current"]   # Negative current because drawing current from battery

    TEST_PARAM["discharge_start_time"] = datetime.now().strftime("%m/%d/%y %H:%M:%S")
    smu.source_enabled = True

    delay(0.1)	# Allow some settling time; required time is TBD

    t0 = time.time()

    if debug:
        print("\nIn do_constant_curr_discharge()...")
        print("\nazero_overhead = " + str(azero_overhead)) 
        print("\nazero_duration = "+ str(azero_duration))
        print("\nmeas_intrvl = " + str(meas_intrvl))
        print("loop_delay = " + str(loop_delay))
        print("\nTEST_PARAM[\"discharge_start_time\"] = " + TEST_PARAM["discharge_start_time"])
        print("\ncounter, tstamp, voc, vload, esr")

    while (quit == False):

        smu.auto_zero = "ONCE"

        tstart_meas_intrvl = round(time.time() - t0, 3)

        vload_tbl.append(None)
        voc_tbl.append(None)
        esr_tbl.append(None)
        tstamp_tbl.append(None)
        
        vload_tbl[counter], voc_tbl[counter], esr_tbl[counter] = meas_esr(0, 0.01)  # Proper settle_time is still TBD

        tstamp_tbl[counter] = tstart_meas_intrvl

        if debug:
            print(counter, tstamp_tbl[counter], voc_tbl[counter], vload_tbl[counter], esr_tbl[counter])


        if vload_tbl[counter] <= TEST_PARAM["vcutoff"]:
            quit = True
            break

        while (round(time.time() - t0, 3) - tstart_meas_intrvl) < (meas_intrvl - azero_duration):
            delay(loop_delay)

        counter = counter + 1

    smu.source_current = 0
    smu.source_enabled = False

    TEST_PARAM["discharge_stop_time"] = datetime.now().strftime("%m/%d/%y %H:%M:%S")

    BATT_MODEL_RAW["capacity"] = TEST_PARAM["discharge_current"] * tstamp_tbl[counter] / 3600

    if debug:
        print("\nTEST_PARAM[\"discharge_stop_time\"] = "+ TEST_PARAM["discharge_stop_time"])
        print("\nBATT_MODEL_RAW[\"capacity\"] = " + str(BATT_MODEL_RAW["capacity"]))

def do_curr_list_discharge(settle_delay,debug):

    # Create local aliases for global tables
    voc_tbl = BATT_MODEL_RAW["voc"]
    vload_tbl = BATT_MODEL_RAW["vload"]
    esr_tbl = BATT_MODEL_RAW["esr"]
    tstamp_tbl = BATT_MODEL_RAW["tstamp"]
    curr_list_tbl = TEST_PARAM["discharge_curr_list"]

     # Declare other local variables
    dialog_text = None

    azero_overhead = 0.00133 # Execution overhead associated with autozero; appears to vary slightly with NPLC value.
                             # Includes execution overhead for timer.cleartime() y=timer.gettime(), which is approx 10us.
                             # Values determined using 2461 with Rev 1.6.1a FW

    azero_duration = 2 * smu.voltage_nplc / smu.line_frequency + azero_overhead  # Approximate execution time of autozero

    npoints = len(curr_list_tbl)
    max_dur_index = TEST_PARAM["discharge_curr_list_max_dur_index"]

    meas_intrvl = TEST_PARAM["measure_interval"]
    loop_delay2 = None
    tstart_step = None
    tmeas = None

    do_measure = None
    counter = None
    quit = False

    if debug:
        print("\nIn do_curr_list_discharge\n")
        print("\nsettle_delay = " + str(settle_delay))
        print("\nazero_overhead = " + str(azero_overhead))
        print("azero_duration = " + str(azero_duration))
        print("\nnpoints = " + str(npoints)) 
        print("max_dur_index = " + str(max_dur_index))
        print("\nmeas_intrvl = "+ str(meas_intrvl))

    # Initialize SMU output
    smu.source_current_range = TEST_PARAM["max_discharge_current"]  # Considering changing to autorange depending on required dynamic range
    smu.source_current = 0

    TEST_PARAM["discharge_start_time"] = datetime.now().strftime("%m/%d/%y %H:%M:%S")

    smu.source_enabled = True

    if debug:
        print("\nTEST_PARAM[\"discharge_start_time\"] = " + TEST_PARAM["discharge_start_time"])
        print("\ncounter, tstamp, voc, iload, vload, esr")

    t0 = time.time()

    if max_dur_index == 0:

        counter = -1
        
    else:

        counter = 0

        smu.source_current = -curr_list_tbl[max_dur_index]["current"]   # Negative current because drawing current from battery

        # Allow some settling time; required time is TBD
        if settle_delay - azero_duration > 0:
            delay(settle_delay - azero_duration)

        smu.auto_zero = "ONCE"

        # Start Trigger Timer 1
        t1 = time.time() 

        tmeas = time.time() - t0

        vload_tbl.append(None)
        voc_tbl.append(None)
        esr_tbl.append(None)
        tstamp_tbl.append(None)
        
        # MeasESR(test_curr, settle_time)
        vload_tbl[counter], voc_tbl[counter], esr_tbl[counter] = meas_esr(0, 0.01)  # Proper settle_time is still TBD

        tstamp_tbl[counter] = tmeas

        if debug:
            print(counter, tstamp_tbl[counter], voc_tbl[counter], -smu.source_current, vload_tbl[counter], esr_tbl[counter])

        if vload_tbl[counter] <= TEST_PARAM["vcutoff"]:
            quit = True
        
    while not(quit):

        for i in range(0, npoints):

            smu.source_current = -curr_list_tbl[i]["current"]   # Negative current because drawing current from battery

            tstart_step = time.time() - t0

            if curr_list_tbl[i]["current"] == curr_list_tbl[max_dur_index]["current"]:

                # Allow some settling time; required time is TBD.
                if settle_delay - azero_duration > 0:
                    delay(settle_delay - azero_duration)

                if counter == -1:

                    counter = counter + 1

                    smu.auto_zero = "ONCE"

                    # Start Trigger Timer 1
                    t1 = time.time()

                    tmeas = time.time() - t0

                    vload_tbl.append(None)
                    voc_tbl.append(None)
                    esr_tbl.append(None)
                    tstamp_tbl.append(None)
        
                    vload_tbl[counter], voc_tbl[counter], esr_tbl[counter] = meas_esr(0, 0.01)  # Proper settle_time is still TBD
                    tstamp_tbl[counter] = tmeas

                    if vload_tbl[counter] <= TEST_PARAM["vcutoff"]:
                        quit = True

                    if debug:
                        print(counter, tstamp_tbl[counter], voc_tbl[counter], -smu.source_current, vload_tbl[counter], esr_tbl[counter])

                while not(quit) and time.time() - t0 - tstart_step < curr_list_tbl[i]["duration"]:

                    # Wait up to meas_intrvl
                    while time.time() - t1 < meas_intrvl:
                        delay(0.001)

                    counter = counter + 1

                    smu.auto_zero = "ONCE"

                    tmeas = time.time() - t0

                    vload_tbl.append(None)
                    voc_tbl.append(None)
                    esr_tbl.append(None)
                    tstamp_tbl.append(None)
        
                    vload_tbl[counter], voc_tbl[counter], esr_tbl[counter] = meas_esr(0, 0.01)  # Proper settle_time is still TBD

                    tstamp_tbl[counter] = tmeas

                    if debug:
                        print(counter, tstamp_tbl[counter], voc_tbl[counter], -smu.source_current, vload_tbl[counter], esr_tbl[counter])

                    print("Total time=" + str(Dround(tmeas,0)) + " s")

                    print("Voc=" + "{0:.2f}".format(voc_tbl[counter]) + " Vload=" + "{0:.2f}".format(vload_tbl[counter]) + " ESR=" + "{0:.4f}".format(esr_tbl[counter]))

                    if vload_tbl[counter] <= TEST_PARAM["vcutoff"]:
                        quit = True

            else:

                if debug:
                    print("\nDischarging at " + str(curr_list_tbl[i]["current"]) + "A for " + str(curr_list_tbl[i]["duration"]) + "s\n")

                print("Discharging at " + str(curr_list_tbl[i]["current"]) + "A")
                delay(curr_list_tbl[i]["duration"])

            if quit:
                break

    smu.source_current = 0
    smu.source_enabled = False

    TEST_PARAM["discharge_stop_time"] = datetime.now().strftime("%m/%d/%y %H:%M:%S")

    BATT_MODEL_RAW["capacity"] = TEST_PARAM["discharge_curr_list_average_curr"] * tstamp_tbl[counter] / 3600  # Current in amps; timestamp in seconds; 3600 s/hr

    if debug:
        print("\nBATT_MODEL_RAW[\"capacity\"] = " + str(BATT_MODEL_RAW["capacity"]))
        print("\nTEST_PARAM[\"discharge_stop_time\"] = "+ TEST_PARAM["discharge_stop_time"])
    
def extract_model(debug):

    # Create local aliases for global tables
    voc_tbl = BATT_MODEL_RAW["voc"]
    vload_tbl = BATT_MODEL_RAW["vload"]
    esr_tbl = BATT_MODEL_RAW["esr"]
    tstamp_tbl = BATT_MODEL_RAW["tstamp"]

    # Declare other local variables
    max_index = len(tstamp_tbl) - 1

    model_interval = tstamp_tbl[max_index] / 100

    BATT_MODEL["soc"][100] = 100     # 100 % state of charge
    BATT_MODEL["voc"][100] = voc_tbl[0]
    BATT_MODEL["vload"][100] = vload_tbl[0]
    BATT_MODEL["esr"][100] = esr_tbl[0]
    BATT_MODEL["tstamp"][100] = tstamp_tbl[0] - tstamp_tbl[0]  # Calculate model timestamps relative to timestamp of first raw timestamp

    if debug:
        print("\nIn extract_model()...")
        print("\nsoc_index, soc, target_time, i, tstamp, voc, vload, esr")
        print(100, BATT_MODEL["soc"][100], 0, 1, BATT_MODEL["tstamp"][100], BATT_MODEL["voc"][100], BATT_MODEL["vload"][100], BATT_MODEL["esr"][100])

    start_index = 0
    soc_index = None
    target_time = None
    i = None

    for soc in range(99, 0, -1):     # 99% to 1% state_of_charge
        
        soc_index = soc
        BATT_MODEL["soc"][soc_index] = soc	
        target_time = (100 - soc) * model_interval
        i = start_index

        while (tstamp_tbl[i] - tstamp_tbl[0]) < target_time:
            i = i + 1
            if i > max_index:
                i = max_index
                break
            
        if (tstamp_tbl[i] - tstamp_tbl[0]) > target_time:
            
            if ((tstamp_tbl[i] - tstamp_tbl[0]) - target_time) < (target_time - (tstamp_tbl[i-1] - tstamp_tbl[0])):
                
                BATT_MODEL["voc"][soc_index] = voc_tbl[i]
                BATT_MODEL["vload"][soc_index] = vload_tbl[i]
                BATT_MODEL["esr"][soc_index] = esr_tbl[i]
                BATT_MODEL["tstamp"][soc_index] = tstamp_tbl[i] - tstamp_tbl[0]    # Calculate model timestamps relative to timestamp of first raw timestamp
                start_index = i

            else:

                BATT_MODEL["voc"][soc_index] = voc_tbl[i-1]
                BATT_MODEL["vload"][soc_index] = vload_tbl[i-1]
                BATT_MODEL["esr"][soc_index] = esr_tbl[i-1]
                BATT_MODEL["tstamp"][soc_index] = tstamp_tbl[i-1] - tstamp_tbl[0]  # Calculate model timestamps relative to timestamp of first raw timestamp
                start_index = i - 1

        else:   # if (tstamp_tbl[i] - tstamp_tbl[0]) == target_time

            BATT_MODEL["voc"][soc_index] = voc_tbl[i]
            BATT_MODEL["vload"][soc_index] = vload_tbl[i]
            BATT_MODEL["esr"][soc_index] = esr_tbl[i]
            BATT_MODEL["tstamp"][soc_index] = tstamp_tbl[i] - tstamp_tbl[0]	   # Calculate model timestamps relative to timestamp of first raw timestamp
            start_index = i

            
        if debug:
            print(soc_index, BATT_MODEL["soc"][soc_index], target_time, i, BATT_MODEL["tstamp"][soc_index], BATT_MODEL["voc"][soc_index], BATT_MODEL["vload"][soc_index], BATT_MODEL["esr"][soc_index])
            
    BATT_MODEL["soc"][0] = 0	# 0% state-of-charge
    BATT_MODEL["voc"][0] = voc_tbl[max_index]
    BATT_MODEL["vload"][0] = vload_tbl[max_index]
    BATT_MODEL["esr"][0] = esr_tbl[max_index]
    BATT_MODEL["tstamp"][0] = tstamp_tbl[max_index] - tstamp_tbl[0]	# Calculate model timestamps relative to timestamp of first raw timestamp

    BATT_MODEL["capacity"] = Dround(BATT_MODEL_RAW["capacity"], 4)

    if debug:
        print(0, BATT_MODEL["soc"][0], 100*model_interval, max_index, BATT_MODEL["tstamp"][0], BATT_MODEL["voc"][0], BATT_MODEL["vload"][0], BATT_MODEL["esr"][0])
        print("\nBATT_MODEL[\"capacity\"] = " + str(BATT_MODEL["capacity"]))

    if len(tstamp_tbl) < 101:
        print("Fewer than 101 measurements were made.  As a result, your\nbattery model will have some duplicate values.")

def save_model(debug):
    print("Saving Battery Discharge Model\n")
    
    filename = TEST_PARAM["batt_model_filename"]

    file = open(filename, "w")

    file.write("PW_MODEL_PW2281S_20_6 \n");

    file.write("Capacity=" + str(BATT_MODEL["capacity"]) + "AH\n")
    file.write("SOC(%), Open Voltage(V), ESR(ohm)\n")

    for i in range(0,101):
        file.write(str(BATT_MODEL["soc"][i]) + ", " + str(BATT_MODEL["voc"][i]) + ", " + format(BATT_MODEL["esr"][i], '.7g') + " \n")
    file.close()

def save_setup_and_raw_data(debug):

    if debug:
        print("\nIn save_setup_and_raw_data()")

    if not TEST_PARAM["save_setup_and_raw_data"]:
        return

    filename = TEST_PARAM["batt_model_filename"][:-4] + "_SetupAndRawData.csv"
                                                                            
    file = open(filename, "w")

    file.write("TEST_PARAM.comment:," + TEST_PARAM["comment"] +"\n")
    file.write("\n")


    smu_id_info = smu.id.split(",")
    file.write("SourceMeter Model:," + smu_id_info[1].lstrip("MODEL ") +"\n")
    file.write("SourceMeter S/N:," + smu_id_info[2] + "\n")
    file.write("SourceMeter Firmware:," + smu_id_info[3].split(" ")[0] + "\n")
    file.write("\n")
    file.write("TEST_PARAM.terminals:," + TEST_PARAM["terminals"].upper()  + " TERMINALS\n")
    file.write("\n")
    file.write("TEST_PARAM.initial_voc:," + str(TEST_PARAM["initial_voc"]) + "\n")
    file.write("TEST_PARAM.vcutoff:," + str(TEST_PARAM["vcutoff"]) + "\n")
    file.write("\n")
    file.write("TEST_PARAM.discharge_type:," + TEST_PARAM["discharge_type"] + "\n")
    if TEST_PARAM["discharge_current"] is not None:
        file.write("TEST_PARAM.discharge_current:," + str(TEST_PARAM["discharge_current"]) + "\n")
        file.write("TEST_PARAM.max_discharge_current:," + str(TEST_PARAM["max_discharge_current"]) + "\n")
    if TEST_PARAM["discharge_curr_list"] is not None:
        file.write("TEST_PARAM.discharge_curr_list:,Index,Current (A),Duration (s)\n")
        for i in range(0,len(TEST_PARAM["discharge_curr_list"])):
            file.write(","+ str(i+1) + "," + str(TEST_PARAM["discharge_curr_list"][i]["current"]) + "," + str(TEST_PARAM["discharge_curr_list"][i]["duration"])+"\n")
        file.write("TEST_PARAM.discharge_curr_list.average_curr:,," + str(TEST_PARAM["discharge_curr_list_average_curr"]) + "\n")
        file.write("TEST_PARAM.discharge_curr_list.duration:,,," + str(TEST_PARAM["discharge_curr_list_duration"]) + "\n")
        file.write("TEST_PARAM.discharge_curr_list.max_dur_index:," + str(TEST_PARAM["discharge_curr_list_max_dur_index"]+1) + "\n")
        file.write("TEST_PARAM.max_discharge_current:," + str(TEST_PARAM["max_discharge_current"]) + "\n")
    file.write("\n")
    file.write("TEST_PARAM.measure_interval:," + str(TEST_PARAM["measure_interval"]) + "\n")
    file.write("\n")
    file.write("TEST_PARAM.discharge_start_time:," + TEST_PARAM["discharge_start_time"] + "\n")
    file.write("TEST_PARAM.discharge_stop_time:," + TEST_PARAM["discharge_stop_time"] + "\n")
    file.write("\n")
    file.write("BATT_MODEL_RAW:,Index,Timestamp,Voc,Vload,ESR\n")
    for i in range(0,len(BATT_MODEL_RAW["tstamp"])):
        file.write("BATT_MODEL_RAW:,"+str(i+1)+","+ str(BATT_MODEL_RAW["tstamp"][i]) + "," + str(BATT_MODEL_RAW["voc"][i]) + "," + str(BATT_MODEL_RAW["vload"][i]) + "," + format(BATT_MODEL_RAW["esr"][i], '.7g') +"\n")
    file.write("BATT_MODEL_RAW.capacity:," + format(BATT_MODEL_RAW["capacity"], '.7g') +"\n")
    file.write("\n")
    file.write("BATT_MODEL:,Index,Timestamp,Voc,Vload,ESR\n")
    for i in range(0, len(BATT_MODEL["tstamp"])):
        file.write("BATT_MODEL:," + str(i+1) + "," + str(BATT_MODEL["tstamp"][i]) + "," + str(BATT_MODEL["voc"][i]) + "," + str(BATT_MODEL["vload"][i]) + "," + format(BATT_MODEL["esr"][i], '.7g') + "\n")
    file.write("BATT_MODEL.capacity:," + str(BATT_MODEL["capacity"]) +"\n")
    
    file.close()

def run_test(do_beeps, debug):

    if debug:
        print("\nCall config_system")

    config_system(do_beeps, debug)

    if debug:
        print("\nCall config_test")

    config_test(do_beeps, debug)

    print("\n")
    dialog_text = "Select OK to START TEST, or Cancel to ABORT and EXIT."

    if do_beeps:
        smu.beep(2400, 0.08)
        
    selection = prompt_choice(dialog_text, ["OK", "Cancel"])
    if selection == "Cancel":
        raise Exception("run_test aborted by user")

    if TEST_PARAM["discharge_type"] == "CONSTANT":

        if debug:
            print("\nCall do_constant_curr_discharge()...")

        do_constant_curr_discharge(debug)

    else:

        if debug:
            print("\nCall do_curr_list_discharge()...")

        # do_curr_list_discharge(settle_delay, debug); need to empirically determine an appropriate settling delay
        #   Start with 50us, which is the practical minimum you can use with the delay() function
        do_curr_list_discharge(50e-6, debug)

    if debug:
        print("\nCall extract_model()...")

    extract_model(debug)

    if debug:
        print("\nCall save_model()...")

    save_model(debug)

    if debug:
        print("\nCall save_setup_and_raw_data()...")

    save_setup_and_raw_data(debug)

debug = False
do_beeps = True

print("\nBattery Discharge Driver for Keithley 2400 SourceMeter\n")
print("Follow all manufacturer's guidelines to ensure safe operation when\ndischarging a battery (especially a LITHIUM ION battery)!")

selection = prompt_choice("Proceed?", ["OK", "Cancel"])

if selection == "Cancel":
    raise Exception("run_test aborted by user")

run_test(do_beeps, debug)

smu.beep(2400, 0.08)
