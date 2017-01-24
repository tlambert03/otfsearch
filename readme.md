installation requirements:
anaconda
CUDA_SIMrecon
install priism
add priism to bashrc
install matlab
git matlab repo



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
Fstack,ampstack = getFFT(indat, shifted=True, log=True)
#line = linecut(amp,p1=coords[0],p2=coords[1], width=3, show=True)

[x,y]=[int(i) for i in coords[0]]
cropsize=70
cropped=amp[x-cropsize:x+cropsize,y-cropsize:y+cropsize]
showPlane(cropped)

m = croparound(ampstack[19],coords[1],15)
from scipy.ndimage import gaussian_filter

sigma = 5 # I have no idea what a reasonable value is here
smoothed = gaussian_filter(croparound(ampstack[18],coords[1],100), sigma)
plt.imshow(smoothed)
plt.show()