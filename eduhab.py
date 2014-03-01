# thanks to ibanezzmatt13 for the origonal code and a great deal of help
# and many thanks to the hab community http://ukhas.org.uk/
# requires the adafruit BMP085 library
# baud rate is set at 50


#!/usr/bin/python

from Adafruit_BMP085 import BMP085 
import os
import serial
import crcmod
import time
import time as time_
 
time_set = False
gps_set_success = False
bmp = BMP085(0x77)
 
# byte array for a UBX command to set flight mode
setNav = bytearray.fromhex("B5 62 06 24 24 00 FF FF 06 03 00 00 00 00 10 27 00 00 05 00 FA 00 FA 00 64 00 2C 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 16 DC")
 
 
# function to disable all NMEA except the GPGGA sentences
def disable_sentences():
    
    GPS = serial.Serial('/dev/ttyAMA0', 9600, timeout=1) # open serial to write to GPS
 
    # Disabling all NMEA sentences 
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
    GPS.close() # close serial
      
#create function equivalent to arduino millis();
def millis():
    return int(round(time_.time() * 1000))
     
# fucntion to send commands to the GPS 
def sendUBX(MSG, length):
    ubxcmds = ""
    for i in range(0, length):
        GPS.write(chr(MSG[i])) #write each byte of ubx cmd to serial port
        ubxcmds = ubxcmds + str(MSG[i]) + " " # build up sent message debug output string
    GPS.write("\r\n") #send newline to ublox
 
 
#calcuate expected UBX ACK packet and parse UBX response from GPS
def getUBX_ACK(MSG):
    
    b = 0
    ackByteID = 0
    ackPacket = [0 for x in range(10)]
    startTime = millis()
 
        
    #construct the expected ACK packet
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
 
 
    #calculate the checksums
    for i in range(2,8):
        ackPacket[8] = ackPacket[8] + ackPacket[i]
        ackPacket[9] = ackPacket[9] + ackPacket[8]
 
 
    for byt in ackPacket:
        print byt
                
    while 1:
        #test for success
        if ackByteID > 9 :
            #all packets are in order
            return True
 
 
        #timeout if no valid response in 3 secs
        if millis() - startTime > 3000:
            return False
        #make sure data is availible to read
        if GPS.inWaiting() > 0:
            b = GPS.read(1)
                   
            #check that bytes arrive in the sequence as per expected ACK packet
            if ord(b) == ackPacket[ackByteID]:
                ackByteID += 1
                #print ord(b)
            else:
                ackByteID = 0 #reset and look again, invalid order
 
crc16f = crcmod.predefined.mkCrcFun('crc-ccitt-false') # function for CRC-CCITT checksum
disable_sentences()
counter = 0 # this counter will increment as our sentence_id
 
# function to set the OS time to GPS time
def set_time(time):
   
    data = list(time) # split the time into individual characters
    
    # construct the hours and minutes variables
    hours = time[0] + time[1] 
    minutes = time[2] + time[3]
    
    parsed_datetime = hours + minutes # finalise the time to be set
    os.system('sudo date --set ' + str(parsed_datetime)) # set the OS time
    time_set = True # show that time is now set
   
 
# function to send both telemetry and packets
def send(data):
    NTX2 = serial.Serial('/dev/ttyAMA0', 50, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_TWO) # opening serial at 300 baud for radio transmission with 8 character bits, no parity and two stop bits
    NTX2.write(data) # write final datastring to the serial port
    NTX2.close()
    
# function to read the gps and process the data it returns for transmission
def parse_gps(NMEA_sentence, flightmode):
 
    # set some fields to zero for transmitting without lock
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
    pressure = 0
    
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
            altitude = int(float(data[9]))
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
            temp = bmp.readTemperature()
            pressure = bmp.readPressure()
 
    # the data fields below can be sent when no lock from GPS
    callsign = "TWICK"
    
        
    string = str(callsign + ',' + str(time) + ',' + str(counter) + ',' + str(latitude) + ',' + str(longitude) + ',' + str(satellites) + ',' + str(flightmode) + ',' + str(altitude)+ ',' + str(temp)+ ',' + str(pressure)) # the data string
    csum = str(hex(crc16f(string))).upper()[2:] # running the CRC-CCITT checksum
    csum = csum.zfill(4) # creating the checksum data
    datastring = str("$$" + string + "*" + csum + "\n") # appending the datastring as per the UKHAS communication protocol
    counter += 1 # increment the sentence ID for next transmission
    print "now sending the following:", datastring
    send(datastring) # send the datastring to the send function to send to the NTX2
 
# function to convert latitude and longitude into a different format 
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
