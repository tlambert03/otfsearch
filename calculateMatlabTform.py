from __init__ import goodChannel
import config 
import subprocess

def calcMatlabTform(inputFile,outpath=None, refChannels=None, iterations=None, dims=None, 
					bestplane=None, TformType=None, interpType=None):
	
	matlabString = "%s('%s'" % (config.MatlabTformCalc,inputFile)
	if outpath: matlabString += ",'outpath','%s'" % outpath
	if refChannels : matlabString += ",'referenceChannels', %s " % str(refChannels)
	if iterations : matlabString += ",'iterations', %d " % iterations
	if dims : matlabString += ",'dims', %d " % dims
	if bestplane : matlabString += ",'bestplane', '%s' " % bestplane
	if TformType : matlabString += ",'type', '%s' " % TformType
	if interpType : matlabString += ",'interp', '%s' " % interpType
	matlabString += "); exit;"

	print matlabString
	subprocess.call(['matlab', '-nosplash', '-nodesktop', '-nodisplay', '-r', matlabString])


if __name__ == '__main__':

	import argparse
	parser = argparse.ArgumentParser(description='Calcultate transformation matrices for Matlab image registration', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument('inputFile', help='The file to process', type=file)
	parser.add_argument('-o','--outpath', help='Destination directory for the registration file', default=None, type=str)
	parser.add_argument('-r','--refs', help='calculate matrices for only these reference channels', 
					default=None, nargs="*", type=goodChannel, metavar='WAVE')
	parser.add_argument('-n','--iter', help='Number of iterations', default=None, type=int)
	parser.add_argument('-d','--dims', help='measure 2D+1 or 3D transformations', default=None, choices=[2,3])
	parser.add_argument('-p','--plane', help='Method to pick plane for 2D Tform calculation', default=None, choices=['focus','max'])
	parser.add_argument('-t','--type', help='Transformation type', default=None, choices=['translation','rigid','similarity','affine'])
	parser.add_argument('-i','--interp', help='Interpolation type', default=None, choices=['linear','nearest','cubic','bicubic'])
	args = vars(parser.parse_args())

	calcMatlabTform(args['inputFile'].name,outpath=args['outpath'], refChannels=args['refs'], iterations=args['iter'], 
		dims=args['dims'], bestplane=args['plane'], TformType=args['type'], interpType=args['interp'])