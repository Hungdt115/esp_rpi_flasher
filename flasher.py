#! /usr/bin/env python
import argparse
import configparser
import glob
import os
import os.path
import RPi.GPIO as GPIO
import serial
import subprocess
import sys
import threading
from time import sleep
import re
import csv

PYTHON = sys.executable

def read_config():
    configFilePath = "/boot/firmware/config.ini"
    config = configparser.ConfigParser()
    config.read(configFilePath)

    projectPath = config.get('DEFAULT', 'projectPath')
    isEncrypt = config.get('DEFAULT', 'isEncrypt')
    DataPath = config.get('DEFAULT', 'appDataPathT1')

    if isEncrypt == 'True':
        bootloaderPath = config.get('ENCRYPT', 'bootloaderPath')
        partitionsPath = config.get('ENCRYPT', 'partitionsPath')
        otaDataPath = config.get('ENCRYPT', 'otaDataPath')
        appDataPath = config.get('ENCRYPT', 'appDataPath')
        secureBootloaderKeyPath = config.get('ENCRYPT', 'secureBootloaderKeyPath')
        flashEcryptionKeyPath = config.get('ENCRYPT', 'flashEcryptionKeyPath')
    else:
        bootloaderPath = config.get('DEFAULT', 'bootloaderPath')
        partitionsPath = config.get('DEFAULT', 'partitionsPath')
        otaDataPath = config.get('DEFAULT', 'otaDataPath')
        appDataPath = config.get('DEFAULT', 'appDataPath')
        appDataPathT1 = config.get('DEFAULT', 'appDataPathT1')
        appDataPathT2 = config.get('DEFAULT', 'appDataPathT2')
        appDataPathT3 = config.get('DEFAULT', 'appDataPathT3')
        appDataPathT4 = config.get('DEFAULT', 'appDataPathT4')
        secureBootloaderKeyPath = config.get('DEFAULT', 'secureBootloaderKeyPath')
        flashEcryptionKeyPath = config.get('DEFAULT', 'flashEcryptionKeyPath')

    flashButton = int(config.get('DEFAULT', 'flashButton'))
    reFlashButton = int(config.get('DEFAULT', 'reFlashButton'))
    rebootButton = int(config.get('DEFAULT', 'rebootButton'))
    flashingLED = int(config.get('DEFAULT', 'flashingLED'))
    reFlashLED = int(config.get('DEFAULT', 'reFlashLED'))
    readyLED = int(config.get('DEFAULT', 'readyLED'))

    ledFailPort0 = int(config.get('DEFAULT', 'ledFailPort0'))
    ledFailPort1 = int(config.get('DEFAULT', 'ledFailPort1'))
    ledFailPort2 = int(config.get('DEFAULT', 'ledFailPort2'))
    ledFailPort3 = int(config.get('DEFAULT', 'ledFailPort3'))

    switch0 = int(config.get('DEFAULT', 'switch0'))
    switch1 = int(config.get('DEFAULT', 'switch1'))
    switch2 = int(config.get('DEFAULT', 'switch2'))
    switch3 = int(config.get('DEFAULT', 'switch3'))

    return (
        projectPath, isEncrypt, DataPath, bootloaderPath, partitionsPath,
        otaDataPath, appDataPath, appDataPathT1, appDataPathT2,
        appDataPathT3, appDataPathT4, secureBootloaderKeyPath,
        flashEcryptionKeyPath, flashButton, reFlashButton, rebootButton,
        flashingLED, reFlashLED, readyLED, ledFailPort0, ledFailPort1,
        ledFailPort2, ledFailPort3, switch0, switch1, switch2, switch3
    )

(
    projectPath, isEncrypt, DataPath, bootloaderPath, partitionsPath,
    otaDataPath, appDataPath, appDataPathT1, appDataPathT2,
    appDataPathT3, appDataPathT4, secureBootloaderKeyPath,
    flashEcryptionKeyPath, flashButton, reFlashButton, rebootButton,
    flashingLED, reFlashLED, readyLED, ledFailPort0, ledFailPort1,
    ledFailPort2, ledFailPort3, switch0, switch1, switch2, switch3
) = read_config()

