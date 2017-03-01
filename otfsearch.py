import sys
import os
from datetime import datetime
import subprocess
import Mrc
import numpy as np
from scipy import stats
import config

# OTF handling functions

def makeOTFdict(dir,template=config.OTFtemplate,delim=config.OTFdelim,ext=config.OTFextension):
	allOTFs = [otf for otf in os.listdir(dir) if otf.endswith(ext)]
	O = [otf.split(ext)[0].split(delim) for otf in allOTFs]
	D=[dict(zip(template.split(delim),o)) for o in O]
	for n in range(len(D)):
		D[n]['path']=os.path.join(dir,allOTFs[n])
		D[n]['ctime']=os.stat(os.path.join(dir,allOTFs[n])).st_ctime
		D[n]['code']=getOTFcode(os.path.join(dir,allOTFs[n]))
	return D

def getMatchingOTFs(otfdict, wave, oilMin, oilMax, maxAge=None, maxNum=None):
	import time
	OTFlist=[O for O in otfdict if O['wavelength']==str(wave) and int(O['oil'])>=oilMin and int(O['oil'])<=oilMax]
	if maxAge is not None:
		oldestDate=time.time()-maxAge*24*60*60
		OTFlist=[O for O in OTFlist if O['ctime']>=oldestDate]
	OTFlist.sort(key=lambda x: x['ctime'], reverse=True)
	OTFlist=OTFlist[0:maxNum]
	return [O for O in sorted(OTFlist, key=lambda x: x['oil'])]

def getOTFcode(fname,template=config.OTFtemplate,delim=config.OTFdelim):
	splits = os.path.basename(fname).split('.otf')[0].split(delim)
	T=template.split(delim)
	code =  "w" + splits[T.index('wavelength')] + "d" + splits[T.index('date')] + "o" + splits[T.index('oil')] + splits[T.index('angle')] + "b" + splits[T.index('beadnum')]
	return code

def decodeOTFcode(code,template=config.OTFtemplate,delim=config.OTFdelim):
	pass


def goodChannel(string):
	import argparse
	goodChannels=config.valid['waves']
	value = int(string)
	if value not in goodChannels:
		msg = "%r is not one of the acceptable channel names: %s" % (string, ', '.join(str(x) for x in goodChannels))
		raise argparse.ArgumentTypeError(msg)
	return value

def cropCheck(string):
	import argparse
	value = int(string)
	if not (value != 0 and ((value & (value - 1)) == 0)):
		msg = "%r is not a power of two" % string
		raise argparse.ArgumentTypeError(msg)
	if value > 1024 or value < 32:
		msg = "Cropsize must be between 32 and 1024"
		raise argparse.ArgumentTypeError(msg)
	return value


# image file manipulation

def callPriism(command=None):
	# must figure out way to add this to path 
	if not os.environ.has_key('IVE_BASE') and os.path.exists(config.priismpath):
		P = os.environ['PATH'].split(":")
		P.insert(0,os.path.join(config.priismpath,'Darwin64','BIN'))
		os.environ['PATH'] = ":".join(P)
		dyld_fallback = [ os.path.join(config.priismpath,'Darwin64','LIB'),
			os.path.join(config.priismpath,'Darwin','LIB'),
			os.path.join(os.path.expanduser('~'),'lib'),
			'/usr/local/lib',
			'/lib',
			'/usr/lib']
		os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = ":".join(dyld_fallback)
		os.environ['IVE_WORKING_SET']='24000'
		os.environ['IVE_BASE']=config.priismpath
		os.environ['LIBQUICKTIME_PLUGIN_DIR']=os.path.join(config.priismpath,'libquicktime','Darwin','lib','libquicktime')
		os.environ['IVE_PGTHRESH']='1024'
		os.environ['IVE_SIZE']='27000'
		os.environ['IVE_WORKING_UNIT']='128'
		# IVE_ENV_SETUP={ test -r '/Users/talley/Dropbox/NIC/software/priism-4.4.1/Priism_setup.sh' && . '/Users/talley/Dropbox/NIC/software/priism-4.4.1/Priism_setup.sh' ; } || exit 1
	if command:
		try:
			subprocess.call(command)
		except EOFError:
			msg = "Priism may not be setup correctly...\n"
			msg += "Source the priism installation and try again"
			raise EOFError(msg)

def splitchannels(fname, waves=None):
	reader = Mrc.open(fname) 
	imWaves = [i for i in reader.hdr.wave if i != 0]
	if waves is None: waves = imWaves
	namesplit = os.path.splitext(fname)
	files = []
	for w in waves:
		if w in imWaves:
			print "Extracting channel %d..." % w
			out=namesplit[0]+"-"+str(w)+namesplit[1]
			callPriism(['CopyRegion', fname, out, "-w="+str(w)])
			files.append(out)
	return files

