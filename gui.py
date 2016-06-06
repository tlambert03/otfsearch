import Tkinter as Tk
import tkFileDialog
import tkMessageBox
import sys
import config as C
import os
from __init__ import isRawSIMfile
from ScrolledText import ScrolledText
from ttk import Notebook, Style
import time
import Mrc
import threading
from functools import partial
import tkFont

try:
	import paramiko
except ImportError as e:
	print 'paramiko not installed'
	print 'Please install paramiko by typing "pip install paramiko" in terminal'
	sys.exit()

outqueue = [0]

def transferFile(inputFile, remotepath, server, username, mode):
	global outqueue
	statusTxt.set( "connecting to " + C.server + "..." )
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) 
	ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
	ssh.connect(server, username=username)
	thr = threading.Thread(target=sftpPut, args=(inputFile, remotepath, ssh))
	thr.start()
	remoteFile=os.path.join(remotepath,os.path.basename(inputFile))
	root.after(400, updateTransferStatus, (remoteFile,mode))

def SFTPprogress(transferred, outOf):
	global outqueue
	outqueue=[transferred, outOf]

def sftpPut(inputFile, remotepath, ssh):
	global outqueue
	statusTxt.set( "Connection successful, copying to server...")
	sftp = ssh.open_sftp()
	remoteFile=os.path.join(remotepath,os.path.basename(inputFile))
	sftp.put(inputFile, remoteFile, callback=SFTPprogress)
	ssh.close()
	outqueue=['finished']

def updateTransferStatus(tup):
	global outqueue
	msg = outqueue
	if len(msg)==2:
		statusTxt.set("Transfered %0.1f of %0.1f MB" % (float(msg[0])/1000000,float(msg[1])/1000000))
		root.after(400, updateTransferStatus, tup)
	elif msg[0] is not 'finished':
		root.after(400, updateTransferStatus, tup)
	else:
		remoteFile=tup[0]
		mode=tup[1]
		statusTxt.set("Transfer finished. Starting remote reconstructions...")
		if tup[1]=='search':
			sendRemoteCommand(makeOTFsearchCommand(tup[0]))
		elif tup[1]=='single':
			sendRemoteCommand(makeSpecifiedOTFcommand(tup[0]))
		# By not calling root.after here, we allow updateTransferStatus to truly end
		pass


def makeSpecifiedOTFcommand(remoteFile):
	command = ['python', C.remoteSpecificScript, remoteFile, 
				'--regfile', RegFile.get(), '-r', RefChannel.get() ]
	if wiener.get()!='None' and wiener.get():  
		command.extend(['-w', wiener.get()])
	if timepoints.get()!='None' and timepoints.get():  
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

	if maxOTFage.get()!='None' and maxOTFage.get()!='': 
		command.extend(['-a', maxOTFage.get()])
	if maxOTFnum.get()!='None' and maxOTFnum.get()!='':  
		command.extend(['-n', maxOTFnum.get()])
	selectedChannels=[key for key, val in channelSelectVars.items() if val.get()==1]
	command.extend(['-c', " ".join([str(n) for n in sorted(selectedChannels)])])
	return command

def sendRemoteCommand(command):
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) 
	ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
	ssh.connect(C.server, username=C.username)
	channel = ssh.invoke_shell()

	statusTxt.set( "Sending command to remote server..." )
	channel.send(" ".join([str(s) for s in command]) + '\n')

	def updateStatusBar():
		if channel.recv_ready():
			response = channel.recv(2048)
		else:
			response=''


		if response!='':
			statusTxt.set("Receiving feedback from server ... see text area above for details.")
			r=[r for r in response.splitlines() if r and r!='']
			textArea.insert(Tk.END, "\n".join(r))
			textArea.insert(Tk.END, "\n")
			textArea.yview(Tk.END)
			if 'Best OTFs:' in r:
				otfDict=r[r.index('Best OTFs:')+1]
				for k,v in otfDict:
					channelOTFPaths[int(k)].set(v)
					statusTxt.set("Best OTFs added to 'Specific OTFs' tab")
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

def deactivateWaves(waves):
	for w in waves:
		channelSelectVars[w].set(0)
		channelSelectBoxes[w].config(state='disabled')

