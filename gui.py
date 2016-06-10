import Tkinter as Tk
import tkFileDialog
import tkMessageBox
import sys
import config as C
import os
from __init__ import isRawSIMfile
from ScrolledText import ScrolledText
from ttk import Notebook, Style
import Mrc
import threading
from functools import partial
from ast import literal_eval
import socket

try:
	import paramiko
except ImportError as e:
	print 'paramiko not installed'
	print 'Please install paramiko by typing "pip install paramiko" in terminal'
	sys.exit()

sentinel = [0]
currentFileTransfer=str()
serverBusy = 0

def connectToServer(host=None, user=None):
	if not host: host=server.get()
	if not user: user = username.get()
	statusTxt.set( "connecting to " + host + "..." )
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) 
	# is this necessary? 
	#hostkey = os.path.expanduser(os.path.join("~", ".ssh", "known_hosts"))
	#try:
	#	ssh.load_host_keys(hostkey)
	#except IOError as e:
	#	statusTxt.set(e)
	#	return 0
	try:
		ssh.connect(host, username=user)
		statusTxt.set( "connected to " + host )
	except socket.gaierror as e:
		# bad server name?
		tkMessageBox.showinfo( 'Connection Failed!', "bad servername?:\n " + host)
		return 0
	except paramiko.PasswordRequiredException as e:
		# bad username?
		tkMessageBox.showinfo( 'Connection Failed!', "bad username?\n " + user)
		return 0
	except paramiko.AuthenticationException as e:
		# bad password/hostkey?
		tkMessageBox.showinfo( 'Connection Failed!', "Authentication error: no password/hostkey?")
		return 0
	except Exception as e:
		print e
		tkMessageBox.showinfo( 'Connection Failed!',e)
		return 0
	return ssh

def uploadFile(inputFile, remotepath, mode):
	'''
	starts a thread for sftp.put.
	the mode command is passed to the updateTranserStatus function
	to determine which command gets sent to the server after upload
	'''
	print 'uploading file: %s' % inputFile
	ssh = connectToServer()
	if ssh:
		thr = threading.Thread(target=putFile, args=(inputFile, remotepath, ssh))
		thr.start()
		remoteFile=os.path.join(remotepath,os.path.basename(inputFile))
		root.after(400, updateTransferStatus, (remoteFile,mode))

def putFile(inputFile, remotepath, ssh):
	sftp = ssh.open_sftp()
	remoteFile=os.path.join(remotepath,os.path.basename(inputFile))
	if os.path.basename(remoteFile) in sftp.listdir(remotepath) and sftp.stat(remoteFile).st_size ==  os.stat(inputFile).st_size:
		statusTxt.set( "File already exists on remote server...")
	else:
		statusTxt.set( "copying to server...")
		global currentFileTransfer
		currentFileTransfer=os.path.basename(inputFile)
		sftp.put(inputFile, remoteFile, callback=SFTPprogress)
	ssh.close()
	global sentinel
	sentinel=['putDone']


def downloadFiles(fileList, ssh):
	global sentinel
	sentinel=[0]
	if ssh:
		thr = threading.Thread(target=getFiles, args=(fileList, ssh))
		thr.start()
		root.after(400, updateTransferStatus, (fileList,))


def getFiles(fileList, ssh):
	#statusTxt.set( "Downloading files...")
	sftp = ssh.open_sftp()
	# this assumes the user hasn't changed it since clicking "reconstruct"
	for file in fileList:
		#statusTxt.set( "Downloading %s..." % file)
		print "Downloading: %s" % file
		localDest = os.path.dirname(rawFilePath.get())
		global currentFileTransfer
		currentFileTransfer=os.path.basename(file)
		sftp.get(file, os.path.join(localDest,os.path.basename(file)), callback=SFTPprogress)
	ssh.close()
	global sentinel
	sentinel=['getDone']


def SFTPprogress(transferred, outOf):
	global sentinel
	sentinel=['sftpProgress',transferred, outOf]


