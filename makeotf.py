import Mrc
import os
import config
import subprocess
from otfsearch import callPriism


def splitAngles(infile, outdir=None):
	"""divid image into nAngles components"""
	header = Mrc.open(infile).hdr
	numWaves = header.NumWaves
	numTimes = header.NumTimes
	imSize = header.Num
	nz = imSize[2]/(numTimes*numWaves)
	for ang in range(1,config.nAngles+1):
		if outdir:
			#outfile = os.path.join(outdir,("_a%d" % ang).join(os.path.splitext(os.path.basename(infile))))
			outfile = os.path.join(outdir,os.path.basename(infile).replace('visit_', "a%d_00" % ang))
		else:
			#outfile = ("_a%d" % ang).join(os.path.splitext(infile))
			outfile = infile.replace('visit_', "a%d_00" % ang)

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
			if (('a1' in F) or ('a2' in F) or ('a3' in F)) and not ('.otf' in F):
				outfile = F.replace('dv','otf')

				maxint = Mrc.open(os.path.join(angdir,F)).hdr.mmm1[1]
				if maxint < config.otfSigRange[1] and maxint > config.otfSigRange[0]:
					print "processing %s with maxint = %d" % (os.path.join(angdir,F),maxint)
					makeotf(os.path.join(angdir,F),os.path.join(angdir,outfile))
				else:
					print "skipping %s with maxint = %d" % (os.path.join(angdir,F),maxint)
				os.remove(os.path.join(angdir,F))
			#	visitnumber
			#	outfile
			#makeotf(F)

def searchparams(file, angle=1):

	import matplotlib.pyplot as plt
	import Mrc
	import numpy as np

	otfs =[]
	krange=range(1,4)
	narange=np.linspace(1.52,1.52,1)
	for k in krange:
		for NA in narange:
			otf = M.makeotf('/Users/talley/Desktop/528_testotf.dv', outfile='/Users/talley/Desktop/otfs/otfs528_testotf'+str(int(NA*100))+"_"+str(k)+".otf", na=NA, nimm=1.52, angle=angle, leavekz=(8,9,k) )
			otfs.append(otf)

	fig = plt.figure()
	for i in range(len(otfs)):
		indat = Mrc.bindFile(otfs[i])
		amplitude = np.sqrt(np.power(indat.imag,2)+np.power(indat.real,2))[:,]
		gamcor = (amplitude / 1000535.)**(1/2.5)

		ax = fig.add_subplot(len(krange), len(narange), i+1)
		ax.imshow(gamcor[2])
		ax.autoscale(True)
		ax.set_title(str(i))
		#axarr[i/len(krange), i%len(narange)].imshow(gamcor[1])
		#axarr[i/len(krange), i%len(narange)].set_title('NA %s, k2 %s' %(narange[i%len(narange)], krange[i/len(krange)] ))

	plt.show()


def makeotf(infile, outfile=None, nimm=1.515, na=1.42, beaddiam=0.11, angle=None, fixorigin=(3,20), background=None, leavekz='auto'):
	if outfile is None:
		#outfile=os.path.splitext(infile)[0]+'.otf'
		outfile = infile.replace('.dv','.otf')

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
			435 : [6, 7, 2],
			528 : [7, 9, 2],
			608 : [8, 10, 2],
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
	#print " ".join(com)
	subprocess.call(com)

	return outfile


if __name__ == '__main__':
	
	import argparse

	parser = argparse.ArgumentParser(description='Apply channel registration to multi-channel file', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument('inputFile', help='The file to process')
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

	if os.path.isdir(args['inputFile'])	:
		batchmakeotf(args['inputFile'])
	else:
		makeotf(args['inputFile'], outfile=args['outputFile'], nimm=args['nimm'], na=args['na'], beaddiam=args['beaddiam'], 
			angle=args['angle'], background=args['background'], fixorigin=fo, leavekz=lkz)

