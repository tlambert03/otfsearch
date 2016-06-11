import numpy as np
import matplotlib.pyplot as plt


def bestplane( array ):
	scores=[]
	for plane in range(array.shape[0]):
		im = array[plane]
		M,N = im.shape # M and N are dimensions of plane
		DH = np.zeros((M,N)) # pre allocate DH and DV of the same size as plane
		DV = np.zeros((M,N))
		DV[:-2,:] = im[2:,:]-im[:-2,:] # all rows but the first two - all rows but the last two
		DH[:,:-2] = im[:,2:]-im[:,:-2] # all cols but the first two - all cols but the last two
		FM = np.maximum(DH, DV); # get the larger of each respective pixel from DV and DH
		scores.append(np.mean(np.power(FM,2))); #take the mean of the whole array
	return scores.index(np.max(scores))


# SIMcheck options
# public boolean autoCutoff = true;     // no noise cut-off?
# public boolean manualCutoff = false;  // manual noise cut-off?
# public boolean applyWinFunc = false;  // apply window function?
# public boolean gammaMinMax = false;   // show 32-bit gamma 0.2, min-max?
# public boolean logDisplay = false;    // show 8-bit log(Amp^2)?
# public boolean autoScale = false;     // re-scale FFT to mode->max?
#   // N.B. autoScale now *always*/only happens for log(Amp^2): TODO, tidy! 
# public boolean blurAndLUT = false;    // blur & apply false color LUT?
# public boolean showAxial = false;     // show axial FFT?


def getFFT(array, window=True, log=False, shifted=True):
	if window:
		han1=np.hanning(array.shape[-2])
		han2=np.hanning(array.shape[-1])
		F = np.fft.fft2(array*np.outer(han1,han2))
	else:
		F = np.fft.fft2(array)
	if shifted:
		F = np.fft.fftshift(F)
	amp = np.log(np.power(np.abs(F),2)) if log else np.abs(F)
	phase = np.angle(shifted)
	return F, amp

def showPlane(array, scale=(0,1)):
	if len(array.shape)==2:
		ma = np.max(array) * scale[1]
		mi = np.min(array) * scale[0]
		plt.imshow(array, vmin = mi, vmax = ma)
	elif len(array.shape)==3:
		bp = bestplane(array)
		ma = np.max(array[bp]) * scale[1]
		mi = np.min(array[bp]) * scale[0]
		plt.imshow(array[bp], vmin = mi, vmax = ma)
	plt.show()

def radial_profile(data, center=None):
	y, x = np.indices((data.shape))
	if not center: center = tuple(np.floor(np.array(data.shape)/2))
	r = np.sqrt((x - center[0])**2 + (y - center[1])**2)
	r = r.astype(np.int)
	tbin = np.bincount(r.ravel(), data.ravel())
	nr = np.bincount(r.ravel())
	radialprofile = tbin / nr
	return radialprofile 


def linecut(arr,p1=None,p2=None, width=1, show=False):
	if not p1: p1 = np.array(amp.shape)/2	# center spot
	if not p2: p2 = np.array(arr.shape)-1	# bottom right corner
	x0, y0 = p1
	x1, y1 = p2
	length = int(np.hypot(x1-x0, y1-y0))
	Z=np.zeros((width,length))
	for i in range(width):
		if i%2==0:
			x0i = x0 + i/2
			y0i = y0 - i/2
			x1i = x1 + i/2
			y1i = y1 - i/2
		else:
			x0i = x0 - (i+1)/2
			y0i = y0 + (i+1)/2
			x1i = x1 - (i+1)/2
			y1i = y1 + (i+1)/2
		x, y = np.linspace(x0i, x1i, length), np.linspace(y0i, y1i, length)
		
		for n in range(length):
			try:
			    Z[i][n] = arr[int(x[n]), int(y[n])] if (x[n]>=0 and y[n]>=0) else np.nan
			except:
				Z[i][n] = np.nan
	zi = np.average(Z,0)

	if show:
		fig, axes = plt.subplots(nrows=2)
		axes[0].imshow(arr)
		axes[0].plot([x0, x1], [y0, y1], 'ro-', lw=width)
		axes[0].axis('image')
		axes[1].plot(zi)
		plt.show()
	return zi




def makeRadial(vector):
	'''
	take a list or 1-dimensional array and make a radial plot
	'''
	size = np.array(vector).size
	x, y = np.meshgrid(np.arange(-size,size),np.arange(-size,size))
	radialMap = 0.0 * x # easy way to get shape right, 0.0 necessary to make it floats

	r=np.arange(size) #this represents radial distance from origin
	r2 = r**2 # hypotenuse of x,y,r triangle ... x**2 + y**2 = r**2
	xy2 = x**2 + y**2 # pythagorean theorem: distance of any (x,y) pixel from origin
	for ii in range(r.size): # for each pixel
		# lookup the frequency by distance from center
		radialMap[np.where(xy2 >= r2[ii])] = vector[ii]
	return radialMap

# better way:

def getIllumCoords(pixelSize, imwidth, spacing, angle, extend=1):
	'''
	get the pixel coordinates in fourier space corresponding to 
	a given line-spacing and illumination angle.
	(For evaluating artifact in a SIM reconstruction)
	use 'extend' to get coordinates farther from orign by a certain factor
	'''
	# frequency as a function of distance from origin
	frequencies = np.fft.fftfreq(imwidth)[:imwidth/2]
	# this is the distance in pixels from the origin to the pixel that 
	# represents the frequency of the spacing in the image
	kSpacing = np.searchsorted(frequencies/xPixelSize,2/spacing)
	# center coords
	x0=imwidth/2
	y0=imwidth/2
	xOff = kSpacing * np.cos(angle) * extend
	yOff = kSpacing * np.sin(angle) * extend
	artCoord1=(x0+xOff,y0+yOff)
	artCoord2=(x0-xOff,y0-yOff)
	return artCoord1,artCoord2

#example usage
import Mrc
import numpy as np
import matplotlib.pyplot as plt

indat=Mrc.bindFile('/Users/talley/Dropbox/OMX/data/SIRreconTEST/testA_1516_PROC.dv')
xPixelSize=indat.Mrc.hdr.d[0]
imwidth = indat.shape[-1]
spacing=0.414635 # from the log file
angle = -0.80385 # the angle in radians of the illumination
coords = getIllumCoords(xPixelSize, imwidth, spacing, angle)

bp = indat[bestplane(indat)]
F,amp = getFFT(bp, shifted=True, log=True)
line = linecut(amp,p1=coords[0],p2=coords[1], width=3, show=True)

