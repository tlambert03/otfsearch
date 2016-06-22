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
					# the goal is simply to rename the file
					s = F.split('_')
					i = s.index('visit')
					s.pop(i)
					num = s.pop(i)
					e = s.pop(-1).split(".")
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


def makeotf(infile, outfile=None, nimm=1.515, na=1.42, beaddiam=0.11, angle=None, fixorigin=(3,20), background=None, leavekz='auto'):
	if outfile is None:
		outfile=os.path.splitext(infile)[0]+'.otf'
	header = Mrc.open(infile).hdr
	wave = header.wave[0]

	if not angle:
		angle = int(infile.split('_a')[1][0])
	
	try:
		fileoil = infile.split('_')[2]
	except:
		pass

	#pull out stuff like oil from otf name here
	spacings = config.spacings
	angles = config.angles

	if leavekz == 'auto':
		leaveKZs = {
			435 : [7, 10, 3],
			528 : [7, 10, 3],
			608 : [7, 10, 3],
			683 : [8, 11, 2]
		}
		leavekz = leaveKZs[wave]


	callPriism()

	com = [config.makeOTFapp, infile, outfile, '-angle', str(angles[wave][angle-1]), '-ls', str(spacings[wave])]
	com.extend(['-na', str(na), '-nimm', str(nimm), '-beaddiam', str(beaddiam)])
	com.extend(['-fixorigin', str(fixorigin[0]), str(fixorigin[1])])
	if leavekz:
		com.append('-leavekz')
		com.extend([str(n) for n in leavekz])
	if background:
		com.extend(['-background', str(background)])
	print " ".join(com)
	subprocess.call(com)

	return outfile


if __name__ == '__main__':
	
	import argparse

	parser = argparse.ArgumentParser(description='Apply channel registration to multi-channel file', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument('inputFile', help='The file to process', type=file)
	parser.add_argument('-o','--outputFile', help='Optional name of output file to process', default=None, metavar='FILE')
	parser.add_argument('-a','--angle', help='Angle of illumination', default=None, type=int)
	parser.add_argument('-i','--nimm', help='Refractive index of imersion oil', default=1.515, type=float)
	parser.add_argument('-n','--na', help='Numerical Aperture', default=1.42, type=float)
	parser.add_argument('-d','--beaddiam', help='Bead Diameter', type=float, default=0.11)
	parser.add_argument('-b','--background', help='background to subtract', type=int, default=None)
	parser.add_argument('-f','--fixorigin', help='the starting and end pixel for interpolation along kr axis', 
					 nargs="*", type=int, metavar='', default=None)
	parser.add_argument('-l','--leavekz', help='the pixels to be retained on kz axis', 
					 nargs=3, type=int, metavar=('kz1_1','kz1_2','kz2'), default=None)
	args = vars(parser.parse_args())

	if args['leavekz']:
		lkz=args['leavekz']
	else:
		lkz='auto'
	if args['fixorigin']:
		fo=args['fixorigin']
	else:
		fo=(3,20)

	makeotf(args['inputFile'].name, outfile=args['outputFile'], nimm=args['nimm'], na=args['na'], beaddiam=args['beaddiam'], 
		angle=args['angle'], background=args['background'], fixorigin=fo, leavekz=lkz)

