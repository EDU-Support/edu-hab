# Thanks to UKHAS community and ibanezzmat13 for help the origonal code
# and James at Pridopia for making it all work



#!/usr/bin/python

import argparse, serial, crcmod
import smbus, os, time, glob
import re, picamera, signal
import time as time_
from subprocess import PIPE, Popen
from Adafruit_BMP085 import BMP085
from HTU21D import HTU21D
import RPi.GPIO as GPIO

Path = os.path.dirname( os.path.abspath( __file__ ) )

if os.getcwd() != Path:
	os.chdir(Path)

global TopAlt
global CutOff
global DropDelay
global HasTriggered
global DropFinished
TopAlt = 12000				# Altitude in meters to cut off.
CutOff = 25				# GPIO Pin in BCM mode to trigger
DropDelay = 10				# Delay in seconds to disable the GPIO pin after it's been "dropped"
HasTriggered = False			# Boolean to test if it has been dropped or not.
DropFinished = False			# Bool to test if the Drop has finished.

NULL = open('/dev/nulll','w')
#Still = ["raspistill", "-w", "1920", "-h", "1080", "-t", "300000", "-tl", "5000", "-o", "Image-%04d.jpg", "-op", "50"]
#Raspistill = Popen(Still, stdout=NULL)	# 72 Hours = 4320 Minutes = 259200 Seconds = 259200000 Milliseconds
					# Delay between pictures = 5 minutes, Total runtime = 3 days

##--------------##
TESTING = False ## If you want to test the Cut Off, Enable this (True).
##--------------##

GPIO.setmode(11)
GPIO.setwarnings(False)
GPIO.setup(CutOff, GPIO.OUT)

Devices = {
"BMP085": True,
"TMP102": True,
"HTU21D": True,
"DS18B20": False
}

StartTime = time.time()

if Devices["HTU21D"]:
	HTU21D = HTU21D()
if Devices["BMP085"]:
	bmp = BMP085(0x77, 3)

time_set = False
gps_set_success = False
bus = smbus.SMBus(1)
DNull = open('/dev/null', 'w')
os.system("chmod +x ./DHT")
Parser = argparse.ArgumentParser(description="Parse and decipher GPS signals from serial. Output to Tx with flightmode enabled.")

Parser.add_argument('-c', nargs='?', help='Custom Callsign for the Tx.')
Parser.add_argument('-p', action='store_const', const='picture', help='Enable timelapse / picture mode.')
Parser.add_argument('-s', action='store_const', const='silent', help='Enable smaller output ( Less chance of error and more data per minute ).')

Args = Parser.parse_args()
print Args.c, Args.p, Args.s
if Args.c:
	callsign = Args.c
else:
	callsign = "PRID"
if Args.s:
	print "Verbose data disabled / Small data stream enabled."
#if Args.p:
#	DNull = open('/dev/null', 'w')
#	Camera = Popen(["sudo", "python", "timelapse.py"], stdout=DNull, stderr=DNull)

setNav = bytearray.fromhex("B5 62 06 24 24 00 FF FF 06 03 00 00 00 00 10 27 00 00 05 00 FA 00 FA 00 64 00 2C 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 16 DC")

def Capture(Delay=1):
    Time = time.strftime("%b_%d_2014--%H-%M-%S")
    Name = "IMAGE_"+Time+".jpg"
    with picamera.PiCamera() as Camera:
        Camera.resolution = (1920, 1080)
        Camera.start_preview()
        Camera.exif_tags['IFD0.Artist'] = '507269646F706961204C74642E'	# Don't Change!
        Camera.exif_tags['IFD0.Copyright'] = '507269646F706961204C74642E'	# Don't Change!
        time_.sleep(Delay)
        Camera.capture(Name)
        Camera.stop_preview()