def updateTransferStatus(tup):
	global sentinel
	if sentinel[0]=='sftpProgress':
		statusTxt.set("Transferring %s: %0.1f of %0.1f MB" % (currentFileTransfer,float(sentinel[1])/1000000,float(sentinel[2])/1000000))
		root.after(400, updateTransferStatus, tup)
	elif sentinel[0] is 'putDone':
		statusTxt.set("Upload finished...")
		if tup[1]=='optimal':
			sendRemoteCommand(makeOTFsearchCommand(tup[0]))
		elif tup[1]=='single':
			sendRemoteCommand(makeSpecifiedOTFcommand(tup[0]))
		elif tup[1]=='registerCal':
			sendRemoteCommand(makeRegCalCommand(tup[0]))
		# By not calling root.after here, we allow updateTransferStatus to truly end
		pass
	elif sentinel[0] is 'getDone':
		statusTxt.set("Download finished... Best OTFs copied to Specify OTFs tab")
		global serverBusy
		serverBusy=0
		pass
	elif sentinel[0] is 'canceled':
		statusTxt.set("Process canceled")
	else:
		root.after(400, updateTransferStatus, tup)


def makeRegCalCommand(remoteFile):
	command = ['python', C.remoteRegCalibration, remoteFile, '--outpath', C.regFileDir]
	if calibrationIterations.get(): command.extend(['--iter', calibrationIterations.get()])
	return command

def makeSpecifiedOTFcommand(remoteFile):
	command = ['python', C.remoteSpecificScript, remoteFile, 
				'--regfile', RegFile.get(), '-r', RefChannel.get() ]
	if wiener.get().strip():  
		command.extend(['-w', wiener.get()])
	if timepoints.get().strip():  
		command.extend(['-t',timepoints.get()])
	selectedChannels=[key for key, val in channelSelectVars.items() if val.get()==1]
	for c in selectedChannels:
		command.extend(['-o', "=".join([str(c),channelOTFPaths[c].get()])])
	if doMax.get(): command.append('-x')
	if doReg.get(): command.append('-g')
	return command

def makeOTFsearchCommand(remoteFile):
	command = ['python', C.remoteOptScript, remoteFile,  '-l', OilMin.get(), '-m', OilMax.get(), 
				'-p', cropsize.get(), '--otfdir', OTFdir.get(), '--regfile', RegFile.get(), 
				'-r', RefChannel.get(), '-x', doMax.get(), '-g', doReg.get()]
	if maxOTFage.get().strip(): 
		command.extend(['-a', maxOTFage.get()])
	if maxOTFnum.get().strip():  
		command.extend(['-n', maxOTFnum.get()])
	selectedChannels=[key for key, val in channelSelectVars.items() if val.get()==1]
	if selectedChannels:
		command.extend(['-c', " ".join([str(n) for n in sorted(selectedChannels)])])
	#if not all([k==v.get() for k,v in forceChannels.items() if k in selectedChannels]):
	# if any of the channel:otf pairings have been changed
	for c in selectedChannels:
		# build the "force channels" commands
		if not c==forceChannels[c].get(): 
			command.extend(['-f', "=".join([str(c),str(forceChannels[c].get())])])
	return command


def sendRemoteCommand(command):
	ssh = connectToServer()
	if ssh:
		channel = ssh.invoke_shell()

		statusTxt.set( "Sending command to remote server..." )
		channel.send(" ".join([str(s) for s in command]) + '\n')

		def updateStatusBar():
			if channel.recv_ready():
				response = channel.recv(2048)
			else:
				response=''
			global sentinel
			if sentinel[0]=='canceled':
				statusTxt.set("Process canceled!")
				ssh.close()
				sentinel = [0]
				return 0
			if response!='':
				statusTxt.set("Receiving feedback from server ... see text area above for details.")
				r=[r for r in response.splitlines() if r and r!='']
				textArea.insert(Tk.END, "\n".join(r))
				textArea.insert(Tk.END, "\n")
				textArea.yview(Tk.END)
				if 'Best OTFs:' in r:
					otfDict=r[r.index('Best OTFs:')+1]
					if not isinstance(otfDict,dict):
						otfDict = literal_eval(otfDict)
					if isinstance(otfDict,dict):
						for k,v in otfDict.items():
							channelOTFPaths[int(k)].set(v)
							statusTxt.set("Done.  Best OTFs added to 'Specific OTFs' tab")
				if 'Files Ready:' in r:
					i=r.index('Files Ready:')+1
					statusTxt.set("Downloading files from server... ")
					fileList = []
					while not r[i].startswith('Done'):
						fileList.append(r[i].split(": ")[1])
						i+=1
					downloadFiles(fileList, ssh)
					return
			if response.endswith(':~$ '):
				if 'OTFs' not in statusTxt.get():
					statusTxt.set("Done")
				ssh.close()
			elif response.endswith("File doesn't appear to be a raw SIM file... continue?"):
				statusTxt.set("Remote server didn't recognize file as raw SIM file and quit")
				ssh.close()

			else:
				statusBar.after(1000, updateStatusBar)
		updateStatusBar()


