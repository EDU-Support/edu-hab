import picamera, time, os

Delay = 30

def Capture():
    Time = time.strftime("%b_%d_2014--%H-%M-%S")
    Name = "IMAGE_"+Time+".jpg"
    with picamera.PiCamera() as Camera:
        Camera.resolution = (1920, 1080)
        Camera.start_preview()
        Camera.exif_tags['IFD0.Artist'] = '507269646F706961204C74642E'		# Don't Change!
        Camera.exif_tags['IFD0.Copyright'] = '507269646F706961204C74642E'	# Don't Change!
        time.sleep(1)
        Camera.capture(Name)
        Camera.stop_preview()
    os.system('convert {} -pointsize 76 -fill red -annotate +20+100 "{}" {}'.format(Name, Time, Name))


while True:
	time.sleep(Delay)
	Capture()