def getRawFile():
	filename = tkFileDialog.askopenfilename(filetypes=[('DeltaVision Files', '.dv')])
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
	if not RefChannel.get().isdigit() or not int(RefChannel.get()) in waves:
		tkMessageBox.showinfo("Input Error", "Reference channel must be one of the following:" + " ".join([str(w) for w in waves]))
		return 0
	selectedChannels=[key for key, val in channelSelectVars.items() if val.get()==1]
	if len(selectedChannels)==0:
		tkMessageBox.showinfo("Input Error", "You must select at least one channel to reconstruct:")
		return 0

	#OTFdir.get()
	#RegFile.get()
	#doMax.get()
	#doReg.get()
	return 1


def getOTFdir():
	filename = tkFileDialog.askdirectory()
	if filename:
		OTFdir.set( filename )
def getSIRconfigDir():
	filename = tkFileDialog.askdirectory()
	if filename:
		SIRconfigDir.set( filename )
def getRegFile():
	filename = tkFileDialog.askopenfilename(filetypes=[('MATLAB files', '.mat')])
	if filename:
		RegFile.set( filename )


def quit():
	#textArea.insert(Tk.END, 'response')
	outqueue=['finished']
	root.destroy()

def runReconstruct(mode):
	inputFile = rawFilePath.get()
	if not os.path.exists(inputFile):
		tkMessageBox.showinfo("Input file Error", "Input file does not exist")
		return 0
	if not isRawSIMfile(inputFile):
		response = tkMessageBox.askquestion("Input file Error", "Input file doesn't appear to be a raw SIM file... Do it anyway?")
		if response == "no":
			return 0
	if mode=='search':
		if entriesValid():
			transferFile(inputFile, C.remotepath, C.server, C.username, 'search')
	elif mode=='single':
		if entriesValid():
			transferFile(inputFile, C.remotepath, C.server, C.username, 'single')
	else:
		return 0



root = Tk.Tk()
root.title('SIM Reconstruction Tool')
root.resizable(0,0)
#center the window on screen with specified dimensions
size = (684,607)
w = root.winfo_screenwidth()
h = root.winfo_screenheight()
x = w/2 - size[0]/2
y = h/2 - size[1]/2
root.geometry("%dx%d+%d+%d" % (size + (x, y)))


top_frame = Tk.Frame(root)

Nb = Notebook(root)
Style().theme_use('clam')

otfsearchFrame = Tk.Frame(Nb)
singleReconFrame = Tk.Frame(Nb)
configFrame = Tk.Frame(Nb)
helpFrame = Tk.Frame(Nb)

Nb.add(otfsearchFrame, text='Optimized Reconstruction')
Nb.add(singleReconFrame, text='Specify OTFs')
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
chooseFileButton = Tk.Button(top_frame, text ="Choose File", command = getRawFile).grid(row=0, column=7, ipady=3, ipadx=10, padx=2)

Tk.Label(top_frame, text='Channels:').grid(row=1, sticky='e')

allwaves=C.valid['waves']
channelSelectBoxes={}
channelSelectVars={}
for i in range(len(allwaves)):
	channelSelectVars[allwaves[i]]=Tk.IntVar()
	channelSelectVars[allwaves[i]].set(0)
	channelSelectBoxes[allwaves[i]]=Tk.Checkbutton(top_frame)
	channelSelectBoxes[allwaves[i]].config(variable=channelSelectVars[allwaves[i]], text=str(allwaves[i]), state='disabled')
	channelSelectBoxes[allwaves[i]].grid(row=1, column=i+1, sticky='W')

doReg = Tk.IntVar()
doReg.set(C.doReg)
doRegButton = Tk.Checkbutton(top_frame, variable=doReg, text='Do registration').grid(row=2, column=1, columnspan=3, sticky='W')

doMax = Tk.IntVar()
doMax.set(C.doMax)
doMaxButton = Tk.Checkbutton(top_frame, variable=doMax, text='Do max projection').grid(row=2, column=4, columnspan=3, sticky='W')

Tk.Label(top_frame, text='Ref Channel:').grid(row=3, sticky='e')
RefChannel = Tk.StringVar()
RefChannel.set(C.refChannel)
RefChannelEntry = Tk.Entry(top_frame, textvariable=RefChannel).grid(row=3, column=1, columnspan=3, sticky='W')
Tk.Label(top_frame, text="(435,477,528,541,608, or 683)").grid(row=3, column=4, columnspan=3,  sticky='W')

quitButton = Tk.Button(top_frame, text ="Quit", command = quit).grid(row=2, column=7, rowspan=2, ipady=10, ipadx=33)



# OTF search tab widgets

leftLabels = ['Max OTF age(day):', 'Max number OTFs:', 'Crop Size (px):', 'Oil Min RI:', 
			'Oil Max RI:']
