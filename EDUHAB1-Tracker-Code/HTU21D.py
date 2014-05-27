#!/usr/bin/python
import struct, array, time, io, fcntl

I2C_SLAVE=0x0703
HTU21D_ADDR = 0x40
CMD_READ_TEMP_HOLD = "\xE3"
CMD_READ_HUM_HOLD = "\xE5"
CMD_READ_TEMP_NOHOLD = "\xF3"
CMD_READ_HUM_NOHOLD = "\xF5"
CMD_WRITE_USER_REG = "\xE6"
CMD_READ_USER_REG = "\xE7"
CMD_SOFT_RESET= "\xFE"

class i2c(object):
	def __init__(self, device, bus):
		self.fr = io.open("/dev/i2c-"+str(bus), "rb", buffering=0)
		self.fw = io.open("/dev/i2c-"+str(bus), "wb", buffering=0)
		fcntl.ioctl(self.fr, I2C_SLAVE, device)
		fcntl.ioctl(self.fw, I2C_SLAVE, device)

	def write(self, bytes):
		self.fw.write(bytes)

	def read(self, bytes):
		return self.fr.read(bytes)

	def close(self):
		self.fw.close()
		self.fr.close()

class HTU21D(object):
	def __init__(self):
		self.dev = i2c(HTU21D_ADDR, 1)
		self.dev.write(CMD_SOFT_RESET)
		time.sleep(.1)

	def crc8check(self, value):
		remainder = ( ( value[0] << 8 ) + value[1] ) << 8
		remainder |= value[2]
		divsor = 0x988000
		for i in range(0, 16):
			if( remainder & 1 << (23 - i) ):
				remainder ^= divsor
			divsor = divsor >> 1
		return not remainder
   
	def read_temperature(self):
		self.dev.write(CMD_READ_TEMP_NOHOLD)
		time.sleep(.1)
		data = self.dev.read(3)
		buf = array.array('B', data)
		if self.crc8check(buf):
			temp = (buf[0] << 8 | buf [1]) & 0xFFFC
			temp = -46.85 + (175.72 * (temp / 65536.0))
			return temp
		else:
			return -255
         
	def read_humidity(self):
		self.dev.write(CMD_READ_HUM_NOHOLD)
		time.sleep(.1)
		data = self.dev.read(3)
		buf = array.array('B', data)
		if self.crc8check(buf):
			humid = (buf[0] << 8 | buf [1]) & 0xFFFC
			humid = -6.0 + (125.0 * (humid / 65536.0))
			return humid
		else:
			return -255
         
if __name__ == "__main__":
	obj = HTU21D()
	while True:
		start1 = time.time()
		Temp = obj.read_temperature()
		end1 = time.time()
		start2 = time.time()
		Humid = obj.read_humidity()
		end2 = time.time()
		print "Took {}ms to Poll Temp     -> {:5.2f}".format(int((end1-start1)*10), Temp)
		print "Took {}ms to Poll Humidity -> {:5.2f}\n".format(int((end2-start2)*10), Humid)
#		print "\nTemp: {}C\nHumidity: {}%".format(Temp, Humid)

