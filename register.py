from __init__ import matlabReg, pickRegFile, goodChannel
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

	matlabReg(args['inputFile'].name,args['regfile'],args['refchannel'],args['domax'])