# Các dòng cài đặt LED và nút
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(flashButton, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(reFlashButton, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(rebootButton, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(flashingLED, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(reFlashLED, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(readyLED, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(ledFailPort0, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(ledFailPort1, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(ledFailPort2, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(ledFailPort3, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(switch0, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(switch1, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(switch2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(switch3, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Biến toàn cục
reFlashPorts = []  # Danh sách cổng cần flash lại
Port_fail = []
mac_str = []
flashFlag = False
reFlashFlag = False
rebootFlag = False
Port0Flag = False
Port1Flag = False
Port2Flag = False
Port3Flag = False

mode = 0b0000

def _readSwitch():
    pin0 = GPIO.input(switch0)
    pin1 = GPIO.input(switch1)
    pin2 = GPIO.input(switch2)
    pin3 = GPIO.input(switch3)
    mode = pin0 << 1 | pin1 << 2 | pin2 << 3 | pin3
    return mode

def _setmodeSwitch():
    mode = _readSwitch()
    if mode == 0b0000:
        DataPath = appDataPathT1
        print(DataPath)
    elif mode == 0b0001:
        DataPath = appDataPathT2
        print(DataPath)
    elif mode == 0b0010:
        DataPath = appDataPathT3
        print(DataPath)
    elif mode == 0b0011:
        DataPath = appDataPathT4
        print(DataPath)

# Các hàm khác
def _get_args(type, esptool_path, port, baud):
    result = [PYTHON, esptool_path, "--port", port, "--do-not-confirm", "--before", "default_reset"]
    if type == "burn_secure_key":
        result += ["burn_key", "secure_boot", secureBootloaderKeyPath]
    elif type == "burn_flash_encryption_key":
        result += ["burn_key", "flash_encryption", flashEcryptionKeyPath]
    elif type == "burn_efuse_cnt":
        result += ["burn_efuse", "FLASH_CRYPT_CNT", "1"]
    elif type == "burn_efuse_config":
        result += ["burn_efuse", "FLASH_CRYPT_CONFIG", "0xf"]
    elif type == "flash":
        result += ["--chip", "esp32", "--baud", str(baud), "--before", "default_reset", "--after", "hard_reset",
                   "write_flash", "-z", "--flash_mode", "dio", "--flash_freq", "40m", "--flash_size", "detect",
                   "0x10000", DataPath, "0x8000", partitionsPath, "0x0", bootloaderPath, "0xe000", otaDataPath]
    elif type == "erase_flash":
        result += ["erase_flash"]
    return result

# Hàm lấy địa chỉ MAC
def _get_mac(port_get):
    mac = os.popen(f"{projectPath}/esptool/esptool.py --chip esp32 --port {port_get} read_mac| grep MAC |uniq").read()
    res_str = re.sub(r"MAC: ", "", mac)
    print(res_str)
    try:
        with open('maclist.csv', 'a', newline='') as f:
            fieldnames = ['MAC_address', 'field_error']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not reFlashFlag:
                writer.writerow({'MAC_address': f'{res_str}', 'field_error': ' '})
            sleep(1)
    except KeyboardInterrupt:
        f.close()

def _get_ports():
    if sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        ports = glob.glob('/dev/tty[Uu]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.U*')
    else:
        raise EnvironmentError('Unsupported platform')
    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result

def _getPort_fail():
    for Port_fail in reFlashPorts:
        _get_mac(Port_fail)
        if Port_fail == '/dev/ttyUSB0':
            global Port0Flag
            Port0Flag = True
        elif Port_fail == '/dev/ttyUSB1':
            global Port1Flag
            Port1Flag = True
        elif Port_fail == '/dev/ttyUSB2':
            global Port2Flag
            Port2Flag = True
        elif Port_fail == '/dev/ttyUSB3':
            global Port3Flag
            Port3Flag = True
    if not reFlashPorts:
        reFlashFlag = False
        Port0Flag = False
        Port1Flag = False
        Port2Flag = False
        Port3Flag = False
        GPIO.output(reFlashLED, GPIO.LOW)
    Port_fail = []

    if Port0Flag:
        GPIO.output(ledFailPort0, GPIO.LOW)
        print("Port0 flash fail")
    else:
        GPIO.output(ledFailPort0, GPIO.HIGH)
        print("Port0 flash successful")
    if Port1Flag:
        GPIO.output(ledFailPort1, GPIO.LOW)
        print("Port1 flash fail")
    else:
        GPIO.output(ledFailPort1, GPIO.HIGH)
        print("Port1 flash successful")
    if Port2Flag:
        GPIO.output(ledFailPort2, GPIO.LOW)
        print("Port2 flash fail")
    else:
        GPIO.output(ledFailPort2, GPIO.HIGH)
        print("Port2 flash successful")
    if Port3Flag:
        GPIO.output(ledFailPort3, GPIO.LOW)
        print("Port3 flash fail")
    else:
        GPIO.output(ledFailPort3, GPIO.HIGH)
        print("Port3 flash successful")
    return 0

def _run_tool(tool_name, args1, args2, args3, args4, args5):
    def quote_arg(arg):
        if " " in arg and not (arg.startswith('"') or arg.startswith("'")):
            return "'" + arg + "'"
        return arg

    def display_command(command):
        display_args = " ".join(quote_arg(arg) for arg in command)
        print("Running %s in directory %s" % (tool_name, quote_arg(projectPath)))
        print('Executing "%s"...' % display_args)

    if isEncrypt == 'True':
        burnKeyFlag = True
        try:
            display_command(args1)
            subprocess.check_call(args1, env=os.environ, cwd=projectPath)
        except subprocess.CalledProcessError as e:
            burnKeyFlag = False
            print("%s failed with exit code %d" % (tool_name, e.returncode))
        try:
            display_command(args2)
            subprocess.check_call(args2, env=os.environ, cwd=projectPath)
        except subprocess.CalledProcessError as e:
            burnKeyFlag = False
            print("%s failed with exit code %d" % (tool_name, e.returncode))
        if burnKeyFlag:
            try:
                display_command(args3)
                subprocess.check_call(args3, env=os.environ, cwd=projectPath)
            except subprocess.CalledProcessError as e:
                print("%s failed with exit code %d" % (tool_name, e.returncode))
            try:
                display_command(args4)
                subprocess.check_call(args4, env=os.environ, cwd=projectPath)
            except subprocess.CalledProcessError as e:
                print("%s failed with exit code %d" % (tool_name, e.returncode))

    try:
        display_command(args5)
        subprocess.check_call(args5, env=os.environ, cwd=projectPath)
        _getPort_fail()
    except subprocess.CalledProcessError as e:
        print("%s failed with exit code %d" % (tool_name, e.returncode))
        GPIO.output(reFlashLED, GPIO.HIGH)
        if args5[5] not in reFlashPorts:
            reFlashPorts.append(args5[5])
        print("%s" % reFlashPorts)
        _getPort_fail()
    sleep(1)
    print("Done")
    return 0

def _flash_callback(channel):
    print("Flash button is pressed")
    global flashFlag
    flashFlag = True

def _flash():
    print("Number of threads: %s" % threading.active_count())
    del reFlashPorts[:]
    GPIO.output(flashingLED, GPIO.HIGH)
    GPIO.output(reFlashLED, GPIO.LOW)
    ports = _get_ports()
    threads = []
    for x in ports:
        args1 = _get_args("burn_secure_key", os.path.join(projectPath, "esptool/espefuse.py"), x, 2000000)
        args2 = _get_args("burn_flash_encryption_key", os.path.join(projectPath, "esptool/espefuse.py"), x, 2000000)
        args3 = _get_args("burn_efuse_cnt", os.path.join(projectPath, "esptool/espefuse.py"), x, 2000000)
        args4 = _get_args("burn_efuse_config", os.path.join(projectPath, "esptool/espefuse.py"), x, 2000000)
        args5 = _get_args("flash", os.path.join(projectPath, "esptool/esptool.py"), x, 921600)
        flashThread = threading.Thread(target=_run_tool, args=("esptool.py", args1, args2, args3, args4, args5))
        threads.append(flashThread)
        _get_mac(x)
    for x in threads:
        x.start()
    for x in threads:
        x.join()
    GPIO.output(flashingLED, GPIO.LOW)
    global flashFlag
    flashFlag = False

def _reflash_callback(channel):
    print("Reflash button is pressed")
    global reFlashFlag
    reFlashFlag = True

def _reflash():
    threads = []
    GPIO.output(flashingLED, GPIO.HIGH)
    GPIO.output(reFlashLED, GPIO.LOW)
    for x in reFlashPorts:
        args1 = _get_args("burn_secure_key", os.path.join(projectPath, "esptool/espefuse.py"), x, 2000000)
        args2 = _get_args("burn_flash_encryption_key", os.path.join(projectPath, "esptool/espefuse.py"), x, 2000000)
        args3 = _get_args("burn_efuse_cnt", os.path.join(projectPath, "esptool/espefuse.py"), x, 2000000)
        args4 = _get_args("burn_efuse_config", os.path.join(projectPath, "esptool/espefuse.py"), x, 2000000)
        args5 = _get_args("flash", os.path.join(projectPath, "esptool/esptool.py"), x, 921600)
        reFlashThread = threading.Thread(target=_run_tool, args=("esptool.py", args1, args2, args3, args4, args5))
        threads.append(reFlashThread)
    del reFlashPorts[:]
    for x in threads:
        x.start()
    for x in threads:
        x.join()
    global reFlashFlag
    reFlashFlag = False
    GPIO.output(flashingLED, GPIO.LOW)

def _reboot_callback(channel):
    print("Reboot button is pressed")
    GPIO.output(readyLED, GPIO.LOW)
    sleep(1)
    global rebootFlag
    rebootFlag = True

def _reboot():
    os.system("sudo reboot")

GPIO.add_event_detect(reFlashButton, GPIO.FALLING, callback=_reflash_callback, bouncetime=2000)
GPIO.add_event_detect(flashButton, GPIO.FALLING, callback=_flash_callback, bouncetime=2000)
GPIO.add_event_detect(rebootButton, GPIO.FALLING, callback=_reboot_callback, bouncetime=2000)
_setmodeSwitch()
with open('maclist.csv', 'w', newline='') as f:
    fieldnames = ['MAC_address', 'field_error']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
try:
    GPIO.output(readyLED, GPIO.HIGH)
    while True:
        if flashFlag:
            _flash()
        if reFlashFlag:
            _reflash()
        if rebootFlag:
            _reboot()
except KeyboardInterrupt:
    GPIO.cleanup()
GPIO.cleanup()

