import os
import subprocess

def cudaSIrecon(inputFile, otfFile, outputFile=None, app='/usr/local/bin/sir', **kwargs):
	'''
	python interface for Lin's CUDAsirecon command line app
	'''
	if not outputFile:
		namesplit = os.path.splitext(inputFile)
		outputFile = namesplit[0]+"_PROC"+namesplit[1]

	commandArray=[app,inputFile,outputFile,otfFile]

	for k,v in kwargs.items():
		if isinstance(v,bool): commandArray.extend(["--%s" % k, str(int(v))])
		elif v: print commandArray.extend(["--%s" % k, str(v)])

	#print " ".join(commandArray)

	try:
		process = subprocess.Popen(commandArray, stdout=subprocess.PIPE)
		output = process.communicate()[0]
		return output
	except OSError as e:
		print "error calling CUDA_SIMrecon: %s" % e
		print "App may not be located at: %s " % app
		return 0



if __name__=="__main__":
	import argparse
	parser = argparse.ArgumentParser(description='Single SIM file reconstruction', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument('input-file', help='input file (or data folder in TIFF mode)', type=file)
	parser.add_argument('otf-file', help='OTF file', type=file)
	parser.add_argument('--output-file', help='output file (or filename pattern in TIFF mode)', default=None)
	parser.add_argument('-w','--wiener', help='Wiener constant', type=float)
	parser.add_argument('-b','--background', help='number of output orders; must be <= norders', type=int)
	parser.add_argument('--usecorr', help='use the flat-field correction file provided', type=file)
	parser.add_argument('-c','--config', help='name of a file of a configuration.', type=file)
	# CCD correction file is a .dv file with two 2D floating-point images. 
	# The x-y dimension of the images has to match the SIM raw data you are 
	# processing. The first contains the dark-field image of the camera, 
	# usually obtained by averaging hundreds or thousands of camera exposures 
	# with no light. The second is sort of what you call the per-pixel gain 
	# image, except that it needs to be the inverse of that gain. You first 
	# obtain the gains for each pixel by whatever means, then divide all gains 
	# by the median of all gains, and finally take the inversion of the 
	# normalized gains. This image should have value distributed around 1.0.
	parser.add_argument('--ndirs', help='number of directions', type=int)
	parser.add_argument('--nphases', help='number of phases per direction', type=int)
	parser.add_argument('--nordersout', help='number of output orders; must be <= norders', type=int)
	parser.add_argument('--angle0', help='angle of the first direction in radians', type=float)
	parser.add_argument('--ls', help='number of phases per direction', type=float)
	parser.add_argument('--na', help='Detection numerical aperture', type=float)
	parser.add_argument('--nimm', help='refractive index of immersion medium', type=float)
	parser.add_argument('--zoomfact', help='lateral zoom factor', type=float)
	parser.add_argument('--zzoom', help='axial zoom factor', type=float)
	parser.add_argument('--explodefact', help='artificially exploding the reciprocal-space distance between orders by this factor', type=float)
	parser.add_argument('--nofilteroverlaps', help='do not filter the overlaping region between bands (usually used in trouble shooting)', type=bool)
	parser.add_argument('--forcemodamp', help='modamps forced to these values')
	parser.add_argument('--k0angles', help='user given pattern vector k0 angles for all directions')
	parser.add_argument('--otfRA', help='using rotationally averaged OTF', type=bool)
	parser.add_argument('--fastSI', help='SIM data is organized in Z->Angle->Phase order, default being Angle->Z->Phase', type=bool)
	parser.add_argument('--k0searchAll', help='search for k0 at all time points', type=bool)
	parser.add_argument('--equalizez', help='bleach correcting for z', type=bool)
	parser.add_argument('--equalizet', help='bleach correcting for time', type=bool)
	parser.add_argument('-d','--dampenOrder0', help='dampen order-0 in final assembly', type=bool)
	# It sort of apply a high pass filter (an inverted Gaussian centering around the origin) 
	# to the order 0 component (i.e., what conventional wide-field microscope would get normally) 
	# to suppress the all low-resolution information, not just the singularity at the origin 
	# as what suppress_singularities does. The "haloing" stuff comes mostly from incorrect 
	# enhancing or subduing of the low-resolution stuff, so it makes sense you see less of 
	# that after dampenOrder0 is applied. 
	parser.add_argument('--nosuppress', help='do not suppress DC singularity in final assembly (good idea for 2D/TIRF data)', type=bool)
	parser.add_argument('--nokz0', help='do not use kz=0 plane of the 0th order in the final assembly', type=bool)
	parser.add_argument('--gammaApo', help='output apodization gamma; 1.0 means triangular apo', type=bool)
	parser.add_argument('--saveprefiltered', help='save separated bands (half Fourier space) into a file and exit', type=bool)
	parser.add_argument('--savealignedraw', help='save drift-fixed raw data (half Fourier space) into a file and exit', type=bool)
	parser.add_argument('--saveoverlaps', help='save overlap0 and overlap1 (real-space complex data) into a file and exit', type=bool)
	parser.add_argument('--2lenses', help='I5S data', type=bool)
	args = vars(parser.parse_args())


	inputFile = args.pop('input-file').name
	otfFile = args.pop('otf-file').name
	if 'output_file' in args: 
		outputFile = args.pop('output_file')
	else:
		outputFile = None
	cudaSIrecon(inputFile,otfFile,outputFile,**args)