def activateWaves(waves):
	for w in waves:
		channelSelectBoxes[w].config(state='normal')
		channelSelectVars[w].set(1)
		forceChannelsMenus[w].config(state='normal')

def deactivateWaves(waves):
	for w in waves:
		channelSelectVars[w].set(0)
		channelSelectBoxes[w].config(state='disabled')
		forceChannelsMenus[w].config(state='disabled')

def getRawFile():
	filename = tkFileDialog.askopenfilename(filetypes=[('DeltaVision Files', '.dv')])
	setRawFile(filename)


def setRawFile(filename):
	if filename:
		rawFilePath.set( filename )
		try:
			header = Mrc.open(filename).hdr
			waves = [i for i in header.wave if i != 0]
			deactivateWaves(allwaves)
			activateWaves(waves)
			statusTxt.set('Valid .dv file')
		except ValueError:
			statusTxt.set('Unable to read file... is it a .dv file?')


def entriesValid():
	if maxOTFnum.get():
		if not maxOTFnum.get().isdigit():
			tkMessageBox.showinfo("Input Error", "Max number of OTFs must be a positive integer (or blank)")
			return 0
	if maxOTFage.get():
		if not maxOTFage.get().isdigit():
			tkMessageBox.showinfo("Input Error", "Max OTF age must be a positive integer (or blank)")
			return 0
	if not OilMin.get().isdigit() or not int(OilMin.get()) in C.valid['oilMin']:
		tkMessageBox.showinfo("Input Error", "Oil min must be an integer between 1510 and 1530")
		return 0
	if not OilMax.get().isdigit() or not int(OilMax.get()) in C.valid['oilMax']:
		tkMessageBox.showinfo("Input Error", "Oil max must be an integer between 1510 and 1530")
		return 0
	if not cropsize.get().isdigit() or not int(cropsize.get()) in C.valid['cropsize']:
		tkMessageBox.showinfo("Input Error", "Cropsize must be a power of 2 <= 512")
		return 0
	waves = [i for i in Mrc.open(rawFilePath.get()).hdr.wave if i != 0]
	if doReg.get():
		if not int(RefChannel.get()) in waves:
			tkMessageBox.showinfo("Input Error", "Reference channel must be one of the following:" + " ".join([str(w) for w in waves]))
			return 0
		if not RegFile.get().strip():
			tkMessageBox.showinfo("Registration File Error", "Please select a registration file in the config tab")
			return 0
	selectedChannels=[key for key, val in channelSelectVars.items() if val.get()==1]
	if len(selectedChannels)==0:
		tkMessageBox.showinfo("Input Error", "You must select at least one channel to reconstruct:")
		return 0

	#OTFdir.get()
	#doMax.get()
	return 1


def getOTFdir():
	filename = tkFileDialog.askdirectory()
	if filename:
		OTFdir.set( filename )
def getSIRconfigDir():
	filename = tkFileDialog.askdirectory()
	if filename:
		SIRconfigDir.set( filename )
def getbatchDir():
	filename = tkFileDialog.askdirectory()
	if filename:
		batchDir.set( filename )



def getRegFile():
	filename = tkFileDialog.askopenfilename(filetypes=[('MATLAB files', '.mat')])
	if filename:
		RegFile.set( filename )



