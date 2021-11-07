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

def config_system(TEST_PARAM, smu, do_beeps, debug):

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

    return TEST_PARAM
