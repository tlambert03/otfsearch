import Mrc
import os
import config
import subprocess
from __init__ import callPriism


def splitAngles(infile, outdir=None):
	"""divid image into nAngles components"""
	header = Mrc.open(infile).hdr
	numWaves = header.NumWaves
	numTimes = header.NumTimes
	imSize = header.Num
	nz = imSize[2]/(numTimes*numWaves)
	for ang in range(1,config.nAngles+1):
		if outdir:
			outfile = os.path.join(outdir,("_a%d" % ang).join(os.path.splitext(os.path.basename(infile))))
		else:
			outfile = ("_a%d" % ang).join(os.path.splitext(infile))
		callPriism([ 'CopyRegion', infile, outfile, '-z=%d:%d' % ((ang-1)*nz/3,ang*nz/3 - 1) ])


def batchmakeotf(directory):
	# create temp folder for reconstructions

	angleDirs = []
	anglesDir=None
	# seperate angles
	for root, subdirs, files in os.walk(directory):
		#print root
		for F in files:
			if F.endswith('.dv') and not any([x in F for x in ['a1','a2','a3']]):
				fullpath=os.path.join(root,F)
				anglesDir = os.path.join(root,'angles')
				try:
					os.makedirs(anglesDir)
				except:
					pass
				print "seperating angles: %s" % F
				splitAngles(fullpath,anglesDir)
		if anglesDir: 
			angleDirs.append(anglesDir)
			anglesDir=None

	# batch make otf
	for angdir in list(set(angleDirs)):
		for F in os.listdir(angdir):
			if F.endswith('_a1.dv') or F.endswith('_a2.dv') or F.endswith('_a3.dv'):
				if "_visit_" in F:
					
					# oh god the terrible horror of this code...
					s = F.split('_')
					i = s.index('visit')
					s.pop(i)
					num = s.pop(i)
					e = s.pop(-1).split(".")
					ext = e.pop(-1)
					e.append(str(num).zfill(3))
					s.extend(e)
					outfile = "_".join(s) + ".otf"

					maxint = Mrc.open(os.path.join(angdir,F)).hdr.mmm1[1]
					if maxint < config.otfSigRange[1] and maxint > config.otfSigRange[0]:
						makeotf(os.path.join(angdir,F),os.path.join(angdir,outfile))
					else:
						print "skipping %s with maxint = %d" % (os.path.join(angdir,F),maxint)
					os.remove(os.path.join(angdir,F))
				#	visitnumber
				#	outfile
				#makeotf(F)


def makeotf(infile, outfile=None):
	if outfile is None:
		outfile=os.path.splitext(infile)[0]+'.otf'
	header = Mrc.open(infile).hdr
	wave = header.wave[0]

	fileangle = int(infile.split('_a')[1][0])
	fileoil = infile.split('_')[2]

	#pull out stuff like oil from otf name here
	spacings = config.spacings
	angles = config.angles

	leaveKZs = {
		435 : [7, 10, 3],
		528 : [7, 10, 3],
		608 : [7, 10, 3],
		683 : [8, 11, 2]
	}

	callPriism()

	com = [config.makeOTFapp, infile, outfile, '-angle', str(angles[wave][fileangle-1]), '-ls', str(spacings[wave])]
	com.extend(['-na', '1.42', '-nimm', '1.515', '-beaddiam', '0.11', '-fixorigin', '3', '20', '-leavekz'])
	com.extend([str(n) for n in leaveKZs[wave]])
	subprocess.call(com)