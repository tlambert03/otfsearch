from otfsearch import matlabReg, pickRegFile, goodChannel
import config

if __name__ == '__main__':

	import argparse
	parser = argparse.ArgumentParser(description='Apply channel registration to multi-channel file', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument('inputFile', help='The file to process', type=file)
	parser.add_argument('-f','--regfile', help='Registration File', default=None, metavar='FILE')
	parser.add_argument('-c','--refchannel', help='reference channel for channel registration', default=config.refChannel, type=goodChannel, metavar='WAVE')
	parser.add_argument('-x','--domax', help='perform max projection after registration', type=bool, default=False, metavar='T/F')
	args = vars(parser.parse_args())

	if not args['regfile']:
		pickRegFile(args['inputFile'],config.regFileDir,filestring=None)

	registeredFile, maxProj = matlabReg(args['inputFile'].name,args['regfile'],args['refchannel'],args['domax'])

	# THIS IS NOT JUST FOR READOUT
	# these lines  trigger the gui.py program to download the files
	# that are printed... 
	# the "updateStatusBar" in the "sendRemoteCommand" function looks for the 
	# 'Files Ready:' string in the response.
	print ""
	print "Files Ready:"
	if registeredFile: print "Registered: %s" % registeredFile
	if maxProj: print "maxProj: %s" % maxProj

	# this is important for the updateStatusBar function in gui.py
	print "Done"