def getRegFile():

	ssh = connectToServer()
	sftp = ssh.open_sftp()
	reglist = sorted([item for item in sftp.listdir(C.regFileDir) if item.endswith('.mat')])

	top = Tk.Toplevel()
	top.title('Choose registration file')
	scrollbar = Tk.Scrollbar(top)
	scrollbar.grid(row=0, column=3, sticky='ns')

	LB = Tk.Listbox(top, yscrollcommand=scrollbar.set, height=18, width=45)
	
	for item in reglist:
		LB.insert(Tk.END, os.path.basename(item))
	LB.grid(row=0, column=0, columnspan=3)

	scrollbar.config(command=LB.yview)

	def Select():
		items = LB.curselection()

		item = [reglist[int(item)] for item in items][0]

		if item: 
			RegFile.set(os.path.join(C.regFileDir,item))
		top.destroy()

	def Cancel():
		top.destroy()

	selectButton = Tk.Button(top, text="Select",command=Select, pady=6, padx=10)
	selectButton.grid(row=1, column=0)

	cancelButton = Tk.Button(top, text="Cancel",command=Cancel, pady=6, padx=10)
	cancelButton.grid(row=1, column=1)
	
	top.update_idletasks()
	w = top.winfo_screenwidth()
	h = top.winfo_screenheight()
	size = tuple(int(_) for _ in top.geometry().split('+')[0].split('x'))
	x = w/2 - size[0]/2
	y = h/2 - size[1]/1.3
	top.geometry("%dx%d+%d+%d" % (size + (x, y)))
	top.resizable(0,0)


def quit():
	root.destroy()

def cancel():
	global serverBusy
	global sentinel
	sentinel = ['canceled']
	serverBusy=0


def runReconstruct(mode):
	inputFile = rawFilePath.get()
	if not os.path.exists(inputFile):
		tkMessageBox.showinfo("Input file Error", "Input file does not exist")
		return 0
	if not isRawSIMfile(inputFile):
		response = tkMessageBox.askquestion("Input file Error", "Input file doesn't appear to be a raw SIM file... Do it anyway?")
		if response == "no":
			return 0
	if entriesValid():
		uploadFile(inputFile, C.remotepath, mode)
	else:
		print 'entries Valid failed....'
		return 0



root = Tk.Tk()
root.title('CBMF SIM Reconstruction Tool')
#center the window on screen with specified dimensions

top_frame = Tk.Frame(root)

Nb = Notebook(root)
Style().theme_use('clam')

otfsearchFrame = Tk.Frame(Nb)
singleReconFrame = Tk.Frame(Nb)
configFrame = Tk.Frame(Nb)
batchFrame = Tk.Frame(Nb)
registrationFrame = Tk.Frame(Nb)
helpFrame = Tk.Frame(Nb)

Nb.add(otfsearchFrame, text='Optimized Reconstruction')
Nb.add(singleReconFrame, text='Specify OTFs')
Nb.add(registrationFrame, text='Channel Registration')
Nb.add(batchFrame, text='Batch')
Nb.add(configFrame, text='Configuration')
Nb.add(helpFrame, text='Help')

textAreaFrame = Tk.Frame(root, bg='gray', bd=2)
statusFrame = Tk.Frame(root)


top_frame.grid(row = 0, pady=10)
Nb.grid(row=1, padx=15, pady=5)
textAreaFrame.grid(row = 2, sticky="nsew", padx=15, pady=10)
statusFrame.grid(row = 3, sticky="ew")


# Top Area widgets

Tk.Label(top_frame, text='Input File:').grid(row=0, sticky='e')
rawFilePath = Tk.StringVar()
rawFileEntry = Tk.Entry(top_frame, textvariable=rawFilePath, width=48).grid(row=0, columnspan=6, column=1, sticky='W')
chooseFileButton = Tk.Button(top_frame, text ="Choose File", command = getRawFile, width=9).grid(row=0, column=7, ipady=3, ipadx=10, padx=2)

Tk.Label(top_frame, text='Use Channels:').grid(row=1, sticky='e')

allwaves=C.valid['waves']
channelSelectBoxes={}
channelSelectVars={}
for i in range(len(allwaves)):
	channelSelectVars[allwaves[i]]=Tk.IntVar()
	channelSelectVars[allwaves[i]].set(0)
	channelSelectBoxes[allwaves[i]]=Tk.Checkbutton(top_frame)
	channelSelectBoxes[allwaves[i]].config(variable=channelSelectVars[allwaves[i]], text=str(allwaves[i]), state='disabled')
	channelSelectBoxes[allwaves[i]].grid(row=1, column=i+1, sticky='W')