def mergeChannels(fileList, outFile=None):
	if outFile is None:
		namesplit = os.path.splitext(fileList[0])
		outFile=namesplit[0]+"_MRG"+namesplit[1]
	command = ['mergemrc', '-append_waves', outFile]
	command.extend(fileList)
	callPriism(command)
	return outFile

def maxprj(fname, outFile=None):
	if outFile is None:
		namesplit = os.path.splitext(fname)
		outFile=namesplit[0]+"_MAX"+namesplit[1]
	header = Mrc.open(fname).hdr
	numWaves = header.NumWaves
	numTimes = header.NumTimes
	imSize = header.Num
	numplanes = imSize[2]/(numTimes*numWaves)
	callPriism([ 'RunProj', fname, outFile, '-z_step=%d'%numplanes, '-z_group=%d'%numplanes, '-max_z' ])
	return outFile

def pseudoWF(fileIn, nangles=3, nphases=5, extract=None, outFile=None):
	"""Generate pseudo-widefield image from raw SIM stack
	by averaging phases together"""
	img = Mrc.bindFile(fileIn)
	nt = img.Mrc.hdr.NumTimes
	nw = img.Mrc.hdr.NumWaves
	nx = img.Mrc.hdr.Num[0]
	ny = img.Mrc.hdr.Num[1]
	nz = float(img.Mrc.hdr.Num[2]) / (nphases * nangles * nw * nt)
	# try to identify OTF files with nangles =1
	if not nz%1==0:
		print "Guessing nangles = 1 ..."
		nangles=1
		nz = img.Mrc.hdr.Num[2] / (nphases * nangles * nw * nt)
	imseq = img.Mrc.hdr.ImgSequence
		# 0 = ZTW
		# 1 = WZT
		# 2 = ZWT
	# reshape array to separate phases and angles from Z
	# and transpose to bring all ImgSeq types to type WZT
	if imseq==0:
		ordered = np.reshape(img,(nw,nt,nangles,nz,nphases,ny,nx))
		ordered = np.transpose(ordered,(1,2,3,4,0,5,6))
	elif imseq==1:
		ordered = np.reshape(img,(nt,nangles,nz,nphases,nw,ny,nx))
	elif imseq==2:
		ordered = np.reshape(img,(nt,nw,nangles,nz,nphases,ny,nx))
		ordered = np.transpose(ordered,(0,2,3,4,1,5,6))
	else:
		raise ValueError('Uknown image sequence in input file')
	# average phases
	imgavg = np.mean(ordered, 3)
	imgavg = imgavg.astype(img.dtype)
	# now order is (nt, na, nz, nw, ny, nx)

	if extract:
		if not extract in range(1,nangles+1):
			print('extracted angle must be between 1 and %d' % nangles)
			print('chosing angle 1')
			extract=1
		imgavg = imgavg[:,extract-1,:,:,:,:]
	else:
		#further average over all angles
		imgavg = np.mean(imgavg, 1, img.dtype)
	imgavg = np.squeeze(imgavg)
	if imgavg.ndim>4:
		raise ValueError('ERROR: pseudo widefield function cannot accept 5d images!') 
	hdr = Mrc.makeHdrArray()
	Mrc.initHdrArrayFrom(hdr, img.Mrc.hdr)
	hdr.ImgSequence=1

	if outFile is None:
		namesplit = os.path.splitext(fileIn)
		outFile=namesplit[0]+"_WF"+namesplit[1]
	if not (outFile is fileIn):
		try:
			Mrc.save(imgavg, outFile, hdr = hdr, ifExists='overwrite')
		except ValueError as e:
			print e
	#return outFile

