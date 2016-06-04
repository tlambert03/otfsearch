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


# image file manipulation

def splitChannels(fname, waves=None):
	reader = Mrc.open(fname) 
	channels = [i for i in reader.hdr.wave if i != 0]
	if waves is None: waves = channels
	namesplit = os.path.splitext(fname)
	files = []
	for w in waves:
		if w in channels:
			out=namesplit[0]+"-"+str(w)+namesplit[1]
			subprocess.call(['CopyRegion', fname, out, "-w="+str(w)])
			files.append(out)
	return files

def mergeChannels(fileList, outFile=None):
	if outFile is None:
		namesplit = os.path.splitext(fileList[0])
		outFile=namesplit[0]+"_MRG"+namesplit[1]
	command = ['mergemrc', '-append_waves', outFile]
	command.extend(fileList)
	subprocess.call(command)
	return outFile


def cropTime(fileIn, fileOut=None, start=1, end=1, step=1):
	if fileOut is None:
		namesplit = os.path.splitext(fileIn)
		fileOut=namesplit[0]+"_T"+str(end)+namesplit[1]
	subprocess.call(['CopyRegion', fileIn, fileOut, "-t="+str(start)+":"+str(end)+":"+str(step)])
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
	
	subprocess.call(['CopyRegion', fileIn, fileOut, "-x="+str(cropstartX)+":"+str(cropendX), "-y="+str(cropstartY)+":"+str(cropendY)])
	return fileOut


# helpers 

def isRawSIMfile(fname):
	if os.path.splitext(fname)[1] != ".dv":
		print "not a raw SIM file"
		return 0
	for q in ['SIR','PROC']:
		if q in fname: return 0
	reader = Mrc.open(fname)
	if reader.hdr.Num[2]%15:
		print "not a raw SIM file"
		return 0
	return 1

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
def reconstruct(inFile, otfFile, outFile=None, configFile=None):
	wave = Mrc.open(inFile).hdr.wave[0]

	if outFile is None:
		namesplit = os.path.splitext(inFile)
		outFile=namesplit[0]+"_PROC"+str(end)+namesplit[1]

	if configFile is None:
		configFile = os.path.join(config.SIconfigDir,str(wave)+'config')

	commandArray=[config.reconApp,inFile,outFile,otfFile,'-c',configFile]
	process = subprocess.Popen(commandArray, stdout=subprocess.PIPE)
	output = process.communicate()[0]
	return output


def reconstructMulti(inFile, OTFdict={}, reconWaves=None, outFile=None, configFile=None):
	"""Splits multi-channel file into individual channels
	then reconstructs each channel and merges the results
	provide OTFdict as { '528' : '/path/to/528/otf', '608' : 'path/to/608/otf'}
	"""
	header = Mrc.open(inFile).hdr
	numWaves = header.NumWaves
	waves = [i for i in header.wave if i != 0]

	# split multi-channel files into component parts
	if numWaves > 1:
		splitfiles = splitChannels(inFile, reconWaves)
	else:
		splitfiles = [inFile]

	filesToMerge = []
	for file in splitfiles:
		wave = Mrc.open(file).hdr.wave[0]

		if OTFdict.has_key(str(wave)):
			otf = OTFdict[str(wave)]
		elif os.path.exists(os.path.join(config.defaultOTFdir,str(wave)+".otf")):
			otf = os.path.join(config.defaultOTFdir,str(wave)+'.otf')
		else:
			print "cannot find OTF for %s, channel %d... skipping" % (file,wave)
			continue

		namesplit = os.path.splitext(file)
		procFile=namesplit[0]+"_PROC"+namesplit[1]
		reconLog = reconstruct(file, otf, procFile)
		filesToMerge.append(procFile)

	if outFile is None:
		namesplit = os.path.splitext(inFile)
		outFile=namesplit[0]+"_PROC"+namesplit[1]

	mergeChannels(filesToMerge, outFile)

	#cleanup files
	for f in splitfiles: os.remove(f)
	for f in filesToMerge: os.remove(f)

	return outFile



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
	nNegPixels = int(negPc * nPixels)
	nPosPixels = int(posPc * nPixels)
	#since negTotal may or may not be negative...
	posNegRatio = float(abs(posTotal / negTotal))
	return posNegRatio

def getRIH(im):
	percentile = 0.0001  	# use 0-100% of histogram extrema
	minPixels = 100.0		# minimum pixels at histogram extrema to use
	modeTol = 0.25  		# mode should be within modeTol*stdev of 0

	nNegPixels = 0
	nPosPixels = 0

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


def getSAM(im):
	from skimage import filters

	hist=np.histogram(im,bins=1024);
	stackMode = hist[1][np.argmax(hist[0])]
	threshold = filters.threshold_otsu(im)
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
	print "{:<8} {:<10} {:^23} {:<8} {:<8} {:<7}".format("Channel", "Bleaching", "OTF", "OTFoil", "Modamp", "RIH")
	for i in scoreList: print "{:<8} {:<10} {:<23} {:<8} {:<05.3}    {:<04.3}".format(i['wavelength'], i['channelDecay'], i['OTFcode'], i['OTFoil'], np.average(i['modamp2']), i['RIH'])