def naccheck(entry, var):
	if var.get() == 0:
		entry.configure(state='disabled')
	else:
		entry.configure(state='normal')

Tk.Label(top_frame, text='Ref Channel:').grid(row=2, sticky='e')
RefChannel = Tk.IntVar()
RefChannel.set(C.refChannel)
RefChannelEntry = Tk.OptionMenu(top_frame, RefChannel, *allwaves)
if not C.doReg: RefChannelEntry.config(state='disabled')
RefChannelEntry.grid(row=2, column=1, columnspan=1, sticky='W')

doReg = Tk.IntVar()
doReg.set(C.doReg)
doRegButton = Tk.Checkbutton(top_frame, variable=doReg, text='Do registration', command=lambda e=RefChannelEntry, v=doReg: naccheck(e,v)).grid(row=2, column=2, columnspan=2, sticky='W')

doMax = Tk.IntVar()
doMax.set(C.doMax)
doMaxButton = Tk.Checkbutton(top_frame, variable=doMax, text='Do max projection').grid(row=2, column=4, columnspan=2, sticky='W')


quitButton = Tk.Button(top_frame, text ="Quit", command = quit, width=9).grid(row=1, column=7, ipady=3, ipadx=10, padx=2)

quitButton = Tk.Button(top_frame, text ="Cancel", command = cancel, width=9).grid(row=2, column=7, ipady=3, ipadx=10, padx=2)


# OTF search tab widgets

leftLabels = ['Max OTF age (days):', 'Max number OTFs:', 'Crop Size (pix):', 'Min Oil RI:', 
			'Max Oil RI:']
for i in range(len(leftLabels)):
	Tk.Label(otfsearchFrame, text=leftLabels[i]).grid(row=i, sticky='E')

maxOTFage = Tk.StringVar()
maxOTFage.set(C.maxAge if C.maxAge is not None else '')
maxOTFageEntry = Tk.Entry(otfsearchFrame, textvariable=maxOTFage).grid(row=0, column=1, columnspan=3, sticky='W')

maxOTFnum = Tk.StringVar()
maxOTFnum.set(C.maxNum if C.maxNum is not None else '')
maxOTFnumEntry = Tk.Entry(otfsearchFrame, textvariable=maxOTFnum).grid(row=1, column=1, columnspan=3, sticky='W')

cropsize = Tk.StringVar()
cropsize.set(C.cropsize)
cropsizeEntry = Tk.Entry(otfsearchFrame, textvariable=cropsize).grid(row=2, column=1, columnspan=3, sticky='W')

OilMin = Tk.StringVar()
OilMin.set(C.oilMin)
OilMinEntry = Tk.Entry(otfsearchFrame, textvariable=OilMin).grid(row=3, column=1, columnspan=3, sticky='W')

OilMax = Tk.StringVar()
OilMax.set(C.oilMax)
OilMaxEntry = Tk.Entry(otfsearchFrame, textvariable=OilMax).grid(row=4, column=1, columnspan=3, sticky='W')


Tk.Button(otfsearchFrame, text ="Run OTF Search", command = partial(runReconstruct, 'optimal'), width=12).grid(row=8, column=1, columnspan=3, ipady=8, ipadx=8, pady=8, padx=8)

forceChannels={}
forceChannelsMenus={}
Tk.Label(otfsearchFrame, text="Force specific images channel:OTF pairings", font=('Arial',12, 'bold')).grid(row=0, column=5, columnspan=3, sticky='w', padx=(20, 0))
for i in range(len(allwaves)):
	Tk.Label(otfsearchFrame, text="OTF to use for channel %s:" % allwaves[i]).grid(row=i+1, column=5, sticky='E', padx=(40, 0))
	forceChannels[allwaves[i]] = Tk.IntVar()
	forceChannels[allwaves[i]].set(allwaves[i])
	forceChannelsMenus[allwaves[i]] = Tk.OptionMenu(otfsearchFrame, forceChannels[allwaves[i]], *allwaves)
	forceChannelsMenus[allwaves[i]].config(state='disabled')
	forceChannelsMenus[allwaves[i]].grid(row=i+1, column=6,sticky='w')
	

# SINGLE RECON TAB


