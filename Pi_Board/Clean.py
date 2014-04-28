from subprocess import Popen, PIPE
import os

Proc = Popen(["ls"], stdout=PIPE)

Count = 0
Read = Proc.stdout.readlines()
for A in Read:
	if A[:6] == "IMAGE_":
		print "Removing", A[:-1]
		os.system( "rm {}".format(A[:-1]) )
		Count = Count + 1

for A in Read:
	try:
		B = A.split(".")
		Cur = B[len(B)-1][:-1]
		if Cur == "pyc" or Cur == "save":
			os.system("rm {}".format(A[:-1]))
			print "Removing", A[:-1]
			Count = Count + 1
	except:
		print ""

print "{} Files removed.".format(Count)
