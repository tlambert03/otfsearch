#default values


server='cb-cbmf-latwork.med.harvard.edu'
username='user'
remotepath='/mnt/data0/remote/'

reconApp='/usr/local/bin/sir'
SIconfigDir = '/mnt/data0/SIMrecon/SIconfig'
remotescript = '/mnt/data0/SIMrecon/otfsearch/'

cropsize=256
maxAge = None
maxNum = None
oilMin = 1510
oilMax = 1522

doReg = False
MatlabRegScript = 'OMXreg2'
refChannel = 528
regFile = '/mnt/data0/MATLAB/talley/OMXwarp/OMXreg_160323_speck.mat'
doMax = False

OTFtemplate = 'wavelength_date_oil_medium_angle_beadnum'
OTFdelim = '_'
OTFextension = '.otf'
OTFdir = '/mnt/data0/SIMrecon/OTFs'
defaultOTFdir = '/mnt/data0/SIMrecon/OTFs/defaultOTFs'

writeFile=False


valid ={
	'waves': [435,477,528,541,608,683],
	'cropsize': [36,64,128,256,512,1024],
	'oilMin': range(1510,1530),
	'oilMax': range(1510,1530),
}