Tk.Label(singleReconFrame, text='Wiener constant:').grid(row=0, sticky='e')
wiener = Tk.StringVar()
wiener.set('')
wienerEntry = Tk.Entry(singleReconFrame, textvariable=wiener, width=15).grid(row=0, column=1, sticky='W')

Tk.Label(singleReconFrame, text='Timepoints:').grid(row=0, column=2, sticky='e')
timepoints = Tk.StringVar()
timepoints.set('')
timepointsEntry = Tk.Entry(singleReconFrame, textvariable=timepoints, width=15).grid(row=0, column=3, sticky='W')


for i in range(len(allwaves)):
	Tk.Label(singleReconFrame, text=str(allwaves[i])+"nm OTF: ").grid(row=i+1, sticky='E')

def getChannelOTF(var):

	ssh = connectToServer()
	sftp = ssh.open_sftp()
	otflist = sorted([item for item in sftp.listdir(OTFdir.get()) if item.endswith('.otf')])
	selectedlist = [item for item in otflist if item.startswith(str(var))]
	fullist=0

	top = Tk.Toplevel()
	top.title('Choose OTF for %d' % var)
	scrollbar = Tk.Scrollbar(top)
	scrollbar.grid(row=0, column=3, sticky='ns')

	LB = Tk.Listbox(top, yscrollcommand=scrollbar.set, height=18, width=28)
	
	for item in selectedlist:
		LB.insert(Tk.END, os.path.basename(item))
	LB.grid(row=0, column=0, columnspan=3)

	scrollbar.config(command=LB.yview)

	def Select():
		items = LB.curselection()
		if fullist:
			item = [otflist[int(item)] for item in items][0]
		else:
			item = [selectedlist[int(item)] for item in items][0]
		if item: 
			channelOTFPaths[var].set(os.path.join(OTFdir.get(),item))
		top.destroy()

	def ShowAll():
		LB.delete(0, 'end')
		for item in otflist:
			LB.insert(Tk.END, os.path.basename(item))
		fullist=1

	def Cancel():
		top.destroy()

	selectButton = Tk.Button(top, text="Select",command=Select, pady=6, padx=10)
	selectButton.grid(row=1, column=0)

	cancelButton = Tk.Button(top, text="ShowAll",command=ShowAll, pady=6, padx=10)
	cancelButton.grid(row=1, column=2)

	cancelButton = Tk.Button(top, text="Cancel",command=Cancel, pady=6, padx=10)
	cancelButton.grid(row=1, column=1)
	
	top.update_idletasks()
	w = top.winfo_screenwidth()
	h = top.winfo_screenheight()
	size = tuple(int(_) for _ in top.geometry().split('+')[0].split('x'))
	x = w/2 - size[0]/2
	y = h/2 - size[1]/1.3
	top.geometry("%dx%d+%d+%d" % (size + (x, y)))
	top.resizable(0,0)



allwaves=C.valid['waves']
channelOTFPaths={}
channelOTFEntries={}
channelOTFButtons={}

for i in range(len(allwaves)):
	channelOTFPaths[allwaves[i]] = Tk.StringVar()
	channelOTFPaths[allwaves[i]].set(os.path.join(C.defaultOTFdir,str(allwaves[i])+'.otf'))
	channelOTFEntries[allwaves[i]] = Tk.Entry(singleReconFrame, textvariable=channelOTFPaths[allwaves[i]], width=48)
	channelOTFEntries[allwaves[i]].grid(row=i+1, columnspan=6, column=1, sticky='W')
	channelOTFButtons[allwaves[i]] = Tk.Button(singleReconFrame, text ="Select OTF", command=partial(getChannelOTF, allwaves[i]))
	channelOTFButtons[allwaves[i]].grid(row=i+1, column=7, ipady=3, ipadx=10, padx=2)


Tk.Button(singleReconFrame, text ="Reconstruct", command = partial(runReconstruct, 'single'), width=12).grid(row=8, column=1, columnspan=3, ipady=8, ipadx=8, pady=8, padx=8)


# REGISTRATION TAB

def getregCalImage():
	filename = tkFileDialog.askopenfilename(filetypes=[('DV file', '.dv')])
	if filename:
		regCalImage.set( filename )