def stackmath(fileIn, operator='max', axis='z', outFile=None):
	"""Generate pseudo-widefield image from raw SIM stack
	by averaging phases together"""
	img = Mrc.bindFile(fileIn)
	nt = img.Mrc.hdr.NumTimes
	nw = img.Mrc.hdr.NumWaves
	nx = img.Mrc.hdr.Num[0]
	ny = img.Mrc.hdr.Num[1]
	nz = img.Mrc.hdr.Num[2] / (nw * nt)
	imseq = img.Mrc.hdr.ImgSequence
		# 0 = ZTW
		# 1 = WZT
		# 2 = ZWT
	# reshape array to separate phases and angles from Z
	# and transpose to bring all ImgSeq types to type WZT
	if imseq==0:
		ordered = np.reshape(img,(nw,nt,nz,ny,nx))
		ordered = np.transpose(ordered,(1,2,0,3,4))
	elif imseq==1:
		ordered = np.reshape(img,(nt,nz,nw,ny,nx))
	elif imseq==2:
		ordered = np.reshape(img,(nt,nw,nz,ny,nx))
		ordered = np.transpose(ordered,(0,2,1,3,4))
	else:
		raise ValueError('Uknown image sequence in input file')

	axtoindex={'t': 0, 'z': 1, 'w': 2, 'c': 2}

	if operator=='max' or operator=='maximum':
		proj = np.max(ordered, axtoindex[axis])
	elif operator=='sum':
		proj = np.sum(ordered, axtoindex[axis])
	elif operator=='std' or operator=='stdev':
		proj = np.std(ordered, axtoindex[axis])
	elif operator=='med' or operator=='median':
		proj = np.std(ordered, axtoindex[axis])
	elif operator=='avg' or operator=='average':
		proj = np.average(ordered, axtoindex[axis])
	else:
		raise ValueError('operator must be: max, sum, std, med, or avg')

	proj = np.squeeze(proj)

	if proj.ndim>4:
		raise ValueError('Mrc.py cannot write 5D .dv images') 
	hdr = Mrc.makeHdrArray()
	Mrc.initHdrArrayFrom(hdr, img.Mrc.hdr)
	hdr.ImgSequence=1
	
	if outFile is None:
		namesplit = os.path.splitext(fileIn)
		outFile=namesplit[0]+"_"+operator.upper()+namesplit[1]

	if not (outFile is fileIn):
		try:
			Mrc.save(proj, outFile, hdr = hdr, ifExists='overwrite')
		except ValueError as e:
			print e



def croptime(fileIn, fileOut=None, start=1, end=1, step=1):
	if fileOut is None:
		namesplit = os.path.splitext(fileIn)
		fileOut=namesplit[0]+"_T"+str(end)+namesplit[1]
	callPriism(['CopyRegion', fileIn, fileOut, "-t="+str(start)+":"+str(end)+":"+str(step)])
	return fileOut

def crop(fileIn, cropsize, fileOut=None):
	reader = Mrc.open(fileIn)
	imSize = reader.hdr.Num
	reader = Mrc.open(fileIn)
	cropstartX=(imSize[0]/2)-(cropsize/2);
	cropendX=cropstartX+cropsize-1
	cropstartY=(imSize[1]/2)-(cropsize/2);
	cropendY=cropstartY+cropsize-1
	
	if fileOut is None:
		namesplit = os.path.splitext(fileIn)
		fileOut=namesplit[0]+"_cropped"+namesplit[1]


	callPriism(['CopyRegion', fileIn, fileOut, "-x="+str(cropstartX)+":"+str(cropendX), "-y="+str(cropstartY)+":"+str(cropendY)])
	return fileOut


# helpers 

def isRawSIMfile(fname):
	if os.path.splitext(fname)[1] != ".dv":
		return 0
	#exclude known processed files
	for q in ['_SIR','_PROC','_WF']:
		if q in os.path.basename(fname): return 0
	try:
		header = Mrc.open(fname).hdr
		numWaves = header.NumWaves
		numTimes = header.NumTimes
		imSize = header.Num
		numplanes = imSize[2]/(numTimes*numWaves)
		if numplanes%15:
			return 0
		return 1
	except Exception as e:
		print "Error reading header in: %s" % fname
		return 0

# this is a more stringent check for raw SIM files... but will fail
# if the log file doesn't exist
def logIsTypeSI(file):
	'''For a given file, look for a .log file with the same name
	if it exists, and the experiment type is "SI", then return 1
	'''
	logfile=os.path.splitext(file)[0] + '.log'
	if not os.path.exists(logfile):
		return 0
	for line in open(logfile, 'r'):
		if 'type:' in line:
			if line.split()[1]=='SI':
				return 1
			else:
				return 0
			break
		else:
			continue 

def isAlreadyProcessed(filename):
	'''simple check to see if a _PROC or _SIR file already exists for a given file
	'''
	if filename.endswith('.dv'):
		if os.path.exists(filename.replace('.dv','_PROC.dv')):
			return 1
		elif os.path.exists(filename.replace('.dv','_SIR.dv')):
			return 1
	return 0

def isaReconstruction(filename):
	'''simple check to see whether a file is a SIM reconstruction
	(probably more elegant ways)
	'''
	if filename.endswith('PROC.dv'):
		return 1
	elif filename.endswith('PROC_MAX.dv'):
		return 1
	return 0

