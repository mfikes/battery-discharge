"""
Script: battery_discharge.py
Writen by: Mike Fikes
Original TSP version written by: Keithley Applications Engineering (Al Ivons)

***********************************************************
*** Copyright 2017 Tektronix, Inc.                      ***
*** See www.tek.com/sample-license for licensing terms. ***
***********************************************************

Revision History:
        * Originally released Nov 2021.

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
import inquirer

def delay(interval):
    time.sleep(interval)

adapter = PrologixAdapter('/dev/cu.usbserial-PXEFMYB9')
smu = Keithley2400(adapter.gpib(26))
TEST_PARAM = {}


def prompt_choice(prompt, choices):
    questions = [
        inquirer.List('choice',
                      message=prompt,
                      choices=choices,
                      ),
        ]
    answers = inquirer.prompt(questions)
    return answers["choice"]
    
# ********** Define Utility Functions **********

def meas_esr(smu, test_curr, settle_time):

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

    # display.changescreen(display.SCREEN_HOME)

    # eventlog.clear()

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

    # TODO disable source readback
    # Original TSP smu.source.readback = smu.OFF
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

    dialog_text = "Make 4-wire connections to your battery at the SMU " + terminals + " terminals and then press OK."
    if do_beeps:
        smu.beep(2400, 0.08)
    
    prompt_choice(dialog_text, ["OK"])

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

    if TEST_PARAM["initial_voc"] <= 0:
        raise ValueError("Negative or zero Initial Voc detected; config_system aborted")

    dialog_text = "Measured battery voltage = " + "{0:.3f}".format(TEST_PARAM["initial_voc"]) + "V.\nPress OK to continue or Cancel to quit."
    if do_beeps:
        smu.beep(2400, 0.08)
    choice = prompt_choice(dialog_text, ["OK", "CANCEL"])
    if choice == "CANCEL":
        raise Exception("config_system aborted by user")

def config_test(do_beeps, debug):

    max_allowed_current = None

    if smu.voltage_range == 200:         # Volts
        max_allowed_current = 0.105      # Amps
    else:
        max_allowed_current = 1.05       # Amps

    if do_beeps:
        smu.beep(2400, 0.08)

    comment = input("Enter Comment (64 char max):")
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
        
        dialog_text = "Discharge Curr (1E-6 to " + str(max_allowed_current) + "A)"
        TEST_PARAM["discharge_curr"] = float(input(dialog_text))
        if TEST_PARAM["discharge_curr"] < 1e-6 or TEST_PARAM["discharge_curr"] > max_allowed_current:
            raise ValueError("Unallowed discharge current: " + str(TEST_PARAM["discharge_curr"]))

        TEST_PARAM["discharge_curr_list"] = None   # If discharge_type is CONSTANT, then there is no current list
        TEST_PARAM["max_discharge_current"] = TEST_PARAM["discharge_current"] # and discharge_current is the max_discharge_current

        if debug:
            print("\nTEST_PARAM[\"discharge_type\"] = " + TEST_PARAM["discharge_type"])
            print("\nTEST_PARAM[\"discharge_current\"] = " + str(TEST_PARAM["discharge_current"]))
            print("\nTEST_PARAM[\"discharge_curr_list\"] = " + str(TEST_PARAM["discharge_curr_list"]))
            print("\nTEST_PARAM[\"max_discharge_current\"] = " + str(TEST_PARAM["max_discharge_current"]))

    else:  # If Current List selected

        TEST_PARAM["discharge_type"] = "LIST"
        TEST_PARAM["discharge_curr_list"] = []   # Create array to hold current list values
        TEST_PARAM["discharge_current"] = None	 # If discharge_type is LIST, then there is no constant discharge_current

        npoints = int(input("Number of Pts in List (2 to 10)"))
        if npoints < 2 or npoints > 10:
            raise ValueError("Unallowed number of points: " + str(npoints))

        if debug:
            print("\nTEST_PARAM[\"discharge_type\"] = " + TEST_PARAM["discharge_type"])
	    print("\nTEST_PARAM[\"discharge_current\"] = " + str(TEST_PARAM["discharge_current"]))
	    print("\nTEST_PARAM[\"discharge_curr_list\"] = " + str(TEST_PARAM["discharge_curr_list"]))
            print("\nnpoints = " + str(npoints))

        average_curr = 0
        list_duration = 0

        for i in range(0,npoints):

            TEST_PARAM["discharge_curr_list"][i] = {} # Create dictionary to hold current level and duration for list point i

            dialog_text = "Dischrg Curr #" + str(i+1) + " (1E-6 to " + str(max_allowed_current) + "A)"
            TEST_PARAM["discharge_curr_list"][i]["current"] = float(input(dialog_text))
            if TEST_PARAM["discharge_curr_list"][i]["current"] < 1e-6 or TEST_PARAM["discharge_curr_list"][i]["current"] > max_allowed_current:
                raise ValueError("Unallowed discharge current: " + str(TEST_PARAM["discharge_curr_list"][i]["current"]))

            TEST_PARAM["discharge_curr_list"][i]["duration"] = float(input("Curr #" + str(i+1) + " Duration (s, 500us min)"))
            if TEST_PARAM["discharge_curr_list"][i]["duration"] < 0.0005:
                raise ValueError("Unallowed discharge duration: " + str(TEST_PARAM["discharge_curr_list"][i]["duration"]))

            average_curr = average_curr + TEST_PARAM["discharge_curr_list"][i]["current"] * TEST_PARAM["discharge_curr_list"][i]["duration"]
            list_duration = list_duration + TEST_PARAM["discharge_curr_list"][i]["duration"]

            if debug:
                print("\nTEST_PARAM[\"discharge_curr_list\"][" + str(i) + "]["current"] = " + TEST_PARAM["discharge_curr_list"][i]["current"])
                print("\nTEST_PARAM[\"discharge_curr_list\"][" + str(i) + "]["duration"] = " + TEST_PARAM["discharge_curr_list"][i]["duration"])

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

        dialog_text = "Cut-off Voltage (0.1 to " + str(cov_max) + "V)" # 100mV is arbitrary minimum
        TEST_PARAM["vcutoff"] = float(input(dialog_text))
        if TEST_PARAM["vcutoff"] < 0.1 or TEST_PARAM["vcutoff"] > cov_max:
            raise ValueError("Unallowed cutoff voltage: " + str(TEST_PARAM["vcutoff"]))

        if debug:
            print("\ncov_max = "+ str(cov_max))
            print("\ncov_default = "+ str(cov_default))
            print("TEST_PARAM[\"vcutoff\"] = "+ str(TEST_PARAM["vcutoff"]))

        TEST_PARAM["measure_interval"] = float(input("ESR Meas Interval (0.08 to 600s)"))
        if TEST_PARAM["measure_interval"] < 0.08 or TEST_PARAM["measure_interval"] > 600:
            raise ValueError("Unalllowed measure interval: " + str(TEST_PARAM["measure_interval"]))

        if debug:
            print("\nTEST_PARAM[\"measure_interval\"] = " + TEST_PARAM["measure_interval"])

        
        