def sendRegCal():
	inputFile = regCalImage.get()
	if not os.path.exists(inputFile):
		tkMessageBox.showinfo("Input file Error", "Registration calibration image doesn't exist")
		return 0
	uploadFile(inputFile, C.remotepath, 'registerCal')


Tk.Label(registrationFrame, text='Calibration Image:').grid(row=0, sticky='e')
regCalImage = Tk.StringVar()
regCalImageEntry = Tk.Entry(registrationFrame, textvariable=regCalImage, width=35).grid(row=0, column=1, columnspan=5, sticky='W')
chooseregCalImageButton = Tk.Button(registrationFrame, text ="Choose Registration Image", command = getregCalImage).grid(row=0, column=3, ipady=3, ipadx=10, padx=2, stick='w')

Tk.Label(registrationFrame, text='Iterations:').grid(row=1, sticky='e')
calibrationIterations = Tk.IntVar()
calibrationIterationsEntry = Tk.Entry(registrationFrame, textvariable=calibrationIterations, width=35).grid(row=1, column=1, columnspan=2, sticky='W')
sendregCalImageButton = Tk.Button(registrationFrame, text ="Perform Registration Calibration", command = sendRegCal).grid(row=1, column=3, columnspan=2, ipady=3, ipadx=10, padx=2, sticky='w')
calibrationIterations.set(C.CalibrationIter)

# CONFIG TAB

Tk.Label(configFrame, text='OTF Directory:').grid(row=0, sticky='e')
OTFdir = Tk.StringVar()
OTFdirEntry = Tk.Entry(configFrame, textvariable=OTFdir, width=48).grid(row=0, column=1, columnspan=6, sticky='W')
chooseOTFdirButton = Tk.Button(configFrame, text ="Choose Dir", command = getOTFdir).grid(row=0, column=7, ipady=3, ipadx=10, padx=2)
OTFdir.set( C.OTFdir )

Tk.Label(configFrame, text='SIR config Dir:').grid(row=1, sticky='e')
SIRconfigDir = Tk.StringVar()
SIRconfigDirEntry = Tk.Entry(configFrame, textvariable=SIRconfigDir, width=48).grid(row=1, column=1, columnspan=6, sticky='W')
chooseSIRconfigdirButton = Tk.Button(configFrame, text ="Choose Dir", command = getSIRconfigDir).grid(row=1, column=7, ipady=3, ipadx=10, padx=2)
SIRconfigDir.set( C.SIconfigDir )

Tk.Label(configFrame, text='Registration File:').grid(row=2, sticky='e')
RegFile = Tk.StringVar()
RegFileEntry = Tk.Entry(configFrame, textvariable=RegFile, width=48).grid(row=2, column=1, columnspan=6, sticky='W')
chooseRegFileButton = Tk.Button(configFrame, text ="Choose File", command = getRegFile).grid(row=2, column=7, ipady=3, ipadx=10, padx=2)
RegFile.set( C.regFile )

Tk.Label(configFrame, text='Server Address:').grid(row=3, sticky='e')
server = Tk.StringVar()
serverEntry = Tk.Entry(configFrame, textvariable=server, width=48).grid(row=3, column=1, columnspan=6, sticky='W')
server.set( C.server )

Tk.Label(configFrame, text='Username:').grid(row=4, sticky='e')
username = Tk.StringVar()
usernameEntry = Tk.Entry(configFrame, textvariable=username, width=48).grid(row=4, column=1, columnspan=6, sticky='W')
username.set( C.username )

def testConnection():
	if connectToServer():
		tkMessageBox.showinfo('Yay!','%s\nConnection successfull!' % server.get())
	else:
		statusTxt.set('Aw snap.','%s\nConnection failed!' % server.get())


Tk.Button(configFrame, text ="Test Connection", command = testConnection, width=12).grid(row=5, column=1, columnspan=2, ipady=6, ipadx=6, sticky='w')


# BATCH TAB

Tk.Label(batchFrame, text='Directory:').grid(row=0, sticky='e')
batchDir = Tk.StringVar()
batchDirEntry = Tk.Entry(batchFrame, textvariable=batchDir, width=48).grid(row=0, column=1, columnspan=6, sticky='W')
batchDirButton = Tk.Button(batchFrame, text ="Choose Dir", command = getbatchDir).grid(row=0, column=7, ipady=3, ipadx=10, padx=2)


