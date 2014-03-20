#!/usr/bin/python
import argparse, serial, crcmod, smbus, os, time, glob, re
import time as time_
from subprocess import PIPE, Popen
from Adafruit_BMP085 import BMP085
 
time_set = False
gps_set_success = False
bmp = BMP085(0x77, 3)
bus = smbus.SMBus(1)
DNull = open('/dev/null', 'w')

Parser = argparse.ArgumentParser(description="Parse and decipher GPS signals from serial. Output to Tx with flightmode enabled.")
Parser.add_argument('-p', action='store_const', const='picture_mode',
	help='Enable timelapse / picture mode.')

Args = Parser.parse_args()
if Args.p:
	Timelapse = Popen(["sudo", "python", "timelapse.py"], stdout=DNull, stderr=DNull)

setNav = bytearray.fromhex("B5 62 06 24 24 00 FF FF 06 03 00 00 00 00 10 27 00 00 05 00 FA 00 FA 00 64 00 2C 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 16 DC")
def gettmp(addr):
    data = bus.read_i2c_block_data(addr, 0)
    msb = data[0]
    lsb = data[1]
    return int((((msb << 8) | lsb) >> 4) * 0.0625)

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

    ackPacket[0] = int('0xB5', 16) #header
    ackPacket[1] = int('0x62', 16) #header
    ackPacket[2] = int('0x05', 16) #class
    ackPacket[3] = int('0x01', 16) #id
    ackPacket[4] = int('0x02', 16) #length
    ackPacket[5] = int('0x00', 16)
    ackPacket[6] = MSG[2] #ACK class
    ackPacket[7] = MSG[3] #ACK id
    ackPacket[8] = 0 #CK_A
    ackPacket[9] = 0 #CK_B

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
crc16f = crcmod.predefined.mkCrcFun('crc-ccitt-false') # function for CRC-CCITT checksum
disable_sentences()
counter = 0 # this counter will increment as our sentence_id

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
            if (time.time() - Start) > 60:
                return 0, 0
        time.sleep(2)


def set_time(time):
    data = list(time) # split the time into individual characters
    hours = time[0] + time[1] 
    minutes = time[2] + time[3]
    parsed_datetime = hours + minutes # finalise the time to be set
    os.system('sudo date --set ' + str(parsed_datetime)) # set the OS time
    time_set = True # show that time is now set

def send(data):
    NTX2 = serial.Serial('/dev/ttyAMA0', 50, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_TWO) # opening serial at 50 baud for radio transmission with 8 character bits, no parity and two stop bits
    NTX2.write(data) # write final datastring to the serial port
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
    
 
    if NMEA_sentence.startswith("$GPGGA"): # if we got a PUBX sentence
        print NMEA_sentence
        data = NMEA_sentence.split(",") # split sentence into individual fields
        if data[6] == "0": # if it does start with a valid sentence but with no fix
            print "No Lock"
            pass
        else: # if it does start with a valid sentence and has a fix
            # parsing required telemetry fields
            satellites = data[7]
            lats = data[2]
            northsouth = data[3]
            lngs = data[4]
            westeast = data[5]
            altitude = data[9]
            raw_time = data[1]
            if time_set == False:
                set_time(raw_time)
            time = float(raw_time)
            string = "%06i" % time # creating a string out of time (this format ensures 0 is included at start if any)
            hours = string[0:2]
            minutes = string[2:4]
            seconds = string[4:6]
            time = str(str(hours) + ':' + str(minutes) + ':' + str(seconds)) # the final time string in form 'hh:mm:ss'
            latitude = convert(lats, northsouth)
            longitude = convert(lngs, westeast)
            Temperature, Humidity = DHT(17)
            temp = Temperature
            humidity = Humidity
            temp2 = "%.1f" % bmp.readTemperature()
            pressure2 = "%.1f" % float(bmp.readPressure()/100.0)
            alt2 = "%.1f" % bmp.readAltitude()
            temp3 = "%.1f" % gettmp(0x48)
            temp4 = read_B18()

    callsign = "TWICK"
    if flightmode == True:
        flightmode = "1"
    elif flightmode == False:
        flightmode = "0"

    string = "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}".format(callsign, time, counter, latitude, longitude, satellites, flightmode, altitude, temp, humidity, temp2, pressure2, alt2, temp3, temp4)
    with open('log.txt', 'r') as File:
        Read = File.read()
        Read = Read.split("\n")
    with open('log.txt', 'w') as File:
        Out = Read.append('{}'.format(string))
        for A in Read:
            File.write(A+"\n")
    csum = str(hex(crc16f(string))).upper()[2:] # running the CRC-CCITT checksum
    csum = csum.zfill(4) # creating the checksum data
    datastring = str("$$" + string + "*" + csum + "\n") # appending the datastring as per the UKHAS communication protocol
    counter += 1 # increment the sentence ID for next transmission
    print "now sending the following:", datastring
    send(datastring) # send the datastring to the send function to send to the NTX2

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
    
    GPS = serial.Serial('/dev/ttyAMA0', 9600, timeout=1) # open serial
    GPS.flush()
    n = millis()
    
    while (millis() - n) < 3000:
        datastring = GPS.readline()
        print "Acquired this data string from serial: " + datastring
        if datastring.startswith("$GPGGA"):
            gps_set_success = False
            sendUBX(setNav, len(setNav)) # send command to enable flightmode
            gps_set_success = getUBX_ACK(setNav) # check the flightmode is enabled
            parse_gps(datastring, gps_set_success) # run the read_gps function to get the data and parse it with status of flightmode
            break
 
    GPS.flush()
    GPS.close()