def query_yes_no(question):
	"""Ask a yes/no question via raw_input() and return their answer.
	"question" is a string that is presented to the user.
	The "answer" return value is True for "yes" or False for "no".
	"""
	valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}

	while True:
		sys.stdout.write(question)
		choice = raw_input().lower()
		if choice in valid:
			return valid[choice]
		else:
			sys.stdout.write("Please respond with 'yes' or 'no' "
							 "(or 'y' or 'n').\n")


# reconstruction
def reconstruct(inFile, otfFile, outFile=None, configFile=None, 
				wiener=None, background=None, configDir=None):
	wave = Mrc.open(inFile).hdr.wave[0]

	if outFile is None:
		namesplit = os.path.splitext(inFile)
		outFile=namesplit[0]+"_PROC"+namesplit[1]

	if configFile is None:
		if configDir is not None:
			configFile = os.path.join(configDir,str(wave)+'config')
		else:
			configFile = os.path.join(config.SIconfigDir,str(wave)+'config')

	if not os.path.exists(configFile):
		raise OSError(2, 'Cannot find SIrecon config file: %s' % configFile)

	commandArray=[config.reconApp,inFile,outFile,otfFile,'-c',configFile]
	if wiener:
		commandArray.extend(['--wiener',str(wiener)])
	if background:
		commandArray.extend(['--background',str(background)])

	
	process = subprocess.Popen(commandArray, stdout=subprocess.PIPE)
	output = process.communicate()[0]
	if 'CUFFT failed to allocate GPU or CPU memory' in output:
		raise MemoryError('CUFFT failed to allocate GPU or CPU memory: File size too large??')
	elif 'done' in output.split('\n')[-2]:
		return output


def reconstructMulti(inFile, OTFdict={}, reconWaves=None, outFile=None, wiener=None,
					background=None,configDir=None, writeLog=True, logFile=None):
	"""Splits multi-channel file into individual channels
	then reconstructs each channel and merges the results
	provide OTFdict as { '528' : '/path/to/528/otf', '608' : 'path/to/608/otf'}
	"""

	if outFile is None:
		namesplit = os.path.splitext(inFile)
		outFile=namesplit[0]+"_PROC"+namesplit[1]


	header = Mrc.open(inFile).hdr
	numWaves = header.NumWaves
	#waves = [i for i in header.wave if i != 0]

	# split multi-channel files into component parts
	if numWaves > 1:
		splitfiles = splitchannels(inFile, reconWaves)
	else:
		splitfiles = [inFile]

	filesToMerge = []
	reconLogs=[]
	for file in splitfiles:
		wave = Mrc.open(file).hdr.wave[0]
		print "Reconstructing channel %d ..." % wave

		if OTFdict.has_key(str(wave)):
			otf = OTFdict[str(wave)]
		elif os.path.exists(os.path.join(config.defaultOTFdir,str(wave)+".otf")):
			otf = os.path.join(config.defaultOTFdir,str(wave)+'.otf')
		else:
			print "cannot find OTF for %s, channel %d... skipping" % (file,wave)
			continue

		namesplit = os.path.splitext(file)
		procFile=namesplit[0]+"_PROC"+namesplit[1]
		filesToMerge.append(procFile)
		try:
			reconLogs.append({ 	'log'  : reconstruct(file, otf, procFile, wiener=wiener, background=background, configDir=configDir), 
								'wave' : wave,
								'otf'  : otf,
								'file' : file,
								'procFile' : procFile
							})
		except Exception as e:
			print "Cannot reconstruct file %s due to error %s" % (inFile,e)
			#cleanup files
			for f in splitfiles: 
				if not f == inFile: os.remove(f) 
			for f in filesToMerge: os.remove(f)
			return 0

		

	if writeLog:
		if not logFile: 
			namesplit=os.path.splitext(outFile)
			logFile=namesplit[0]+"_LOG.txt"
		with open(logFile, 'w') as the_file:
			the_file.write("INPUT FILE: %s \n" % inFile)
			the_file.write("\n")
			for D in reconLogs:
				the_file.write("#"*80+'\n')
				the_file.write("\n")
				the_file.write("WAVELENGTH: %d \n" % D['wave'])
				the_file.write("FILE: %s \n" % D['file'])
				the_file.write("OTF: %s \n" % D['otf'])
				indat = Mrc.bindFile(D['procFile'])
				imRIH = getRIH(indat)
				the_file.write("RECONSTRUCTION SCORE (MMR): %0.2f \n" % imRIH)
				the_file.write("\n")
				the_file.write("RECONSTRUCTION LOG: \n")
				the_file.write(D['log'])
				the_file.write("\n")

	if len(filesToMerge) > 1:
		print "Merging multi-channel reconstructions..."
		mergeChannels(filesToMerge, outFile)
		#cleanup files
		for f in splitfiles: os.remove(f)
		for f in filesToMerge: os.remove(f)
	else:
		outFile=filesToMerge[0]

	return (outFile,logFile)



