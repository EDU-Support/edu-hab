from subprocess import Popen, PIPE
import os

Proc = Popen(["ls"], stdout=PIPE)

ImgCount = 0
PycCount = 0
Read = Proc.stdout.readlines()

for A in Read:
	if A[:5].upper() == "IMAGE":
#		print "Removing", A[:-1]
		os.system( "rm {}".format(A[:-1]) )
		ImgCount = ImgCount + 1

for A in Read:
	try:
		B = A.split(".")
		Cur = B[len(B)-1][:-1]
		if Cur == "pyc" or Cur == "save":
			os.system("rm {}".format(A[:-1]))
#			print "Removing", A[:-1]
			PycCount = PycCount + 1
	except:
		print ""

print "{} Image Files removed.".format(ImgCount)
print "{} Pyc / Save Files removed.".format(PycCount)
