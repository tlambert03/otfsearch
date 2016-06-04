#default values

host='cb-cbmf-omx.med.harvard.edu/data1'
reconApp='/usr/local/bin/sir'
SIconfigDir = '/mnt/data0/SIMrecon/SIconfig'

cropsize=256
maxAge = ''
maxNum = 10
oilMin = 1510
oilMax = 1522

doReg = True
MatlabRegScript = 'OMXreg2'
refChannel = 528
regFile = '/mnt/data0/MATLAB/talley/OMXwarp/OMXreg_160323_speck.mat'
doMax = True

OTFtemplate = 'wavelength_date_oil_medium_angle_beadnum'
OTFdelim = '_'
OTFextension = '.otf'
OTFdir = '/mnt/data0/SIMrecon/OTFs'
defaultOTFdir = '/mnt/data0/SIMrecon/OTFs/defaultOTFs'

server='cb-cbmf-latwork.med.harvard.edu'
username='user'
remotepath='/mnt/data0/remote/'

writeFile=False