# SCORING FUNCTIONS 

def calcPosNegRatio(pc, bg, histMin, histMax, hist, nPixels):
	#find hist step (bin size)
	histStep = (histMax - histMin) / len(hist)

	# for negative histogram extreme, add until percentile reached
	negPc = 0.0
	negTotal = 0.0
	bin = 0
	binValue = float(histMin)

	while (negPc < pc and binValue <= bg and bin < len(hist)):
		negPc += float(hist[bin]) / nPixels
		negTotal += (binValue - bg) * hist[bin]  # make mode 0
		bin += 1
		binValue += histStep
	pc = negPc

	# for positive histogram extreme, add until percentile reached
	posPc = 0.0
	posTotal = 0.0
	bin = len(hist) - 1
	binValue = float(histMax)
	while (posPc < pc and bin >=0):
		posPc += float(hist[bin]) / nPixels
		posTotal += (binValue - bg) * hist[bin]  # make mode 0
		bin -= 1
		binValue -= histStep
	#uncomment to check actual histogram bins used (pc and pixels)
	#nNegPixels = int(negPc * nPixels)
	#nPosPixels = int(posPc * nPixels)
	#since negTotal may or may not be negative...
	posNegRatio = float(abs(posTotal / negTotal))
	return posNegRatio

def getRIH1(im):
	percentile = 0.0001  	# use 0-100% of histogram extrema
	minPixels = 100.0		# minimum pixels at histogram extrema to use
	#modeTol = 0.25  		# mode should be within modeTol*stdev of 0

	#nNegPixels = 0
	#nPosPixels = 0

	flat = np.ndarray.flatten(im)
	histMin = flat.min()
	histMax = flat.max()
	hist = np.histogram(flat,bins=1024)
	background = hist[1][np.argmax(hist[0])] # find the rough mode

	if (histMin == 0):
		print "Image has no neg values!"
	if histMin <= background:
		# ensure we consider a bare minimum of pixels
		totalPixels = len(flat)
		if totalPixels * percentile / 100 < minPixels:
			percentile = minPixels * 100 / totalPixels
		# caluclate +ve / -ve ratio if histogram has negatives
		posNegRatio = calcPosNegRatio(percentile / 100, background, histMin, histMax, hist[0], totalPixels)
		return posNegRatio
	else:
		print "! histogram minimum above background. unable to calculate +ve/-ve intensity ratio"
		return 0.0

def getRIH(im):
	if im.Mrc.hdr.NumWaves > 1:
		scores = [];
		for i in im:
			scores.append((getRIH1(i)))
	else:
		scores = getRIH1(im)
	return scores

def getSAM(im):
	from skimage import filters

	#hist=np.histogram(im,bins=1024);
	#stackMode = hist[1][np.argmax(hist[0])]
	#threshold = filters.threshold_otsu(im)
	sliceMinima = [np.min(i) for i in im]
	sliceMeans = [np.average(plane[np.where(plane > filters.threshold_otsu(plane))]) for plane in im]
	avgmean = np.nanmean(sliceMeans)
	minStd = np.std(sliceMinima)
	return minStd/avgmean


def CIP(im):
	phases = 5 # phases
	nz = im.shape[-3] # shape gives (c, t, z, y, x)
	angles = 3 #angles
	nz = nz / (phases * angles)  # take phase & angle out of Z
	npz = nz * phases
	zwin = 9

	#### TIV ########
	sliceMeans = list(reversed(np.mean(im.reshape(im.shape[-3],-1), axis=1)[::-1]))

	centralWindow=[]

	# TIV
	for a in range(angles):
		zFirst = (a*npz) + npz/2 -(zwin*phases/2)
		zLast = zFirst+zwin*phases
		centralWindow.append(sliceMeans[zFirst:zLast])

	intensMin = np.min(centralWindow)
	intensMax = np.max(centralWindow)

	TIV = round(100 * (intensMax - intensMin) / intensMax,2)


	# per-channel intensity decay
	xSlice = range(len(sliceMeans))

	# estimate % decay over each angle via simple straight line fit
	angleDecays = []
	angleMeans = []
	for a in range(angles):
		nzp = nz * phases
		xa = xSlice[a*nzp:(a+1)*nzp]
		ya = sliceMeans[a*nzp:(a+1)*nzp]
		angleMeans.append(np.mean(ya))
		fitParams = stats.linregress(xa,ya)
		angleDecays.append((fitParams[0] * nzp * -100.0) / fitParams[1])
	channelDecay = np.mean(angleDecays)
	# negative bleaching does not make sense, so report 0
	if channelDecay < 0: channelDecay = 0
	channelDecay = round(channelDecay,2)


	angleMax = np.max(angleMeans)
	angleMin = np.min(angleMeans)
	largestDiff = abs(angleMax - angleMin)
	angleDiffs = round(100 * largestDiff / angleMax,2)

	return (TIV, channelDecay, angleDiffs)