for i in range(len(leftLabels)):
	Tk.Label(otfsearchFrame, text=leftLabels[i]).grid(row=i, sticky='E')

maxOTFage = Tk.StringVar()
maxOTFage.set(C.maxAge if C.maxAge is not None else '')
maxOTFageEntry = Tk.Entry(otfsearchFrame, textvariable=maxOTFage).grid(row=0, column=1, sticky='W')
Tk.Label(otfsearchFrame, text="(leave blank for no limit)").grid(row=0, column=2,  sticky='W')

maxOTFnum = Tk.StringVar()
maxOTFnum.set(C.maxNum if C.maxNum is not None else '')
maxOTFnumEntry = Tk.Entry(otfsearchFrame, textvariable=maxOTFnum).grid(row=1, column=1, sticky='W')
Tk.Label(otfsearchFrame, text="(leave blank for no limit)").grid(row=1, column=2,  sticky='W')

cropsize = Tk.StringVar()
cropsize.set(C.cropsize)
cropsizeEntry = Tk.Entry(otfsearchFrame, textvariable=cropsize).grid(row=2, column=1, sticky='W')
Tk.Label(otfsearchFrame, text="(make it a power of 2)").grid(row=2, column=2,  sticky='W')

OilMin = Tk.StringVar()
OilMin.set(C.oilMin)
OilMinEntry = Tk.Entry(otfsearchFrame, textvariable=OilMin).grid(row=3, column=1, sticky='W')

OilMax = Tk.StringVar()
OilMax.set(C.oilMax)
OilMaxEntry = Tk.Entry(otfsearchFrame, textvariable=OilMax).grid(row=4, column=1, sticky='W')

Tk.Button(otfsearchFrame, text ="Run OTF Search", command = partial(runReconstruct, 'search'), width=12).grid(row=8, column=1, columnspan=3, ipady=8, ipadx=8, pady=8, padx=8)


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
	filename = tkFileDialog.askopenfilename(filetypes=[('OTF files', '.otf')])
	if filename:
		channelOTFPaths[var].set(filename)

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

# Help Frame


helpText = Tk.Text(helpFrame)
helpText.pack(fill='both')

helpText.tag_configure("heading", font=('Arial',14,'bold'))
helpText.tag_configure("paragraph", font=('Arial',12,'normal'))
helpText.tag_configure("code", font=('Courier',12,'bold'), background='#bbb')
helpText.tag_configure("italics", font=('Arial',14,'italic'))

helpText.insert('insert','Input File\n', 'heading')
helpText.insert('insert','Select a raw SIM .dv file to process and choose the ', 'paragraph')
helpText.insert('insert',' Channels ', 'code')
helpText.insert('insert',' that you would like to include in the reconstructions. ', 'paragraph')
helpText.insert('insert','When you open a new file, the channels will be automatically populated based on the available channels in the image. \n', 'paragraph')
helpText.insert('insert','\n')
helpText.insert('insert','Optimized Reconstruction \n', 'heading')
helpText.insert('insert','Use this tab to search the folder of OTFs specified in the configuration tab for the optimal OTF for each channel. ', 'paragraph')
helpText.insert('insert','Adjust the OTF search parameters in the optimized reconstruction tab and hit the ', 'paragraph')
helpText.insert('insert',' Run OTF Search ', 'code')
helpText.insert('insert',' button. \n', 'paragraph')
helpText.insert('insert','\n')
helpText.insert('insert','Specify OTFs\n', 'heading')
helpText.insert('insert','This tab can be used to specifiy OTFs for each channel present in the file, then perform a single reconstruction. \n ', 'paragraph')
helpText.insert('insert','\n')
helpText.insert('insert','Configuration\n', 'heading')
helpText.insert('insert','The configuration specifies important folders used in the reconstructions. \n ', 'paragraph')
helpText.insert('insert','\n')
helpText.insert('insert',"If you are getting bugs or unexpected results, don't hesistate to ask for help!", 'italics')


helpText.config(height=15, state='disabled')

# TEXT AREA
textArea = ScrolledText(textAreaFrame)
textArea.config(height=10)
textArea.pack(side='bottom', fill='both')

# STATUS BAR
statusTxt = Tk.StringVar()
statusBar = Tk.Label(statusFrame, textvariable=statusTxt, bd=1, relief='sunken', anchor='w', background='gray')
statusBar.pack(side='bottom', fill='x')

#START PROGRAM
root.mainloop()