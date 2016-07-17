"""Configuration File."""
import os 

# CONNECTION TO REMOTE SERVER
# this program assumes the use of private keys for authentication
# https://help.github.com/articles/generating-an-ssh-key/
server = 'cb-cbmf-latwork.med.harvard.edu'
username = 'cbmf'

priismpath = '/Users/talley/Dropbox/NIC/software/priism-4.4.1'

masterScoreCSV = '/mnt/data0/SIMrecon/scores_master.csv'

# DIRECTORIES ON THE RECONSTRUCTION SERVER
# temp folder where files will get uploaded to
remotepath = '/mnt/data0/remote/'
# script to trigger optimized reconstruction
remoteOptScript = '/mnt/data0/SIMrecon/otfsearch/optimalRecon.py'
# script to trigger single recon with specific OTFs
remoteSpecificScript = '/mnt/data0/SIMrecon/otfsearch/singleRecon.py'
# script to trigger single registration with specific OTFs
remoteRegScript = '/mnt/data0/SIMrecon/otfsearch/register.py'
# script to trigger channel registration calibration
remoteRegCalibration = '/mnt/data0/SIMrecon/otfsearch/calculateMatlabTform.py'
# directory with all the OTFs
OTFdir = '/mnt/data0/SIMrecon/OTFs'
# directory with default OTFs
# (this could probably be eliminated in favor of filename conventions)
defaultOTFdir = '/mnt/data0/SIMrecon/OTFs/defaultOTFs'
# string that determines formatting of the OTF filename
OTFtemplate = 'wavelength_date_oil_medium_angle_beadnum'
# delimiter for parsing OTFtemplate
OTFdelim = '_'
# extension of otf files
OTFextension = '.otf'
# app to generate OTF
makeOTFapp = '/Users/talley/Dropbox/Documents/Python/otfsearch/makeotf'
# directory with config files for CUDA-SIMrecon reconstruction
SIconfigDir = '/mnt/data0/SIMrecon/SIconfig'
# path to CUDA-SIMrecon reconstruction app
reconApp = '/usr/local/bin/sir'

# 
otfSigRange=[18000,31500]

# OPTMIIZED RECONSTRUCTION PARAMETERS
# all files will be cropped to this size before reconstruction
cropsize = 256
# max age (in days) of OTFs to use in search process
maxAge = None
# max number of OTFs to use in search process
maxNum = None
# minimum OTF oil RI to use in search
oilMin = 1512
# maximum OTF oil RI to use in seach
oilMax = 1520
# whether to save the CSV file after scoring all the OTFS
writeCSV = True

wiener = 0.001

background = 90

# REGISTRATION AND POST-RECONSTRUCTION PROCESSING
# perform channel registration by default
doReg = False
# perform max projection by default
doMax = False
# perform pseudo WF by default
doWF = False
# name of matlab registration function (must be on MATLAB path)
MatlabRegScript = 'omxreg'
# default reference channel for registration
refChannel = 528
# default matlab regisration file to use
regFile = '/mnt/data0/regfiles/OMXreg_160616_waves435-528-608-683_grid.mat'
# directory containing registration files (and where they will be saved to by default)
regFileDir = '/mnt/data0/regfiles/'

# name of matlab registration calibration function (must be on MATLAB path)
MatlabTformCalc = 'omxregcal'
# default number of iterations for calibration for GUI
CalibrationIter = 2000

# VALIDATION DICTIONARY
# these are valid choices for the respective settings
valid = {
	'waves': [435, 477, 528, 541, 608, 683],
	'cropsize': [36, 64, 128, 256, 512, 1024],
	'oilMin': range(1510, 1530),
	'oilMax': range(1510, 1530)
}

spacings = {
	435 : 0.1920,
	528 : 0.2035,
	608 : 0.2075,
	683 : 0.2200,
	477 : 0.2290,
	541 : 0.2400,
}

nAngles=3
nPhases=5

angles = {
	435 : [-0.831000,-1.884600,0.213000],
	528 : [-0.804300,-1.855500,0.238800],
	608 : [-0.775600,-1.826500,0.270100],
	683 : [-0.768500,-1.823400,0.276100],
	477 : [-0.803400,-1.856900,0.238900],
	541 : [-0.798300,-1.849100,0.244700]
}

em2ex = {
	435 : 405,
	477 : 445,
	528 : 488,
	541 : 514,
	608 : 568,
	683 : 642
}