def printFormattedScores(scoreList):
	'''
	prints a nicely formatted version of the output from scoreOTFs
	'''
	print "{:<8} {:<10} {:^23} {:<8} {:<8} {:<7}".format("Channel", "Bleaching", "OTF", "OTFoil", "Modamp", "RIH")
	for i in scoreList: print "{:<8} {:<10} {:<23} {:<8} {:<05.3}    {:<04.3}".format(i['wavelength'], i['channelDecay'], i['OTFcode'], i['OTFoil'], np.average(i['modamp2']), i['RIH'])


def scoreOTFs(inputFile, cropsize=256, OTFdir=config.OTFdir, reconWaves=None, forceChannels=None, oilMin=1510, oilMax=1524, maxAge=None, maxNum=None, verbose=True, cleanup=True):
	'''
	Takes an input file and reconstructs it by all of the OTFs that match certain criteria

	'''

	import shutil

	# check if it exists
	if not os.path.isfile(inputFile):
		sys.exit(inputFile + " not found... quitting")

	# create temp folder for reconstructions
	tmpDir = os.path.splitext(inputFile)[0]+"_tmp"
	if os.path.exists(tmpDir):
		shutil.rmtree(tmpDir)
	os.makedirs(tmpDir)
	
	# create symlink of original file in tmp
	fname=os.path.join(tmpDir,os.path.basename(inputFile))
	os.symlink(inputFile, fname)


	# get file info
	header = Mrc.open(fname).hdr
	numWaves = header.NumWaves
	waves = [i for i in header.wave if i != 0]
	numTimes = header.NumTimes
	imSize = header.Num

	# cut timelapse to the first timepoint
	if numTimes>1:
		print("Timelapse detected, clipping to the first timepoint")
		fname=croptime(fname)

	# crop to a central region to speed things up
	if imSize[0]>cropsize or imSize[1]>cropsize:
		print "Cropping to the center %d pixels..." % cropsize
		fname=crop(fname, cropsize)

	if reconWaves is not None:
		if isinstance(reconWaves,list):
			for W in reconWaves:
				if not W in waves:
					reconWaves.remove(W)
					if verbose: print "channel %d does not exist in the input file..." % W
		elif isinstance(reconWaves,int):
			reconWaves = [reconWaves]
		else:
			if verbose: 
				print "Channel input format not recognized: %s" % reconWaves
				print "Channels must be integer or list of integers.  Quitting..."
				sys.exit(1)
	else:
		# reconstruct all channels
		reconWaves = waves

	# split multi-channel files into component parts
	if numWaves > 1:
		splitfiles = splitchannels(fname, reconWaves)
	else:
		splitfiles = [fname]

	# generate searchable dict of OTFs in a directory
	otfDict = makeOTFdict(OTFdir)

	allScores=[]
	# reconstruct each channel file by all matching OTFs
	for file in splitfiles:
		namesplit = os.path.splitext(file)
		
		imChannel = Mrc.open(file).hdr.wave[0]
		
		if verbose:
			print "%s - Channel: %s" % (os.path.basename(file), imChannel)

		# raw data/bleaching test
		indat=Mrc.bindFile(file)
		im=np.asarray(indat)
		TIV,channelDecay,angleDiffs = CIP(im)

		if verbose:
			print
			print "Bleaching rate: %.2f%%" % channelDecay
			print "Angle Illumination variance: %.2f%%" % angleDiffs
			print "Total intensity variation: %.2f%%" % TIV
			if channelDecay > 30:
				print "WARNING: Image: %s, Channel: %s, Bleaching: %.2f%%" % (os.path.basename(file),imChannel,channelDecay)
			if angleDiffs > 20:
				print "WARNING: Image: %s, Channel: %s, AngleDiff: %.2f%%" % (os.path.basename(file),imChannel,angleDiffs)

		fileDict={  "input" : inputFile,
					"input-ctime" : datetime.fromtimestamp(os.path.getctime(inputFile)),
					"TIV" : TIV,
					"channelDecay" : channelDecay,						
					"angleDiffs" : angleDiffs,
					"imChannel" : imChannel
		}

		# this line allows the user to match certain image channels to certain OTF channels
		if forceChannels:
			otfWave = forceChannels[imChannel] if forceChannels.has_key(imChannel) else imChannel
		else:
			otfWave = imChannel

		OTFlist = getMatchingOTFs(otfDict,otfWave,oilMin,oilMax, maxAge=maxAge, maxNum=maxNum)

		for otf in OTFlist:

			# this is where we parse the reconstruction log and mine for import data
			procFile=namesplit[0] + "_" + otf['code'] + "_PROC" + namesplit[1]
			reconLog = reconstruct(file, otf['path'], procFile)
			combinedModamps = [float(line.split('amp=')[1].split(',')[0]) for line 
							 in reconLog.split('\n') if 'Combined modamp' in line]
			correlationCoeffs = [float(line.split(": ")[1]) for line in reconLog.split('\n') 
								if 'Correlation coefficient' in line]
			spacings = [float(line.split(" ")[0]) for line in reconLog.split('spacing=')[1:]]
			angles = [float(line.split(",")[0]) for line in reconLog.split('Optimum k0 angle=')[1:]]
			lengths = [float(line.split(",")[0]) for line in reconLog.split('length=')[1:]]
			fitDeltas = [float(line.split(" ")[0]) for line in reconLog.split('best fit for k0 is ')[1:]]
			warnings = [line for line in reconLog.split('\n') if 'WARNING' in line]
			indat = Mrc.bindFile(procFile)
			imRIH = getRIH(indat)
			imSAM = getSAM(indat)
			
			scoreDict={ "OTFcode" : otf['code'],
						"OTFoil"  : otf['oil'],
						"OTFangle": otf['angle'][1:],
						"OTFbead" : otf['beadnum'],
						"OTFdate" : otf['date'],
						"OTFwave" : otf['wavelength'],
						"OTFpath" : otf['path'],
						"RIH" 	  : round(imRIH,3),
						"SAM" 	  : round(imSAM,3),
						"warnings": warnings,
						"correl2" : correlationCoeffs[0:6:2],
						"correl1" : correlationCoeffs[1:6:2],
						"avgcorrel" : np.average(correlationCoeffs),
						"avgcorrel1" : np.average(correlationCoeffs[1:6:2]),
						"avgcorrel2" : np.average(correlationCoeffs[0:6:2]),
						"modamp2" : combinedModamps[0:6:2],
						"modamp1" : combinedModamps[1:6:2],
						"avgmodamp" : np.average(combinedModamps),
						"avgmodamp1" : np.average(combinedModamps[1:6:2]),
						"avgmodamp2" : np.average(combinedModamps[0:6:2]),
						"wiener"  : reconLog.split('wiener=')[1][:5],
						"spacings" : spacings,
						"angles" : angles,
						"lengths" : lengths,
						"fitDeltas" : fitDeltas
			}
			scoreDict['score'] = scoreDict['RIH'] * scoreDict['avgmodamp2']

			scoreDict.update(fileDict)
			allScores.append(scoreDict)
			if verbose: print "%s: %0.3f %.2f" % (otf['code'], np.average(combinedModamps[0:6:2]), imRIH)
		if verbose: print ""			

	if cleanup: shutil.rmtree(tmpDir)
	return allScores


