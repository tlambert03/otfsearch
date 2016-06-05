import sys
import os
import argparse
import config
import math
from __init__ import reconstructMulti, goodChannel, cropCheck, cropTime, isRawSIMfile, query_yes_no
import Mrc


def otfAssignment(string):
	if "=" in string and len(string.split('='))==2:
		k,v = string.split('=')
		if goodChannel(k):
			if not v.endswith('.otf'):
				msg = "%r is not an OTF file ending in '.otf'" % v
				raise argparse.ArgumentTypeError(msg)
			else:
				return {k:v}
	msg = "OTF assignment %r is not of the form <WAVE>=<FILE>" % string
	raise argparse.ArgumentTypeError(msg)

parser = argparse.ArgumentParser(description='OTF matching program', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('inputFile', help='The file to process', type=file)
parser.add_argument('--outputFile', help='Optional name of output file to process', default=None, metavar='FILE')
parser.add_argument('-o', '--otf', help='OTF assignment in the form: <WAVE>=<FILE>', 
				metavar='<WAVE>=<FILE>', nargs=1, action='append',type=otfAssignment, default=[])
parser.add_argument('-c','--channels', help='channels to process (sep by spaces)', 
				default=None, nargs="*", type=goodChannel, metavar='WAVE')
parser.add_argument('--configDir', help='Director with config files', default=config.SIconfigDir, metavar='DIR')
parser.add_argument('-t','--time', help='Cut to first N timepoints', default=None, type=int)
#parser.add_argument('-p','--crop', help='ROI crop size to use for testing', default=config.cropsize, type=cropCheck)
parser.add_argument('--regfile', help='Registration File', default=config.regFile, metavar='FILE')
parser.add_argument('-r','--refchannel', help='reference channel for channel registration', 
				default=config.refChannel, type=goodChannel)
parser.add_argument('-x','--domax', help='perform max projection after registration', default=False, action='store_true')
parser.add_argument('-g','--doreg', help='perform channel registration', default=False, action='store_true')
parser.add_argument('-q','--quiet', help='suppress feedback during reconstructions', default=False, action='store_true')
parser.add_argument('--version', action='version', version='%(prog)s 0.1')

args = vars(parser.parse_args())

otfDict = {}
for item in args['otf']:
	otfDict.update(item[0])
for k,v, in otfDict.items():
	otfDict[k]=os.path.join(config.OTFdir,v)

fname = args['inputFile'].name
header = Mrc.open(fname).hdr
numWaves = header.NumWaves
waves = [i for i in header.wave if i != 0]
numTimes = header.NumTimes

if not isRawSIMfile(fname):
	if not query_yes_no("File doesn't appear to be a raw SIM file... continue?"):
		sys.exit("Quitting...")

if args['time'] and args['time']>0 and numTimes > 1:
	inputFile = cropTime(fname, end=args['time'])
	timecropped = 1
else:
	inputFile = fname
	timecropped = 0

if args['channels']:
	for c in args['channels']:
		if c not in waves:
			print "Channel %d requested, but not in file... skipping" % c
	reconWaves=sorted([c for c in args['channels'] if c in waves])
else:
	reconWaves= waves

reconstructMulti(inputFile, OTFdict=otfDict, reconWaves=args['channels'], outFile=args['outputFile'], configDir=args['configDir'])

# cleanup the file that was made
if timecropped:
	os.remove(inputFile)