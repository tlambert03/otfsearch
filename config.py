"""Configuration File."""

# CONNECTION TO REMOTE SERVER
# this program assumes the use of private keys for authentication
# https://help.github.com/articles/generating-an-ssh-key/
server = 'cb-cbmf-latwork.med.harvard.edu'
username = 'user'

# DIRECTORIES ON THE RECONSTRUCTION SERVER
# temp folder where files will get uploaded to
remotepath = '/mnt/data0/remote/'
# script to trigger optimized reconstruction
remoteOptScript = '/mnt/data0/SIMrecon/otfsearch/__main__.py'
# script to trigger single recon with specific OTFs
remoteSpecificScript = '/mnt/data0/SIMrecon/otfsearch/singleRecon.py'
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
# directory with config files for CUDA-SIMrecon reconstruction
SIconfigDir = '/mnt/data0/SIMrecon/SIconfig'
# path to CUDA-SIMrecon reconstruction app
reconApp = '/usr/local/bin/sir'

# OPTMIIZED RECONSTRUCTION PARAMETERS
# all files will be cropped to this size before reconstruction
cropsize = 256
# max age (in days) of OTFs to use in search process
maxAge = None
# max number of OTFs to use in search process
maxNum = None
# minimum OTF oil RI to use in search
oilMin = 1510
# maximum OTF oil RI to use in seach
oilMax = 1522
# whether to save the CSV file after scoring all the OTFS
writeCSV = True

wiener = 0.001

background = 90

# REGISTRATION AND POST-RECONSTRUCTION PROCESSING
# perform channel registration by default
doReg = False
# perform max projection by default
doMax = False
# name of matlab registration function (must be on MATLAB path)
MatlabRegScript = 'omxreg'
# default reference channel for registration
refChannel = 528
# default matlab regisration file to use
regFile = '/mnt/data0/MATLAB/talley/OMXwarp/OMXreg_160323_speck.mat'
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
