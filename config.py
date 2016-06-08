#default values


server='cb-cbmf-latwork.med.harvard.edu'
username='user'
remotepath='/mnt/data0/remote/'

reconApp='/usr/local/bin/sir'
SIconfigDir = '/mnt/data0/SIMrecon/SIconfig'
remoteOptScript = '/mnt/data0/SIMrecon/otfsearch/__main__.py'
remoteSpecificScript = '/mnt/data0/SIMrecon/otfsearch/singleRecon.py'
remoteRegCalibration = '/mnt/data0/SIMrecon/otfsearch/calculateMatlabTform.py'

cropsize=256
maxAge = None
maxNum = None
oilMin = 1510
oilMax = 1522

doReg = False
doMax = False
MatlabRegScript = 'OMXreg2'
MatlabTformCalc = 'OMXregCal'
refChannel = 528
regFile = '/mnt/data0/MATLAB/talley/OMXwarp/OMXreg_160323_speck.mat'
CalibrationIter = 10000
regFileDir = '/mnt/data0/regfiles/'

OTFtemplate = 'wavelength_date_oil_medium_angle_beadnum'
OTFdelim = '_'
OTFextension = '.otf'
OTFdir = '/mnt/data0/SIMrecon/OTFs'
defaultOTFdir = '/mnt/data0/SIMrecon/OTFs/defaultOTFs'

writeFile=True


valid ={
	'waves': [435,477,528,541,608,683],
	'cropsize': [36,64,128,256,512,1024],
	'oilMin': range(1510,1530),
	'oilMax': range(1510,1530),
}