def scoreOTFs(inputFile, cropsize=256, OTFdir=config.OTFdir, reconWaves=None, oilMin=1510, oilMax=1524, maxAge=None, maxNum=None, verbose=True, cleanup=True):
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
	numPlanes = imSize[2]/(numTimes*numWaves) # does this work?

	# cut timelapse to the firs timepoint
	if numTimes>1:
		print("Timelapse detected, clipping to the first timepoint")
		fname=cropTime(fname)

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
		splitfiles = splitChannels(fname, reconWaves)
	else:
		splitfiles = [fname]

	# generate searchable dict of OTFs in a directory
	otfDict = makeOTFdict(OTFdir)

	allScores=[]
	# reconstruct each channel file by all matching OTFs
	for file in splitfiles:
		namesplit = os.path.splitext(file)
		
		wave = Mrc.open(file).hdr.wave[0]
		if verbose: print "%s - Channel: %s" % (os.path.basename(file), wave)

		# raw data/bleaching test
		indat=Mrc.bindFile(file)
		im=np.asarray(indat)
		TIV,channelDecay,angleDiffs = CIP(im)

		fileDict={  "input" : os.path.basename(inputFile),
					"date" : datetime.fromtimestamp(os.path.getctime(inputFile)),
					"TIV" : TIV,
					"channelDecay" : channelDecay,						
					"angleDiffs" : angleDiffs,
					"wavelength" : wave
		}

		OTFlist = getMatchingOTFs(otfDict,wave,oilMin,oilMax, maxAge=maxAge, maxNum=maxNum)

		for otf in OTFlist:
			procFile=namesplit[0] + "_" + otf['code'] + "_PROC" + namesplit[1]
			reconLog = reconstruct(file, otf['path'], procFile)
			combinedModamps = [float(line.split('amp=')[1].split(',')[0]) for line 
							 in reconLog.split('\n') if 'Combined modamp' in line]
			correlationCoeffs = [float(line.split(": ")[1]) for line in reconLog.split('\n') 
								if 'Correlation coefficient' in line]
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
						"wiener"  : reconLog.split('wiener=')[1][:5]
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
		channels = list(set([s['wavelength'] for s in scoreDict]))
	for c in channels:
		sortedList = sorted([s for s in scoreDict if s['wavelength']==c], key=lambda x: x['score'], reverse=True)
		results[str(c)] = sortedList[0]['OTFpath']
		if verbose: 
			print "Channel %s:" % c
			q=[(s['OTFcode'], s['score'], s['RIH'], s['avgmodamp2']) for s in sortedList][:report]
			print "{:<23} {:<6} {:<5} {:<7}".format('OTFcode','Score','RIH','modamp')
			for i in q:
				print "{:<23} {:<05.3}  {:<04.3}  {:<05.3}".format(*i)
	return results


def matlabReg(fname,regFile,refChannel,doMax):
	maxbool = 'true' if doMax else 'false'
	matlabString = "%s('%s','%s', %d,'DoMax', %s);exit" % (config.MatlabRegScript,fname,regFile,refChannel,maxbool)
	subprocess.call(['matlab', '-nosplash', '-nodesktop', '-nodisplay', '-r', matlabString])


def makeBestReconstruction(fname, cropsize=256, oilMin=1510, oilMax=1524, maxAge=config.maxAge, maxNum=config.maxNum, writeFile=config.writeFile, OTFdir=config.OTFdir, 
	reconWaves=None, regFile=config.regFile, refChannel=config.refChannel, doMax=config.doMax, doReg=config.doReg, cleanup=True, verbose=True,):
	# check if it appears to be a raw SIM file
	if not isRawSIMfile(fname):
		if not query_yes_no("File doesn't appear to be a raw SIM file... continue?"):
			sys.exit("Quitting...")

	allScores = scoreOTFs(fname, cropsize=cropsize, OTFdir=config.OTFdir, reconWaves=reconWaves, oilMin=oilMin, oilMax=oilMax, maxAge=maxAge, maxNum=maxNum, verbose=verbose, cleanup=cleanup)
	bestOTFs  = getBestOTFs(allScores, verbose=verbose)

	if verbose: print "reconstructing final file..."
	reconstructed = reconstructMulti(fname, bestOTFs)

	numWaves = Mrc.open(reconstructed).hdr.NumWaves
	if doReg and numWaves>1: # perform channel registration
		if verbose: print "perfoming channel registration..."
		matlabReg(reconstructed,regFile,refChannel,doMax)
	
	if writeFile: # write the file to csv
		import pandas as pd
		scoreDF = pd.DataFrame(allScores)
		scoreDF.to_csv(os.path.splitext(fname)[0]+"_scores.csv")