def getBestOTFs(scoreDict,channels=None, report=10, verbose=True):
	results={}
	if channels is None:
		channels = list(set([s['imChannel'] for s in scoreDict]))
	for c in channels:
		sortedList = sorted([s for s in scoreDict if s['imChannel']==c], key=lambda x: x['score'], reverse=True)
		results[str(c)] = sortedList[0]['OTFpath']
		if verbose: 
			print "Channel %s:" % c
			q=[(s['OTFcode'], s['score'], s['RIH'], s['avgmodamp2']) for s in sortedList][:report]
			print "{:<23} {:<6} {:<5} {:<7}".format('OTFcode','Score','RIH','modamp')
			for i in q:
				print "{:<23} {:<05.3}  {:<04.3}  {:<05.3}".format(*i)
	return results



def matlabReg(fname,regFile,refChannel,doMax,form='dv'):
	maxbool = 'true' if doMax else 'false'
	matlabString = "%s('%s','%s', %d,'DoMax', %s, 'format', '%s');exit" % (config.MatlabRegScript,fname,regFile,refChannel,maxbool,form)
	subprocess.call(['matlab', '-nosplash', '-nodesktop', '-nodisplay', '-r', matlabString])
	registeredFile = os.path.splitext(fname)[0]+"-REGto"+str(refChannel)+"."+form
	if doMax: 
		maxProj = os.path.splitext(fname)[0]+"-REGto"+str(refChannel)+"-MAX."+form
	else:
		maxProj = None
	return (registeredFile, maxProj)


