# thanks to Matthew Beckett (ibanezzmatt13 NORB) for the original code and a great deal of help
# and many thanks to the hab community http://ukhas.org.uk/



#!/usr/bin/python

import argparse, serial, crcmod, smbus, os, time, glob, re, picamera
import time as time_
from subprocess import PIPE, Popen
from Adafruit_BMP085 import BMP085
import RPi.GPIO as GPIO

Path = os.path.dirname( os.path.abspath( __file__ ) )


TopAlt = 12000
CutOff = 25

GPIO.setmode(11)
GPIO.setup(CutOff, GPIO.OUT)

Devices = {
"BMP085": True,
"TMP102": True,
"DHT22": True,
"DS18B20": False
}

StartTime = time.time()

if os.getcwd() != Path:
	os.chdir(Path)
time_set = False
gps_set_success = False
bmp = BMP085(0x77, 3)
bus = smbus.SMBus(1)
DNull = open('/dev/null', 'w')
os.system("chmod +x ./DHT")
Parser = argparse.ArgumentParser(description="Parse and decipher GPS signals from serial. Output to Tx with flightmode enabled.")

Parser.add_argument('-c', nargs='?',
    help='Custom Callsign for the Tx.')
Parser.add_argument('-p', action='store_const', const='picture',
    help='Enable timelapse / picture mode.')
Parser.add_argument('-s', action='store_const', const='silent',
    help='Enable smaller output ( Less chance of error and more data per minute ).')

Args = Parser.parse_args()
print Args.c, Args.p, Args.s
if Args.c:
    callsign = Args.c
else:
    callsign = "PRID"
if Args.s:
    print "Verbose data disabled / Small data stream enabled."
if Args.p:
    DNull = open('/dev/null', 'w')
    Camera = Popen(["sudo", "python", "timelapse.py"], stdout=DNull, stderr=DNull)

setNav = bytearray.fromhex("B5 62 06 24 24 00 FF FF 06 03 00 00 00 00 10 27 00 00 05 00 FA 00 FA 00 64 00 2C 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 16 DC")

def gettmp(addr):
    data = bus.read_i2c_block_data(addr, 0)
    msb = data[0]
    lsb = data[1]
    neg = data[2]
    print "LOOK HERE JED --------- {} : {} : {} : {}".format(data[0], data[1], data[2], data[3])
    tmp = int((((msb << 8) | lsb) >> 4) * 0.0625)
    if neg == 0:
        tmp = 255-tmp
    return tmp

def read_B18_Raw():
    os.system('modprobe w1-gpio')
    os.system('modprobe w1-therm')

    base_dir = '/sys/bus/w1/devices/'
    device_folder = glob.glob(base_dir + '28*')[0]
    device_file = device_folder + '/w1_slave'
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    return lines

def read_B18():
    lines = read_B18_Raw()
    while lines[0].strip()[-3:] != 'YES':
            time.sleep(0.2)
            lines = read_B18_Raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        temp_f = temp_c * 9.0 / 5.0 + 32.0
        return "%.1f" % (temp_c)

def disable_sentences():
    GPS = serial.Serial('/dev/ttyAMA0', 9600, timeout=1) # open serial to write to GPS
    time.sleep(0.5)
    GPS.write("$PUBX,40,GLL,0,0,0,0*5C\r\n")
    time.sleep(0.5)
    GPS.write("$PUBX,40,GSA,0,0,0,0*4E\r\n")
    time.sleep(0.5)
    GPS.write("$PUBX,40,RMC,0,0,0,0*47\r\n")
    time.sleep(0.5)
    GPS.write("$PUBX,40,GSV,0,0,0,0*59\r\n")
    time.sleep(0.5)
    GPS.write("$PUBX,40,VTG,0,0,0,0*5E\r\n")
    time.sleep(0.5)
    
    GPS.flush()
    GPS.close()

def millis():
    return int(round(time_.time() * 1000))

def sendUBX(MSG, length):
    ubxcmds = ""
    for i in range(0, length):
        GPS.write(chr(MSG[i]))
        ubxcmds = ubxcmds + str(MSG[i]) + " "
    GPS.write("\r\n")

def getUBX_ACK(MSG):
    b = 0
    ackByteID = 0
    ackPacket = [0 for x in range(10)]
    startTime = millis()

    ackPacket[0] = int('0xB5', 16)	# header
    ackPacket[1] = int('0x62', 16)	# header
    ackPacket[2] = int('0x05', 16)	# class
    ackPacket[3] = int('0x01', 16)	# id
    ackPacket[4] = int('0x02', 16)	# length
    ackPacket[5] = int('0x00', 16)	# spacing
    ackPacket[6] = MSG[2]		# ACK class
    ackPacket[7] = MSG[3]		# ACK id
    ackPacket[8] = 0			# CK_A
    ackPacket[9] = 0			# CK_B

    for i in range(2,8):
        ackPacket[8] = ackPacket[8] + ackPacket[i]
        ackPacket[9] = ackPacket[9] + ackPacket[8]

    for byt in ackPacket:
        print byt

    while 1:
        if ackByteID > 9 :
            return True

        if millis() - startTime > 3000:
            return False

        if GPS.inWaiting() > 0:
            b = GPS.read(1)

            if ord(b) == ackPacket[ackByteID]:
                ackByteID += 1
            else:
                ackByteID = 0
crc16f = crcmod.predefined.mkCrcFun('crc-ccitt-false')
disable_sentences()
counter = 0

