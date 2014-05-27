Software Setup

Use these arguments to enable functions:

Start Image Timelapse (set to 30 secs) -p
Set your own Callsign -c
Start sending short string for transmission -s

Short string = callsign, time, counter, latitude, longitude, satellites, flightmode, temp2, altitude, cutdown

Example: sudo python eduhab.py -p -s -c EDUHAB1

The code has a cutdown function that sends GPIO pin 25 high on activation

Parameters are set here:

TopAlt = 12000 # Altitude in meters to cut off.
CutOff = 25 # GPIO Pin in BCM mode to trigger
DropDelay = 10 # Delay in seconds to disable the GPIO pin after it's been "dropped"

To test the cutdown logic set this line to True

##--------------##
TESTING = False ## If you want to test the Cut Off, Enable this (True).
##--------------##

This will cause the altitude to increase by an amount set here:

TESTALTITUDE += 1000

The Pi will restart at a pre-determined time interval set here:

EndLimit = (60 * 60) * Hours			# 30 Minutes

The sensors BMP085, TMP102, HTU21D can be Enabled or Disabled here:

"BMP085": True,
"TMP102": True,
"HTU21D": True,
"DS18B20": False

To adjust camera settings use the picamera module commands http://picamera.readthedocs.org/en/release-1.4/

Camera.resolution = (1920, 1080)
Camera.start_preview()
        Camera.exif_tags['IFD0.Artist'] = '507269646F706961204C74642E'	# Don't Change!
        Camera.exif_tags['IFD0.Copyright'] = '507269646F706961204C74642E'	# Don't Change!
        time_.sleep(Delay)
        Camera.capture(Name)
        Camera.stop_preview()
        
The sensor data is recorded in the log.txt file with a timestamp

Run sudo python clean.py to remove all your old images
        