def gettmp(addr):
	data = bus.read_i2c_block_data(addr, 0)
	msb = data[0]
	lsb = data[1]
	neg = data[2]
	tmp = int((((msb << 8) | lsb) >> 4) * 0.0625)
	print "LOOK HERE JED ----{}---- {} : {} : {} : {}".format(tmp, data[0], data[1], data[2], data[3])
	#if neg == 0:
	#	tmp = 255-tmp
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
	GPS = serial.Serial('/dev/ttyAMA0', 9600, timeout=1)
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

	ackPacket[0] = 0xB5	# header
	ackPacket[1] = 0x62	# header
	ackPacket[2] = 0x05	# class
	ackPacket[3] = 0x01	# id
	ackPacket[4] = 0x02	# length
	ackPacket[5] = 0x00	# spacing
	ackPacket[6] = MSG[2]	# ACK class
	ackPacket[7] = MSG[3]	# ACK id
	ackPacket[8] = 0	# CK_A
	ackPacket[9] = 0	# CK_B

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
	global TESTALTITUDE
	satellites = 0
	lats = 0
	northsouth = 0
	lngs = 0
	westeast = 0
	altitude = 0
	if TESTING:
		altitude = TESTALTITUDE
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
				if Value == "HTU21D" and Devices[Value]:
					print "HTU21D Enabled"
					start = time_.time()
					elap = 0
					while elap < 5:
						elap = time_.time() - start
						temp = float(HTU21D.read_temperature())
						humidity = float(HTU21D.read_humidity())
						temp = "%.2f" % temp
						humidity = "%.2f" % humidity
						print "HTU21D -> {}C, {}%".format(temp, humidity)
						if temp  and humidity:
							print "Time elapsed for HTU21D: {}".format(elap)
							break
				if Value == "BMP085" and Devices[Value]:
					print "BMP085 Enabled"
					start = time_.time()
					elap = 0
					while elap < 5:
						try:
							elap = time_.time() - start
							temp2 = "%.2f" % bmp.readTemperature()
							pressure2 = "%.1f" % float(bmp.readPressure()/100.0)
							alt2 = "%.1f" % bmp.readAltitude()
							print "BMP085 -> {}C, {}HPa, {}m".format(temp2, pressure2, alt2)
							if temp2 == "12.8" and pressure2 == "125.1" and alt2 == "14557.3":
								temp2 = pressure2 = alt2 = 0
								break
							if temp2 and pressure2 and alt2:
								print "Time elapsed for BMP085: {}".format(elap)
								break
						except:
							pass
				if Value == "TMP102" and Devices[Value]:
					print "TMP102 Enabled"
					start = time_.time()
					while elap < 5:
						elap = time_.time() - start
						temp3 = "%.2f" % gettmp(0x49)
						print "TMP102 -> {}".format(temp3)
						if temp3:
							print "Time elapsed for TMP102: {}".format(elap)
							break
				if Value == "DS18B20" and Devices[Value]:
					"DS18B20 Enabled"
					start = time_.time()
					elap = 0
					while elap < 5:
						elap = time_.time() - start
						temp4 = read_B18()
						print "DS18B20 -> {}".format(temp4)
						if temp4:
							print "Time elapsed for DS18B20: {}".format(elap)
							break
			raw_time = data[1]
			lats = data[2]
			northsouth = data[3]
			lngs = data[4]
			westeast = data[5]
			satellites = data[7]
			altitude = data[9]
			if TESTING:
				altitude = TESTALTITUDE	# This will set the altitude for comparing / sending etc.
			if time_set == False:
				set_time(raw_time)
			time = float(raw_time)
			string = "%06i" % time
			hours = string[0:2]
			minutes = string[2:4]
			seconds = string[4:6]
			time = "{}:{}:{}".format(hours, minutes, seconds)	# Could also use time.strftime("%H:%M:S") which will output HOURS:MINUTES:SECONDS
			latitude = convert(lats, northsouth)			# Full list can be found at https://docs.python.org/2/library/time.html ( time.strftime() )
			longitude = convert(lngs, westeast)
	global HasTriggered
	global DropFinished
	global DropStart
	global DropDelay
	global CutOff
	global TopAlt
	if HasTriggered and DropFinished == False:
		if (time_.time() - DropStart) > DropDelay:
			#print "Drop has finished. GPIO {} to Off.".format(CutOff)
			GPIO.output(CutOff, 0)
			DropFinished = True
	if float(altitude) >= TopAlt and not HasTriggered and not DropFinished:
		#print "Drop Starting! GPIO {} Triggered!".format(CutOff)
		GPIO.output(CutOff, 1)
		HasTriggered = True
		DropStart = time_.time()
	#flightmode = int(flightmode)	# Accidental overwriting?

	logstring = "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}".format(callsign, time, counter, latitude, longitude, satellites, int(flightmode), altitude, temp, humidity, temp2, pressure2, alt2, temp3, temp4, int(HasTriggered))

	if Args.s:
		string = "{},{},{},{},{},{},{},{},{},{}".format(callsign, time, counter, latitude, longitude, satellites, int(flightmode), temp2, altitude, int(HasTriggered))
	else:
		string = logstring
	if not os.path.isfile('log.txt'):
		with open('log.txt', 'w+') as File:
			File.write("Log Text:\n")
	with open('log.txt', 'r') as File:
		Read = File.read()
		Read = Read.split("\n")
	with open('log.txt', 'w+') as File:
		Out = Read.append('{}'.format(logstring))
		for A in Read:
			File.write(A+"\n")
	csum = str(hex(crc16f(string))).upper()[2:]
	csum = csum.zfill(4)
	datastring = str("$$$$$$" + string + "*" + csum + "\n")
	counter += 1
	print "Sending >> ", datastring
	time_.sleep(0.1)
	send(datastring)
	if Args.p:
		print "Taking Picture!"
		Capture()
		print "Finished Taking Picture."

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
TESTALTITUDE = 9000
while True:
	if TESTING:
		TESTALTITUDE += 1000
	CurTime = time.time()
	Hours = 2
	EndLimit = (60 * 60) * Hours			# 30 Minutes
	if (CurTime - StartTime) > (EndLimit):		# Seconds -> Minutes -> Hours	( Currently 5 Minutes )
		with open('errorlog.txt', 'r+') as File:
			Read = File.read()
		with open('errorlog.txt', 'w+') as File:
			File.write(Read+"The start time is {}, Current time is {},  and it has been running for {}\n".format(StartTime, CurTime , CurTime - StartTime))
		print "Time is Up. Restarting"		# We are not running this for
		os.system("sudo reboot")		# days on end so recursion is no an issue.
		sys.exit(0)
	GPS = serial.Serial('/dev/ttyAMA0', 9600, timeout=1)
	GPS.flush()
	n = millis()
	while (millis() - n) < 3000:
		try:
			datastring = GPS.readline()
			if datastring.startswith("$GPGGA"):
				print "Acquired this data string from serial: " + datastring
				gps_set_success = False
				sendUBX(setNav, len(setNav))
				gps_set_success = getUBX_ACK(setNav)
				parse_gps(datastring, gps_set_success)
				break
		except:
			pass

	GPS.flush()
	GPS.close()
