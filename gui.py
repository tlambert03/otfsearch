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


try:
	import paramiko
except ImportError as e:
	print 'paramiko not installed'
	print 'Please install paramiko by typing "pip install paramiko" in terminal'
	sys.exit()

outqueue = [0]

def transferFile(inputFile, remotepath, server, username):
	global outqueue
	statusTxt.set( "connecting to " + C.server + "..." )
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) 
	ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
	ssh.connect(server, username=username)
	thr = threading.Thread(target=sftpPut, args=(inputFile, remotepath, ssh))
	thr.start()
	remoteFile=os.path.join(remotepath,os.path.basename(inputFile))
	root.after(400, update, remoteFile)

def SFTPprogress(transferred, outOf):
	global outqueue
	outqueue=[transferred, outOf]

def sftpPut(inputFile, remotepath, ssh):
	global outqueue
	statusTxt.set( "Connection successful, copying to server... Program may freeze")
	sftp = ssh.open_sftp()
	remoteFile=os.path.join(remotepath,os.path.basename(inputFile))
	sftp.put(inputFile, remoteFile, callback=SFTPprogress)
	ssh.close()
	outqueue=['finished']

def update(remoteFile):
	global outqueue
	msg = outqueue
	if len(msg)==2:
		statusTxt.set("Transfered %0.1f of %0.1f MB" % (float(msg[0])/1000000,float(msg[1])/1000000))
		root.after(400, update, remoteFile)
	elif msg[0] is not 'finished':
		root.after(400, update, remoteFile)
	else:
		statusTxt.set("Transfer finished. Starting remote reconstructions...")
		triggerRemoteOTFsearch(remoteFile)
		# By not calling root.after here, we allow update to
		# truly end
		pass


def triggerRemoteOTFsearch(remoteFile):
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) 
	ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
	ssh.connect(C.server, username=C.username)
	channel = ssh.invoke_shell()

	command = ['python', C.remotescript, remoteFile, '-n', maxOTFnum.get(), 
				'-l', OilMin.get(), '-m', OilMax.get(), '-p', cropsize.get(), 
				'--otfdir', OTFdir.get(), '--regfile', RegFile.get(), 
				'-r', RefChannel.get(), '-x', doMax.get(), '-g', doReg.get()]
	if maxOTFage.get()!='None' and maxOTFage.get() != '':  
		command.extend(['-a', maxOTFage.get()])

	selectedChannels=[key for key, val in channelSelectVars.items() if val.get()==1]
	command.extend(['-c', " ".join([str(n) for n in sorted(selectedChannels)])])

	statusTxt.set( "Sending reconstruction command to remote server..." )
	channel.send(" ".join([str(s) for s in command]) + '\n')

	def updateStatusBar():
		if channel.recv_ready():
			response = channel.recv(2048)
		else:
			response=''

		if response.endswith(':~$ '):
			statusTxt.set("done")
			ssh.close()
		elif response.endswith("File doesn't appear to be a raw SIM file... continue?"):
			statusTxt.set("Remote server didn't recognize file as raw SIM file and quit")
			ssh.close()
		else:
			statusTxt.set("scoring reconstructions...")
			if response!='':
				r=[r for r in response.splitlines() if r and r!='']
				textArea.insert(Tk.END, "\n".join(r))
				textArea.insert(Tk.END, "\n")
				textArea.yview(Tk.END)
			statusBar.after(1000, tick)
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
	filename = tkFileDialog.askopenfilename()
	rawFilePath.set( filename )
	header = Mrc.open(filename).hdr
	waves = [i for i in header.wave if i != 0]
	deactivateWaves(allwaves)
	activateWaves(waves)

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
	filename = tkFileDialog.askopenfilename()
	OTFdir.set( filename )
def getSIRconfigDir():
	filename = tkFileDialog.askopenfilename()
	SIRconfigDir.set( filename )
def getRegFile():
	filename = tkFileDialog.askopenfilename()
	RegFile.set( filename )


def quit():
	#textArea.insert(Tk.END, 'response')
	outqueue=['finished']
	root.destroy()

def doit():
	inputFile = rawFilePath.get()
	if not os.path.exists(inputFile):
		tkMessageBox.showinfo("Input file Error", "Input file does not exist")
		return 0
	if not isRawSIMfile(inputFile):
		response = tkMessageBox.askquestion("Input file Error", "Input file doesn't appear to be a raw SIM file... Do it anyway?")
		if response == "no":
			return 0

	if entriesValid():
		#	tkMessageBox.showinfo("Copying", "Copying...")
		remoteFile = transferFile(inputFile, C.remotepath, C.server, C.username)
	else:
		return 0



root = Tk.Tk()
root.title('SIM Reconstruction Tool')
#root.geometry("720x600+550+150")

# create all of the main containers
Nb = Notebook(root)
Style().theme_use('clam')

center = Tk.Frame(Nb)
btm_frame = Tk.Frame(root, bg='gray', bd=2)
statusFrame = Tk.Frame(root)

Nb.add(center, text='OTF search')


# layout all of the main containers
root.grid_rowconfigure(1, weight=1)
root.grid_columnconfigure(0, weight=1)

#top_frame.grid(row=0, sticky="ew")
Nb.grid(row=0, sticky="ew", padx=20, pady=10)
btm_frame.grid(row = 1, sticky="ew")
statusFrame.grid(row = 2, sticky="ew")

channel_data = str()

# center widgets