def batchRecon(mode):
	batchlist=[]
	directory =  batchDir.get()
	for R, S, F in os.walk(directory):
		for file in F:
			fullpath=os.path.join(R,file)
			if isRawSIMfile(fullpath):
				batchlist.append(fullpath)

	def callback(mode):
		global serverBusy
		if serverBusy:
			root.after(600, callback, mode)
		else:
			serverBusy=1
			if len(batchlist):
				item = batchlist.pop(0)
				setRawFile(item)
				print("sending reconstruction on %s" %item)
				runReconstruct(mode)
				callback(mode)
			else:
				pass
	callback(mode)



Tk.Button(batchFrame, text ="Batch Optimized Recon", command = partial(batchRecon, 'optimal')).grid(row=1, column=1, columnspan=3, ipady=6, ipadx=6, sticky='w')
Tk.Button(batchFrame, text ="Batch Recon with Specified OTFs", command = partial(batchRecon, 'single')).grid(row=1, column=4, columnspan=3, ipady=6, ipadx=6, sticky='w')
Tk.Label(batchFrame, text='(Settings on the respective tabs will be used for batch reconstructions)').grid(row=2, column=1, columnspan=6, sticky='e')

# Help Frame


helpText = ScrolledText(helpFrame, wrap='word')
helpText.pack(fill='both')

helpText.tag_configure("heading", font=('Helvetica',12,'bold'))
helpText.tag_configure("paragraph", font=('Helvetica',10,'normal'))
helpText.tag_configure("code", font=('Monaco',10,'bold'))
helpText.tag_configure("italics", font=('Helvetica',12,'italic'))

helpText.insert('insert','Input File\n', 'heading')
helpText.insert('insert','Select a raw SIM .dv file to process and choose the ', 'paragraph')
helpText.insert('insert','Channels ', 'code')
helpText.insert('insert','that you would like to include in the reconstructions. ', 'paragraph')
helpText.insert('insert','When you open a new file, the channels will be automatically populated based on the available channels in the image. \n', 'paragraph')
helpText.insert('insert','\n')
helpText.insert('insert','Optimized Reconstruction \n', 'heading')
helpText.insert('insert','Use this tab to search the folder of OTFs specified in the configuration tab for the optimal OTF for each channel. ', 'paragraph')
helpText.insert('insert','Adjust the OTF search parameters in the optimized reconstruction tab and hit the ', 'paragraph')
helpText.insert('insert','Run OTF Search ', 'code')
helpText.insert('insert','button. \n', 'paragraph')
helpText.insert('insert','\n')
helpText.insert('insert','Specify OTFs\n', 'heading')
helpText.insert('insert','This tab can be used to specifiy OTFs for each channel present in the file, then perform a single reconstruction. \n ', 'paragraph')
helpText.insert('insert','\n')
helpText.insert('insert','Configuration\n', 'heading')
helpText.insert('insert','The configuration specifies important folders used in the reconstructions. \n ', 'paragraph')
helpText.insert('insert','\n')
helpText.insert('insert',"If you are getting bugs or unexpected results, don't hesistate to ask for help!\n", 'italics')
helpText.insert('insert','\n')
helpText.insert('insert',"Created by Talley Lambert, (c) 2016", 'paragraph')

helpText.config(height=17, state='disabled')

# TEXT AREA
textArea = ScrolledText(textAreaFrame)
textArea.config(height=10)
textArea.pack(side='bottom', fill='both')

# STATUS BAR
statusTxt = Tk.StringVar()
statusBar = Tk.Label(statusFrame, textvariable=statusTxt, bd=1, relief='sunken', anchor='w', background='gray')
statusBar.pack(side='bottom', fill='x')


# UPDATE WINDOW GEOMETRY AND CENTER ON SCREEN
root.update_idletasks()
w = root.winfo_screenwidth()
h = root.winfo_screenheight()
size = tuple(int(_) for _ in root.geometry().split('+')[0].split('x'))
x = w/2 - size[0]/2
y = h/2 - size[1]/1.3
root.geometry("%dx%d+%d+%d" % (size + (x, y)))
root.resizable(0,0)


#START PROGRAM
root.mainloop()