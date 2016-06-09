import argparse
import config
from __init__ import makeBestReconstruction, goodChannel, cropCheck

def otfAssignment(string):
	if "=" in string and len(string.split('='))==2:
		k,v = string.split('=')
		if goodChannel(k) and goodChannel(v):
			return [k,v]
	msg = "OTF force %r is not of the form CHANNEL=OTF (each in wavelengths)" % string
	raise argparse.ArgumentTypeError(msg)

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='OTF matching program', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

	parser.add_argument('inputFile', help='The file to process', type=file)
	parser.add_argument('-a','--age', help='max age of OTF file in days', default=None, type=int)
	parser.add_argument('-n','--num', help='max number of OTF files used', default=config.maxNum, type=int)
	parser.add_argument('-l','--oilmin', help='min oil refractive index to search', default=config.oilMin, type=int, choices=config.valid['oilMin'], metavar='1510-1530')
	parser.add_argument('-m','--oilmax', help='max oil refractive index to search', default=config.oilMax, type=int, choices=config.valid['oilMax'], metavar='1510-1530')
	parser.add_argument('-f', '--force', help='Force OTF wave for specific channel in form: <CHAN>=<OTF>', 
				metavar='<CHAN>=<OTF>', nargs=1, action='append',type=otfAssignment, default=[])
				#parser.add_argument('-t','--time', help='number of timepoints to use', default=config.maxNum)
	parser.add_argument('-p','--crop', help='ROI crop size to use for testing', default=config.cropsize, type=cropCheck)
	parser.add_argument('-c','--channels', help='channels to process (sep by spaces)', default=None, nargs="*", type=goodChannel, metavar='CHAN')
	#parser.add_argument('-f','--forceotf', help='force wavelength to use specified OTF wavelength. provided as space-seperated list of comma-seperated pairs: e.g. 528,528', nargs="*")
	parser.add_argument('--otfdir', help='OTF directory', default=config.OTFdir, metavar='')
	parser.add_argument('--regfile', help='Registration File', default=config.regFile, metavar='')
	parser.add_argument('-r','--refchannel', help='reference channel for channel registration', default=config.refChannel, type=goodChannel)
	parser.add_argument('-x','--domax', help='perform max projection after registration', type=bool, default=config.doMax)
	parser.add_argument('-g','--doreg', help='perform channel registration', default=config.doReg)
	parser.add_argument('-w','--writefile', help='write score results to csv file', default=config.writeFile, action='store_true')
	parser.add_argument('-q','--quiet', help='suppress feedback during reconstructions', default=False, action='store_true')
	parser.add_argument('--version', action='version', version='%(prog)s 0.1')

	args = vars(parser.parse_args())

	forceOTFdict = {}
	for item in args['force']:
		forceOTFdict[int(item[0][0])]=int(item[0][1])

	bestOTFs, reconstructed, logFile, registeredFile, maxProj, scoreFile = makeBestReconstruction(args['inputFile'].name, 
		cropsize=args['crop'], oilMin=args['oilmin'], oilMax=args['oilmax'], maxAge=args['age'], maxNum=args['num'], 
		OTFdir=args['otfdir'], reconWaves=args['channels'], forceChannels=forceOTFdict, regFile=args['regfile'], 
		refChannel=args['refchannel'], doMax=int(args['domax']), doReg=int(args['doreg']), writeFile=args['writefile'], cleanup=True, verbose=True,)

	# THIS IS NOT JUST FOR READOUT
	# these lines  trigger the gui.py program set the specific OTF window
	# with the OTFS
	if bestOTFs:
		print ""
		print "Best OTFs:"
		print bestOTFs

	# THIS IS NOT JUST FOR READOUT
	# these lines  trigger the gui.py program to download the files
	# that are printed... 
	# the "updateStatusBar" in the "sendRemoteCommand" function looks for the 
	# 'Files Ready:' string in the response.
	print ""
	print "Files Ready:"
	if reconstructed: print "Reconstruction: %s" % reconstructed
	if logFile: print "LogFile: %s" % logFile
	if registeredFile: print "Registered: %s" % registeredFile
	if maxProj: print "maxProj: %s" % maxProj
	if scoreFile: print "ScoreCSV: %s" % scoreFile

	# this is important for the updateStatusBar function in gui.py
	print "Done"
