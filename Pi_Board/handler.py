import time, subprocess
from subprocess import PIPE, Popen

time.sleep(5)
DNull = open('/dev/null', 'w')
Proc = Popen(['sudo', 'python', 'eduhab.py', '-p', '-s', '-c', 'TWICK'])#, stdout=PIPE, stderr=PIPE)
Finished = False

while not Finished:
	Finished = Proc.poll()
	time.sleep(30)