def pickRegFile(fname,directory,filestring=None):
	filelist = sorted(os.listdir(directory), key=lambda x: x.split("_")[1], reverse=True)
	reader = Mrc.open(fname) 
	imWaves = [i for i in reader.hdr.wave if i != 0]
	for f in filelist:
		fileWaves = [int(w) for w in f.split('waves')[1].split('_')[0].split('-')]
		if set(imWaves).issubset(set(fileWaves)):
			if filestring:
				if filestring in f:
					return f
			else:
				return f

	# should add another bit to check whether the .mat file has that channel as
	# a reference channel... 
	# if the regile has "refs" in the filename, it means that not all wavelengths
	# are referenced to all other wavelengths (otherwise, that can be assumed)
	return 0


def makeBestReconstruction(fname, cropsize=256, oilMin=1510, oilMax=1524, maxAge=config.maxAge, wiener=None,
							maxNum=config.maxNum, writeCSV=config.writeCSV, appendtomaster=True, OTFdir=config.OTFdir, 
							reconWaves=None, forceChannels=None, regFile=None, regdir=config.regFileDir,
							refChannel=config.refChannel, doMax=None, doReg=None, cleanup=True, verbose=True):
	# check if it appears to be a raw SIM file
	if not isRawSIMfile(fname):
		if not query_yes_no("File doesn't appear to be a raw SIM file... continue?"):
			sys.exit("Quitting...")

	allScores = scoreOTFs(fname, cropsize=cropsize, OTFdir=config.OTFdir, reconWaves=reconWaves, 
							forceChannels=forceChannels, oilMin=oilMin, oilMax=oilMax, maxAge=maxAge, 
							maxNum=maxNum, verbose=verbose, cleanup=cleanup)
	bestOTFs  = getBestOTFs(allScores, verbose=verbose)

	if verbose: print "reconstructing final file..."
	reconstructed,logFile = reconstructMulti(fname, OTFdict=bestOTFs, reconWaves=reconWaves, wiener=wiener)

	numWaves = Mrc.open(reconstructed).hdr.NumWaves

	registeredFile = None
	maxProj = None
	if doReg and numWaves>1: # perform channel registration
		if verbose: print "perfoming channel registration in matlab..."
		if not regFile:
			regFile = pickRegFile(fname,regdir)
		registeredFile, maxProj = matlabReg(reconstructed,regFile,refChannel,doMax) # will be a list
	elif doMax:
		maxProj = maxprj(reconstructed)


	scoreFile=None
	if writeCSV: # write the file to csv
		import pandas as pd
		scoreDF = pd.DataFrame(allScores)
		scoreFile = os.path.splitext(fname)[0]+"_scores.csv"
		scoreDF.to_csv(scoreFile)
		if appendtomaster: # write the file to master csv file with all the scores
			if not os.path.isfile(config.masterScoreCSV):
				scoreDF.to_csv(config.masterScoreCSV, mode='a', index=False)
			elif len(scoreDF.columns) != len(pd.read_csv(config.masterScoreCSV, nrows=1).columns):
				raise Exception("Columns do not match!! new scores have " + str(len(scoreDF.columns)) + " columns. CSV file has " + str(len(pd.read_csv(config.masterScoreCSV, nrows=1).columns)) + " columns.")
			elif not (scoreDF.columns == pd.read_csv(config.masterScoreCSV, nrows=1).columns).all():
				raise Exception("Columns and column order of dataframe and csv file do not match!!")
			else:
				scoreDF.to_csv(config.masterScoreCSV, mode='a', index=False, header=False)
				cleanupDupes(config.masterScoreCSV)


	return (bestOTFs, reconstructed, logFile, registeredFile, maxProj, scoreFile)

def cleanupDupes(csvFile=config.masterScoreCSV):
	import pandas as pd
	df = pd.DataFrame.from_csv(csvFile)
	df.drop_duplicates().to_csv(csvFile)



def batchRecon(directory, mode, **kwargs):

	for root, subdirs, files in os.walk(directory):
		for file in files:
			fullpath=os.path.join(root,file)
			if isRawSIMfile(fullpath):
				if mode=='optimal':
					print "Doing optimal reconstruction on file: %s" % file
					try:
						makeBestReconstruction(fullpath, **kwargs)
					except Exception as e:
						print 'Skipping file %s due to error %s' % (fullpath,e)
				elif mode=='single':
					print "Doing single reconstruction on file: %s" % file
					try:
						reconstructMulti(fullpath, **kwargs)
					except Exception as e:
						print 'Skipping file %s due to error %s' % (fullpath,e)
				else:
					raise ValueError('Mode %s in batchRecon function was not understood' % mode)
					return 0
	return 1