leftLabels = ['Input File', 'Selected Channels:', 'Max OTF age(day):', 'Max number OTFs:', 'Crop Size (px):', 
			'Oil Min RI:', 'Oil Max RI:', 'OTF Directory:', 'SIRconfig Dir:', 'Register Channels:', 
			'Registration File:','Reference Channel:','Do Max Projection:']
for i in range(len(leftLabels)):
	Tk.Label(center, text=leftLabels[i]).grid(row=i, sticky='E')

allwaves=C.valid['waves']
channelSelectBoxes={}
channelSelectVars={}
for i in range(len(allwaves)):
	channelSelectVars[allwaves[i]]=Tk.IntVar()
	channelSelectVars[allwaves[i]].set(0)
	channelSelectBoxes[allwaves[i]]=Tk.Checkbutton(center)
	channelSelectBoxes[allwaves[i]].config(variable=channelSelectVars[allwaves[i]], text=str(allwaves[i]), state='disabled')
	channelSelectBoxes[allwaves[i]].grid(row=1, column=i+1, sticky='W')

rawFilePath = Tk.StringVar()
rawFileEntry = Tk.Entry(center, textvariable=rawFilePath, width=48).grid(row=0, columnspan=6, column=1, sticky='W')
chooseFileButton = Tk.Button(center, text ="Choose File", command = getRawFile).grid(row=0, column=7, ipady=3, ipadx=10, padx=2)

maxOTFage = Tk.StringVar()
maxOTFage.set(C.maxAge if C.maxAge is not None else '')
maxOTFageEntry = Tk.Entry(center, textvariable=maxOTFage, width=6).grid(row=2, column=1, sticky='W')
Tk.Label(center, text="(leave blank for no limit)").grid(row=2, column=2, columnspan=4, sticky='W')

maxOTFnum = Tk.StringVar()
maxOTFnum.set(C.maxNum if C.maxNum is not None else '')
maxOTFnumEntry = Tk.Entry(center, textvariable=maxOTFnum, width=6).grid(row=3, column=1, sticky='W')
Tk.Label(center, text="(leave blank for no limit)").grid(row=3, column=2, columnspan=4, sticky='W')

cropsize = Tk.StringVar()
cropsize.set(C.cropsize)
cropsizeEntry = Tk.Entry(center, textvariable=cropsize, width=6).grid(row=4, column=1, sticky='W')
Tk.Label(center, text="(make it a power of 2)").grid(row=4, column=2, columnspan=4, sticky='W')

OilMin = Tk.StringVar()
OilMin.set(C.oilMin)
OilMinEntry = Tk.Entry(center, textvariable=OilMin, width=6).grid(row=5, column=1, sticky='W')

OilMax = Tk.StringVar()
OilMax.set(C.oilMax)
OilMaxEntry = Tk.Entry(center, textvariable=OilMax, width=6).grid(row=6, column=1, sticky='W')

OTFdir = Tk.StringVar()
OTFdirEntry = Tk.Entry(center, textvariable=OTFdir, width=48).grid(row=7, column=1, columnspan=6, sticky='W')
chooseOTFdirButton = Tk.Button(center, text ="Choose File", command = getOTFdir).grid(row=7, column=7, ipady=3, ipadx=10, padx=2)
OTFdir.set( C.OTFdir )

SIRconfigDir = Tk.StringVar()
SIRconfigDirEntry = Tk.Entry(center, textvariable=SIRconfigDir, width=48).grid(row=8, column=1, columnspan=6, sticky='W')
chooseSIRconfigdirButton = Tk.Button(center, text ="Choose File", command = getSIRconfigDir).grid(row=8, column=7, ipady=3, ipadx=10, padx=2)
SIRconfigDir.set( C.SIconfigDir )

doReg = Tk.IntVar()
doReg.set(C.doReg)
doRegButton = Tk.Checkbutton(center, variable=doReg).grid(row=9, column=1, sticky='W')

RegFile = Tk.StringVar()
RegFileEntry = Tk.Entry(center, textvariable=RegFile, width=48).grid(row=10, column=1, columnspan=6, sticky='W')
chooseRegFileButton = Tk.Button(center, text ="Choose File", command = getRegFile).grid(row=10, column=7, ipady=3, ipadx=10, padx=2)
RegFile.set( C.regFile )

RefChannel = Tk.StringVar()
RefChannel.set(C.refChannel)
RefChannelEntry = Tk.Entry(center, textvariable=RefChannel, width=6).grid(row=11, column=1, sticky='W')
Tk.Label(center, text="(435,477,528,541,608, or 683)").grid(row=11, column=2, columnspan=4, sticky='W')

doMax = Tk.IntVar()
doMax.set(C.doMax)
doMaxButton = Tk.Checkbutton(center, variable=doMax).grid(row=12, column=1, sticky='W')

Tk.Button(center, text ="Reconstruct", command = doit, width=12).grid(row=13, column=1, columnspan=2,ipady=8, ipadx=8, pady=8, padx=8)
Tk.Button(center, text ="Quit", command = quit, width=12).grid(row=13, column=4, columnspan=2,ipady=8, ipadx=8, pady=8, padx=8)

textArea = ScrolledText(btm_frame)
textArea.config(height=10)
textArea.pack(side='bottom', fill='x')

statusTxt = Tk.StringVar()
statusBar = Tk.Label(statusFrame, textvariable=statusTxt, bd=1, relief='sunken', anchor='w', background='gray')
statusBar.pack(side='bottom', fill='x')

root.mainloop()