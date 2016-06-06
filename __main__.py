import sys
import argparse
import config
from __init__ import makeBestReconstruction, goodChannel, cropCheck


parser = argparse.ArgumentParser(description='OTF matching program', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('inputFile', help='The file to process', type=file)
parser.add_argument('-a','--age', help='max age of OTF file in days', default=None, type=int)
parser.add_argument('-n','--num', help='max number of OTF files used', default=config.maxNum, type=int)
parser.add_argument('-l','--oilmin', help='min oil refractive index to search', default=config.oilMin, type=int, choices=config.valid['oilMin'], metavar='1510-1530')
parser.add_argument('-m','--oilmax', help='max oil refractive index to search', default=config.oilMax, type=int, choices=config.valid['oilMax'], metavar='1510-1530')
#parser.add_argument('-t','--time', help='number of timepoints to use', default=config.maxNum)
parser.add_argument('-p','--crop', help='ROI crop size to use for testing', default=config.cropsize, type=cropCheck)
parser.add_argument('-c','--channels', help='channels to process (sep by spaces)', default=None, nargs="*", type=goodChannel, metavar='CHAN')
#parser.add_argument('-f','--forceotf', help='force wavelength to use specified OTF wavelength. provided as space-seperated list of comma-seperated pairs: e.g. 528,528', nargs="*")
parser.add_argument('--otfdir', help='OTF directory', default=config.OTFdir, metavar='')
parser.add_argument('--regfile', help='Registration File', default=config.regFile, metavar='')
parser.add_argument('-r','--refchannel', help='reference channel for channel registration', default=config.refChannel, type=goodChannel)
parser.add_argument('-x','--domax', help='perform max projection after registration', type=bool, default=config.doMax)
parser.add_argument('-g','--doreg', help='perform channel registration', type=bool, default=config.doReg)
parser.add_argument('-w','--writefile', help='write score results to csv file', default=config.writeFile, action='store_true')
parser.add_argument('-q','--quiet', help='suppress feedback during reconstructions', default=False, action='store_true')
parser.add_argument('--version', action='version', version='%(prog)s 0.1')

args = vars(parser.parse_args())

makeBestReconstruction(args['inputFile'].name, cropsize=args['crop'], oilMin=args['oilmin'], oilMax=args['oilmax'], 
	maxAge=args['age'], maxNum=args['num'], OTFdir=args['otfdir'], reconWaves=args['channels'], regFile=args['regfile'], 
	refChannel=args['refchannel'], doMax=args['domax'], doReg=args['doreg'], writeFile=args['writefile'], cleanup=True, verbose=True,)