def DHT(Pin):
    Start = time.time()
    Args = ["./DHT", "2302", str(Pin)]
    while True:
        Temp = Humi = Out = ""
        Proc = Popen(Args, stdout=PIPE)
        Out = Proc.stdout.read()
        Proc.stdout.flush()
        Temp = re.findall(r'([-]*[0-9]*.[0-9]*) C', Out)
        Humi = re.findall(r'([-]*[0-9]*.[0-9]*) %', Out)
        if len(Temp)>0 and len(Humi)>0:
            return float(Temp[0]), float(Humi[0])
        else:
            if (time.time() - Start) > 15:
                return 0, 0
        time.sleep(2)


def set_time(time):
    data = list(time)
    hours = time[0] + time[1] 
    minutes = time[2] + time[3]
    parsed_datetime = hours + minutes
    os.system('sudo date --set ' + str(parsed_datetime))
    time_set = True

def send(data):
    NTX2 = serial.Serial('/dev/ttyAMA0', 50, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_TWO)
    NTX2.write(data)
    NTX2.close()

def parse_gps(NMEA_sentence, flightmode):
    satellites = 0
    lats = 0
    northsouth = 0
    lngs = 0
    westeast = 0
    altitude = 0
    time = 0
    latitude = 0
    longitude = 0
    temp = 0
    humidity = 0
    temp2 = 0
    pressure2 = 0
    alt2 = 0
    temp3 = 0
    temp4 = 0
    
    global counter
    
 
    if NMEA_sentence.startswith("$GPGGA"):
        print NMEA_sentence
        data = NMEA_sentence.split(",")
        if data[6] == "0":
            print "No Lock"
            pass
        else:
            for Value in Devices:
                if Value == "DHT22" and Devices[Value]:
                    print "DHT22 Enabled"
                    temp, humidity = DHT(17)
                elif Value == "BMP085" and Devices[Value]:
                    print "BMP085 Enabled"
                    temp2 = "%.1f" % bmp.readTemperature()
                    pressure2 = "%.1f" % float(bmp.readPressure()/100.0)
                    alt2 = "%.1f" % bmp.readAltitude()
                elif Value == "TMP102" and Devices[Value]:
                    print "TMP102 Enabled"
                    temp3 = "%.1f" % gettmp(0x49)
                elif Value == "DS18B20" and Devices[Value]:
                    "DS18B20 Enabled"
                    temp4 = read_B18()
             
            raw_time = data[1]
            lats = data[2]
            northsouth = data[3]
            lngs = data[4]
            westeast = data[5]
            satellites = data[7]
            altitude = data[9]
            if time_set == False:
                set_time(raw_time)
            time = float(raw_time)
            string = "%06i" % time
            hours = string[0:2]
            minutes = string[2:4]
            seconds = string[4:6]
            time = "{}:{}:{}".format(hours, minutes, seconds)	# Could also use time.strftime("%H:%M:S") which will output HOURS:MINUTES:SECONDS
            latitude = convert(lats, northsouth)		# Full list can be found at https://docs.python.org/2/library/time.html ( time.strftime() )
            longitude = convert(lngs, westeast)
    if altitude >= TopAlt:
        GPIO.output(CutOff, 1)
    if flightmode == True:
        flightmode = "1"
    elif flightmode == False:
        flightmode = "0"

    logstring = "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}".format(callsign, time, counter, latitude, longitude, satellites, flightmode, altitude, temp, humidity, temp2, pressure2, alt2, temp3, temp4)

    if Args.s:
        string = "{},{},{},{},{},{},{},{}".format(callsign, time, counter, latitude, longitude, satellites, flightmode, temp2)
    else:
        string = logstring

    with open('log.txt', 'r') as File:
        Read = File.read()
        Read = Read.split("\n")
    with open('log.txt', 'w') as File:
        Out = Read.append('{}'.format(logstring))
        for A in Read:
            File.write(A+"\n")
    csum = str(hex(crc16f(string))).upper()[2:]
    csum = csum.zfill(4)
    datastring = str("SEND$$" + string + "*" + csum + "\n")
    counter += 1
    print "Sending: ", datastring
    time_.sleep(5)
    send(datastring)

def convert(position_data, orientation):
        decs = "" 
        decs2 = "" 
        for i in range(0, position_data.index('.') - 2): 
            decs = decs + position_data[i]
        for i in range(position_data.index('.') - 2, len(position_data) - 1):
            decs2 = decs2 + position_data[i]
        position = float(decs) + float(str((float(decs2)/60))[:8])
        if orientation == ("S") or orientation == ("W"): 
            position = 0 - position 
        return position

character = ""
datastring = ""
n = 0
while True:
    CurTime = time.time()
    EndLimit = (60 * 60) * 2
    if (CurTime - StartTime) > (EndLimit):		# Seconds -> Minutes -> Hours	( Currently 5 Minutes )
        print "Time is Up. Restarting"			# We are not running this for
        os.system("sudo reboot")			# days on end so recursion is no an issue.
        sys.exit(0)
    GPS = serial.Serial('/dev/ttyAMA0', 9600, timeout=1)
    GPS.flush()
    n = millis()
    
    while (millis() - n) < 3000:
	try:
	        datastring = GPS.readline()
	        print "Acquired this data string from serial: " + datastring
	        if datastring.startswith("$GPGGA"):
	            gps_set_success = False
	            sendUBX(setNav, len(setNav))
	            gps_set_success = getUBX_ACK(setNav)
	            parse_gps(datastring, gps_set_success)
	            break
	except:
		print "An error occured with GPS.readlin()"
		pass
 
    GPS.flush()
    GPS.close()


## TEST ## 

