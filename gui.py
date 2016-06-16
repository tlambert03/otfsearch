"""Tkinter-based GUI for OTF-searching workflow."""

import Tkinter as Tk
import tkFileDialog
import tkMessageBox
import sys
import config as C
import os
from __init__ import isRawSIMfile
from ScrolledText import ScrolledText
from ttk import Notebook, Style
import threading
from functools import partial
from ast import literal_eval
import socket
import time

try:
	import paramiko
except ImportError as e:
	print 'paramiko not installed'
	print 'Please install paramiko by typing "pip install paramiko" in terminal'
	sys.exit()
try:
	import Mrc
except ImportError as e:
	print 'This program requires the Mrc.py class file for reading .dv files'
	sys.exit()

sftp = ''
Server = {
	'busy' : False,
	'connected' : False,
	'currentFile' : None,
	'progress' : (0,0),
	'status' : None, # transferring, putDone, getDone, processing, canceled
}


def make_connection(host=None, user=None):
	"""Open connection to ssh server with paramiko."""
	if not host: host = server.get()
	if not user: user = username.get()
	statusTxt.set("connecting to " + host + "...")
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	# is this necessary?
	# hostkey = os.path.expanduser(os.path.join("~", ".ssh", "known_hosts"))
	# try:
	# 	ssh.load_host_keys(hostkey)
	# except IOError as e:
	# 	statusTxt.set(e)
	# 	return 0
	try:
		ssh.connect(host, username=user)
		statusTxt.set("connected to " + host)
		Server['connected']=True
	except socket.gaierror as e:
		# bad server name?
		tkMessageBox.showinfo('Connection Failed!', "bad servername?:\n " + host)
		return 0
	except paramiko.PasswordRequiredException as e:
		# bad username?
		tkMessageBox.showinfo('Connection Failed!', "bad username?\n " + user)
		return 0
	except paramiko.AuthenticationException as e:
		# bad password/hostkey?
		tkMessageBox.showinfo(
			'Connection Failed!',
			"Authentication error: no password/hostkey?")
		return 0
	except Exception as e:
		print e
		tkMessageBox.showinfo('Connection Failed!', e)
		return 0
	return ssh

def reset_server():
	#if ssh: ssh.close()
	#Server['connected'] = False
	Server['busy'] = False
	Server['currentFile'] = None
	Server['status'] = None

def test_connect():
	"""Test connection to ssh server and provide feedback."""
	if make_connection():
		tkMessageBox.showinfo('Yay!', '%s\nConnection successfull!' % server.get())
	else:
		statusTxt.set('Aw snap.', '%s\nConnection failed!' % server.get())


def upload(file, remotepath, mode):
	"""
	Start a thread for sftp.put.

	The 'mode' command is passed to the updateTranserStatus function
	to determine which command gets sent to the server after upload
	"""
	if not Server['busy']:
		# start thread with sftp_put
		thr = threading.Thread(target=sftp_put, args=(file, remotepath))
		Server['status'] = 'uploading'
		Server['busy'] = True
		thr.start()
		remotefile = os.path.join(remotepath, os.path.basename(file))
		# then hand control to upload_watcher loop and 
		# wait for the appropriate server response
		root.after(200, upload_watcher, (remotefile, mode))
	else:
		print "SERVER NOT READY FOR UPLOAD"

# this is on a separate THREAD
def sftp_put(infile, remotepath):
	"""Use paramiko sftp to upload infile to remotepath."""
	global Server
	ssh = make_connection()
	sftp = ssh.open_sftp()
	remotefile = os.path.join(remotepath, os.path.basename(infile))
	# if the file already exists on the server, don't upload
	if os.path.basename(remotefile) in sftp.listdir(remotepath) and \
		sftp.stat(remotefile).st_size == os.stat(infile).st_size:
			statusTxt.set("File already exists on remote server...")
			print "File already exists on remote server..."
	else: # otherwise upload the file
		sys.stdout.write("Uploading: %s ... " % infile)
		statusTxt.set("copying to server...")
		Server['currentFile'] = os.path.basename(remotefile)
		sftp.put(infile, remotefile, callback=sftp_progress)
		print 'done!'
	# in either case, after the file is on the server
	# change the server status
	sftp.close()
	ssh.close()
	Server['status'] = 'putDone'
	Server['busy'] = False

# this is on a separate THREAD
def sftp_progress(transferred, outof):
	"""Update global sentinel variable with sftp progress."""
	global Server
	Server['progress'] = (transferred, outof)

def download(filelist):
	"""Start a thread for sftp.get."""
	try:
		statusTxt.set("Downloading files from server... ")
		thr = threading.Thread(target=sftp_get, args=(filelist,))
		Server['status'] = 'downloading'
		Server['busy'] = True
		thr.start()
		root.after(200, download_watcher, (filelist,))
	except Exception as e:
		print("Error at downloading files!")
		print(e)


# this is on a separate THREAD
def sftp_get(filelist):
	"""Use paramiko sftp to download a list of files."""
	# statusTxt.set( "Downloading files...")
	global Server
	ssh = make_connection()
	sftp = ssh.open_sftp()
	for f in filelist:
		sys.stdout.write("Downloading: %s ... " % f)
		Server['currentFile'] = os.path.basename(f)
		# local download path pulled from current rawpath
		# this could lead to problems if the user changes 
		# it in the meantime...
		localpath = os.path.dirname(rawFilePath.get())
		sftp.get(f, os.path.join(localpath, os.path.basename(f)), callback=sftp_progress)
		print("done!")
	sftp.close()
	ssh.close()
	Server['status'] = 'getDone'


def upload_watcher(tup):
	"""
	Update status bar with file transfer progress.

	This function servers as a checkpoint for sftp_put and sftp_get and
	yields control to send a command to process files when ready.

	tup == (remote file, mode) ( where mode = single | optimal | registerCal).
	"""

	if Server['status'] == 'canceled':
		statusTxt.set("Process canceled... closing server connection")
		# not doing anything here lets the process die...
		# but won't stop any current uploads/downloads

	elif Server['status'] == 'uploading':
		statusTxt.set("Uploading %s: %0.1f of %0.1f MB" %
			(Server['currentFile'], float(Server['progress'][0]) / 
				1000000, float(Server['progress'][1]) / 1000000))
		root.after(200, upload_watcher, tup)

	elif Server['status'] == 'putDone':
		statusTxt.set("Upload finished...")
		print "Sending '%s' command to server" % tup[1]
		send_command(tup[0], tup[1])

	else:
		pass



def download_watcher(tup):
	"""
	Update status bar with file transfer progress.

	This function servers as a checkpoint for sftp_put and sftp_get and
	yields control to send a command to process files when ready.

	tup == (remote file, mode) ( where mode = single | optimal | registerCal).
	"""
	global Server

	if Server['status'] == 'canceled':
		statusTxt.set("Process canceled... closing server connection")
		# not doing anything here lets the process die...
		# but won't stop any current uploads/downloads

	elif Server['status'] == 'downloading':
		statusTxt.set("Downloading %s: %0.1f of %0.1f MB" %
			(Server['currentFile'], float(Server['progress'][0]) / 
				1000000, float(Server['progress'][1]) / 1000000))
		root.after(200, download_watcher, tup)

	elif Server['status'] == 'getDone':
		statusTxt.set("Download finished... Best OTFs copied to Specify OTFs tab")
		Server['busy'] = False
		Server['currentFile'] = None
		# this is likely the completion of the entire loop...

	else:
		pass


def send_command(remotefile, mode):
	"""Send one of the commands above to the server."""

	Server['busy'] = True
	Server['status'] = 'processing'

	if mode == 'registerCal':
		command = ['python', C.remoteRegCalibration, remotefile, '--outpath', C.regFileDir]
		if calibrationIterations.get(): command.extend(['--iter', calibrationIterations.get()])
	
	elif mode == 'single':
		command = ['python', C.remoteSpecificScript, remotefile,
					'--regfile', RegFile.get(), '-r', RefChannel.get()]
		if wiener.get().strip():
			command.extend(['-w', wiener.get()])
		if timepoints.get().strip():
			command.extend(['-t', timepoints.get()])
		selected_channels = [key for key, val in channelSelectVars.items() if val.get() == 1]
		for c in selected_channels:
			command.extend(['-o', "=".join([str(c), channelOTFPaths[c].get()])])
		if doMax.get(): command.append('-x')
		if doReg.get(): command.append('-g')

	elif mode == 'optimal':
		command = ['python', C.remoteOptScript, remotefile, '-l', OilMin.get(),
					'-m', OilMax.get(), '-p', cropsize.get(), '--otfdir', OTFdir.get(),
					'--regfile', RegFile.get(), '-r', RefChannel.get(),
					'-x', doMax.get(), '-g', doReg.get()]
		if maxOTFage.get().strip():
			command.extend(['-a', maxOTFage.get()])
		if maxOTFnum.get().strip():
			command.extend(['-n', maxOTFnum.get()])
		selected_channels = [key for key, val in channelSelectVars.items() if val.get() == 1]
		if selected_channels:
			command.extend(['-c', " ".join([str(n) for n in sorted(selected_channels)])])
		# if not all([k==v.get() for k,v in forceChannels.items() if k in selected_channels]):
		# if any of the channel:otf pairings have been changed
		for c in selected_channels:
			# build the "force channels" commands
			if not c == forceChannels[c].get():
				command.extend(['-f', "=".join([str(c), str(forceChannels[c].get())])])

	else:
		raise ValueError('Uknown command mode: %s' % mode)

	ssh = make_connection()
	channel = ssh.invoke_shell()
	statusTxt.set("Sending command to remote server...")
	# send the command to the server
	channel.send(" ".join([str(s) for s in command]) + '\n')
	
	def receive_command_response(ssh):

		if Server['status'] == 'canceled':
			statusTxt.set("Process canceled...")
			#reset_server()
			return 0

		elif Server['status'] == 'processing':
			if channel.recv_ready():
				# if there's something waiting in the queue, read it
				response = channel.recv(2048)

				if response != '': 
					statusTxt.set("Receiving feedback from server ... see text area above for details.")
					r = [r for r in response.splitlines() if r and r != '']
					textArea.insert(Tk.END, "\n".join(r))
					textArea.insert(Tk.END, "\n")
					textArea.yview(Tk.END)

					if 'Best OTFs:' in r:
						otfdict = r[r.index('Best OTFs:') + 1]
						if not isinstance(otfdict, dict):
							otfdict = literal_eval(otfdict)
						if isinstance(otfdict, dict):
							for k, v in otfdict.items():
								channelOTFPaths[int(k)].set(v)
								print "Best OTF for %s: %s" %(k,v)
								statusTxt.set("Best OTFs added to 'Specific OTFs' tab")
					
					if 'Files Ready:' in r:
						i = r.index('Files Ready:') + 1
						filelist = []
						while not r[i].startswith('Done'):
							filelist.append(r[i].split(": ")[1])
							i += 1
						if len(filelist):
							download(filelist)
						# this is where this loop ends... 
						return
				
				if response.endswith(':~$ '):
					if 'OTFs' not in statusTxt.get():
						statusTxt.set("Done")

				
				elif response.endswith("File doesn't appear to be a raw SIM file... continue?"):
					statusTxt.set("Remote server didn't recognize file as raw SIM file and quit")
				
				else:
					# response was empty...
					root.after(300, receive_command_response, ssh)

			else:
				# if there's nothing ready to receive, wait another second
				root.after(300, receive_command_response, ssh)

		else:
			print('Unexpected server status: %s' % Server['status'])
			raise ValueError('Unexpected server status: %s' % Server['status'])

	root.after(300, receive_command_response, ssh)



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


def entriesValid(silent=False):
	errors=[]
	if maxOTFnum.get():
		if not maxOTFnum.get().isdigit():
			errors.append(["Optimized Reconstruction Input Error","Max number of OTFs must be a positive integer (or blank)"])
	if maxOTFage.get():
		if not maxOTFage.get().isdigit():
			errors.append(["Optimized Reconstruction Input Error","Max OTF age must be a positive integer (or blank)"])
	if not OilMin.get().isdigit() or not int(OilMin.get()) in C.valid['oilMin']:
		errors.append(["Optimized Reconstruction Input Error","Oil min must be an integer between 1510 and 1530"])
	if not OilMax.get().isdigit() or not int(OilMax.get()) in C.valid['oilMax']:
		errors.append(["Optimized Reconstruction Input Error","Oil max must be an integer between 1510 and 1530"])
	if not cropsize.get().isdigit() or not int(cropsize.get()) in C.valid['cropsize']:
		errors.append(["Optimized Reconstruction Input Error","Cropsize must be a power of 2 <= 512"])
	if doReg.get():
		waves = [i for i in Mrc.open(rawFilePath.get()).hdr.wave if i != 0]
		if not int(RefChannel.get()) in waves:
			errors.append(["Registration Settings Error","Reference channel must be one of the following:" + " ".join([str(w) for w in waves])])
		if not RegFile.get().strip():
			errors.append(["Registration File Error","Please select a registration file in the registration tab"])

		try: 
			regwaves = os.path.basename(RegFile.get()).split('waves')[1].split('_')[0].split('-')
			# could potentially try to read the matlab file directly with something like:
			# import scipy.io
			# mat = scipy.io.loadmat(RegFile.get())
			# regwaves = mat.get('R')[0][0][6][0][0][0][0]
			if not RefChannel.get() in regwaves:
				errors.append(["Registration File Error","The selected reference channel does not exist in the registration file. Please either change the registration file or the reference channel"])
		except:
			errors.append(["Registration File Error","Cannot parse registration file name... for now, the filename must include 'waves_'... etc"])
		
	selectedchannels = [key for key, val in channelSelectVars.items() if val.get() == 1]
	if len(selectedchannels) == 0:
		errors.append(["Input Error","You must select at least one channel to reconstruct:"])
	if len(errors):
		if not silent:
			[tkMessageBox.showinfo(*error) for error in errors]
		return 0,errors
	else:
		return 1,errors


def getOTFdir():
	filename = tkFileDialog.askdirectory()
	if filename:
		OTFdir.set(filename)


def getSIRconfigDir():
	filename = tkFileDialog.askdirectory()
	if filename:
		SIRconfigDir.set(filename)


def getbatchDir():
	filename = tkFileDialog.askdirectory()
	if filename:
		batchDir.set(filename)


def getRegFile():
	ssh = make_connection()
	sftp = ssh.open_sftp()
	reglist = sorted([item for item in sftp.listdir(C.regFileDir) if item.endswith('.mat')])

	top = Tk.Toplevel()
	top.title('Choose registration file')
	scrollbar = Tk.Scrollbar(top)
	scrollbar.grid(row=0, column=3, sticky='ns')

	lb = Tk.Listbox(top, yscrollcommand=scrollbar.set, height=18, width=45)

	for item in reglist:
		lb.insert(Tk.END, os.path.basename(item))
	lb.grid(row=0, column=0, columnspan=3)

	scrollbar.config(command=lb.yview)

	def Select():
		items = lb.curselection()

		item = [reglist[int(item)] for item in items][0]

		if item:
			RegFile.set(os.path.join(C.regFileDir, item))
		top.destroy()

	selectButton = Tk.Button(top, text="Select", command=Select, pady=6, padx=10)
	selectButton.grid(row=1, column=0)

	cancelButton = Tk.Button(top, text="Cancel", command=lambda: top.destroy(), pady=6, padx=10)
	cancelButton.grid(row=1, column=1)

	top.update_idletasks()
	w = top.winfo_screenwidth()
	h = top.winfo_screenheight()
	size = tuple(int(_) for _ in top.geometry().split('+')[0].split('x'))
	x = w / 2 - size[0] / 2
	y = h / 2 - size[1] / 1.3
	top.geometry("%dx%d+%d+%d" % (size + (x, y)))
	top.resizable(0, 0)


def quit():
	"""Quit the program."""
	root.destroy()

def cancel():
	"""Cancel the current activity."""
	print("Cancel button pressed.")
	global Server
	if Server['status'] and Server['status'] != 'canceled':
		statusTxt.set("Process canceled!")
		textArea.insert(Tk.END, "Process canceled...\n\n")
	Server['status'] = 'canceled'
	Server['busy'] = False
	# could be more agressiver here and close ssh

def runReconstruct(mode):
	inputfile = rawFilePath.get()
	if not os.path.exists(inputfile):
		tkMessageBox.showinfo("Input file Error", "Input file does not exist")
		return 0
	if not isRawSIMfile(inputfile):
		response = tkMessageBox.askquestion("Input file Error", "Input file doesn't appear to be a raw SIM file... Do it anyway?")
		if response == "no":
			return 0
	V = entriesValid()
	if V[0]:
		upload(inputfile, C.remotepath, mode)
	else:
		textArea.insert(Tk.END, "Invalid settings!\n")
		[textArea.insert(Tk.END, ": ".join(e) + "\n" ) for e in V[1]]
		textArea.insert(Tk.END, "\n")
		return 0


def get_git_revision_short_hash():
	import subprocess
	os.chdir(os.path.dirname(os.path.realpath(__file__)))
	return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'])

root = Tk.Tk()
root.title('CBMF SIM Reconstruction Tool v.%s' % get_git_revision_short_hash())

top_frame = Tk.Frame(root)

Nb = Notebook(root)
Style().theme_use('clam')

otfsearchFrame = Tk.Frame(Nb)
singleReconFrame = Tk.Frame(Nb)
serverFrame = Tk.Frame(Nb)
batchFrame = Tk.Frame(Nb)
registrationFrame = Tk.Frame(Nb)
helpFrame = Tk.Frame(Nb)

Nb.add(otfsearchFrame, text='Optimized Reconstruction')
Nb.add(singleReconFrame, text='Specify OTFs')
Nb.add(registrationFrame, text='Channel Registration')
Nb.add(batchFrame, text='Batch')
Nb.add(serverFrame, text='Server')
Nb.add(helpFrame, text='Help')

textAreaFrame = Tk.Frame(root, bg='gray', bd=2)
statusFrame = Tk.Frame(root)


top_frame.grid(row=0, pady=10)
Nb.grid(row=1, padx=15, pady=5)
textAreaFrame.grid(row=2, sticky="nsew", padx=15, pady=10)
statusFrame.grid(row=3, sticky="ew")


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
doRegButton = Tk.Checkbutton(top_frame, variable=doReg,
	text='Do registration', command=lambda e=RefChannelEntry, v=doReg: naccheck(e,v))
doRegButton.grid(row=2, column=2, columnspan=2, sticky='W')

doMax = Tk.IntVar()
doMax.set(C.doMax)
doMaxButton = Tk.Checkbutton(top_frame, variable=doMax, text='Do max projection')
doMaxButton.grid(row=2, column=4, columnspan=2, sticky='W')


quitButton = Tk.Button(top_frame, text="Quit", command=quit, width=9)
quitButton.grid(row=1, column=7, ipady=3, ipadx=10, padx=2)

quitButton = Tk.Button(top_frame, text="Cancel", command=cancel, width=9)
quitButton.grid(row=2, column=7, ipady=3, ipadx=10, padx=2)


# OTF search tab widgets

leftLabels = ['Max OTF age (days):', 'Max number OTFs:', 'Crop Size (pix):',
	'Min Oil RI:', 'Max Oil RI:']
for i in range(len(leftLabels)):
	Tk.Label(otfsearchFrame, text=leftLabels[i]).grid(row=i, sticky='E')

maxOTFage = Tk.StringVar()
maxOTFage.set(C.maxAge if C.maxAge is not None else '')
maxOTFageEntry = Tk.Entry(otfsearchFrame, textvariable=maxOTFage)
maxOTFageEntry.grid(row=0, column=1, columnspan=3, sticky='W')

maxOTFnum = Tk.StringVar()
maxOTFnum.set(C.maxNum if C.maxNum is not None else '')
maxOTFnumEntry = Tk.Entry(otfsearchFrame, textvariable=maxOTFnum)
maxOTFnumEntry.grid(row=1, column=1, columnspan=3, sticky='W')

cropsize = Tk.StringVar()
cropsize.set(C.cropsize)
cropsizeEntry = Tk.Entry(otfsearchFrame, textvariable=cropsize)
cropsizeEntry.grid(row=2, column=1, columnspan=3, sticky='W')

OilMin = Tk.StringVar()
OilMin.set(C.oilMin)
OilMinEntry = Tk.Entry(otfsearchFrame, textvariable=OilMin)
OilMinEntry.grid(row=3, column=1, columnspan=3, sticky='W')

OilMax = Tk.StringVar()
OilMax.set(C.oilMax)
OilMaxEntry = Tk.Entry(otfsearchFrame, textvariable=OilMax)
OilMaxEntry.grid(row=4, column=1, columnspan=3, sticky='W')


Tk.Button(otfsearchFrame, text="Run OTF Search",
	command=partial(runReconstruct, 'optimal'), width=12).grid(row=8,
	column=1, columnspan=3, ipady=8, ipadx=8, pady=8, padx=8)

forceChannels = {}
forceChannelsMenus = {}
Tk.Label(otfsearchFrame, text="Force specific images channel:OTF pairings",
	font=('Arial', 12, 'bold')).grid(row=0, column=5, columnspan=3,
	sticky='w', padx=(20, 0))

for i in range(len(allwaves)):
	Tk.Label(otfsearchFrame, text="OTF to use for channel %s:" % allwaves[i]).grid(row=i + 1,
		column=5, sticky='E', padx=(40, 0))
	forceChannels[allwaves[i]] = Tk.IntVar()
	forceChannels[allwaves[i]].set(allwaves[i])
	forceChannelsMenus[allwaves[i]] = Tk.OptionMenu(otfsearchFrame,
		forceChannels[allwaves[i]], *allwaves)
	forceChannelsMenus[allwaves[i]].grid(row=i + 1, column=6, sticky='w')


# SINGLE RECON TAB


Tk.Label(singleReconFrame, text='Wiener constant:').grid(row=0, sticky='e')
wiener = Tk.StringVar()
wiener.set(C.wiener)
wienerEntry = Tk.Entry(singleReconFrame, textvariable=wiener, width=15)
wienerEntry.grid(row=0, column=1, sticky='W')

Tk.Label(singleReconFrame, text='Timepoints:').grid(row=0, column=2, sticky='e')
timepoints = Tk.StringVar()
timepoints.set('')
timepointsEntry = Tk.Entry(singleReconFrame, textvariable=timepoints, width=15)
timepointsEntry.grid(row=0, column=3, sticky='W')


for i in range(len(allwaves)):
	Tk.Label(singleReconFrame, text=str(allwaves[i]) + "nm OTF: ").grid(row=i + 1, sticky='E')

def getChannelOTF(var):

	ssh = make_connection()
	sftp = ssh.open_sftp()
	otflist = sorted([item for item in sftp.listdir(OTFdir.get()) if item.endswith('.otf')])
	selectedlist = [item for item in otflist if item.startswith(str(var))]
	fullist=0

	top = Tk.Toplevel()
	top.title('Choose OTF for %d' % var)
	scrollbar = Tk.Scrollbar(top)
	scrollbar.grid(row=0, column=3, sticky='ns')

	lb = Tk.Listbox(top, yscrollcommand=scrollbar.set, height=18, width=28)
	
	for item in selectedlist:
		lb.insert(Tk.END, os.path.basename(item))
	lb.grid(row=0, column=0, columnspan=3)

	scrollbar.config(command=lb.yview)

	def Select():
		items = lb.curselection()
		if fullist:
			item = [otflist[int(item)] for item in items][0]
		else:
			item = [selectedlist[int(item)] for item in items][0]
		if item:
			channelOTFPaths[var].set(os.path.join(OTFdir.get(), item))
		top.destroy()

	def ShowAll():
		lb.delete(0, 'end')
		for item in otflist:
			lb.insert(Tk.END, os.path.basename(item))
		fullist = 1

	def cancelOTF():
		top.destroy()

	selectButton = Tk.Button(top, text="Select",command=Select, pady=6, padx=10)
	selectButton.grid(row=1, column=0)

	cancelButton = Tk.Button(top, text="ShowAll",command=ShowAll, pady=6, padx=10)
	cancelButton.grid(row=1, column=2)

	cancelButton = Tk.Button(top, text="Cancel",command=cancelOTF, pady=6, padx=10)
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
		regCalImage.set(filename )


def sendRegCal():
	inputfile = regCalImage.get()
	if not os.path.exists(inputfile):
		tkMessageBox.showinfo("Input file Error", "Registration calibration image doesn't exist")
		return 0
	upload(inputfile, C.remotepath, 'registerCal')


Tk.Label(registrationFrame, text='Apply registration to image file', font=('Arial', 13, 'bold')).grid(row=0, columnspan=4, sticky='w')

Tk.Label(registrationFrame, text='Registration File:').grid(row=1, sticky='e')
RegFile = Tk.StringVar()
RegFileEntry = Tk.Entry(registrationFrame, textvariable=RegFile, width=43).grid(row=1, column=1, columnspan=6, sticky='W')
chooseRegFileButton = Tk.Button(registrationFrame, text ="Choose File", command = getRegFile).grid(row=1, column=3, ipady=3, ipadx=10, padx=2, sticky='w')
RegFile.set( C.regFile )

Tk.Label(registrationFrame, text='Calibrate registration', font=('Arial', 13, 'bold')).grid(row=2, columnspan=4, sticky='w',pady=(20,0))

Tk.Label(registrationFrame, text='Calibration Image:').grid(row=3, sticky='e')
regCalImage = Tk.StringVar()
regCalImageEntry = Tk.Entry(registrationFrame, textvariable=regCalImage, width=43).grid(row=3, column=1, columnspan=5, sticky='W')
chooseregCalImageButton = Tk.Button(registrationFrame, text ="Choose Image", command = getregCalImage).grid(row=3, column=3, ipady=3, ipadx=10, padx=2, stick='w')

Tk.Label(registrationFrame, text='Iterations:').grid(row=4, sticky='e')
calibrationIterations = Tk.IntVar()
calibrationIterationsEntry = Tk.Entry(registrationFrame, textvariable=calibrationIterations, width=43).grid(row=4, column=1, columnspan=2, sticky='W')
sendregCalImageButton = Tk.Button(registrationFrame, text ="Calibrate", command = sendRegCal).grid(row=4, column=3, columnspan=2, ipady=3, ipadx=10, padx=2, sticky='w')
calibrationIterations.set(C.CalibrationIter)

# CONFIG TAB

Tk.Label(serverFrame, text='OTF Directory:').grid(row=0, sticky='e')
OTFdir = Tk.StringVar()
OTFdirEntry = Tk.Entry(serverFrame, textvariable=OTFdir, width=48).grid(row=0, column=1, columnspan=6, sticky='W')
#chooseOTFdirButton = Tk.Button(serverFrame, text ="Choose Dir", command = getOTFdir).grid(row=0, column=7, ipady=3, ipadx=10, padx=2)
OTFdir.set(C.OTFdir )

Tk.Label(serverFrame, text='SIR config Dir:').grid(row=1, sticky='e')
SIRconfigDir = Tk.StringVar()
SIRconfigDirEntry = Tk.Entry(serverFrame, textvariable=SIRconfigDir, width=48).grid(row=1, column=1, columnspan=6, sticky='W')
#chooseSIRconfigdirButton = Tk.Button(serverFrame, text ="Choose Dir", command = getSIRconfigDir).grid(row=1, column=7, ipady=3, ipadx=10, padx=2)
SIRconfigDir.set( C.SIconfigDir )

Tk.Label(serverFrame, text='Server Address:').grid(row=3, sticky='e')
server = Tk.StringVar()
serverEntry = Tk.Entry(serverFrame, textvariable=server, width=48).grid(row=3, column=1, columnspan=6, sticky='W')
server.set( C.server )

Tk.Label(serverFrame, text='Username:').grid(row=4, sticky='e')
username = Tk.StringVar()
usernameEntry = Tk.Entry(serverFrame, textvariable=username, width=48).grid(row=4, column=1, columnspan=6, sticky='W')
username.set( C.username )


Tk.Button(serverFrame, text="Test Connection", command=test_connect,
	width=12).grid(row=5, column=1, columnspan=2, ipady=6, ipadx=6, sticky='w')


# BATCH TAB

Tk.Label(batchFrame, text='Directory:').grid(row=0, sticky='e')
batchDir = Tk.StringVar()
batchDirEntry = Tk.Entry(batchFrame, textvariable=batchDir, width=50).grid(row=0, column=1, columnspan=6, sticky='W')
batchDirButton = Tk.Button(batchFrame, text ="Choose Dir", command = getbatchDir).grid(row=0, column=7, ipady=3, ipadx=10, padx=2)


def dobatch(mode):
	"""Start batch job.

	mode can be one of 'optimal', 'single', or 'register'
	and will perform the corresponding task on the provided
	batch folder
	"""
	global Server

	if Server['status'] == 'canceled':
		Server['status'] = None # this is here in case the last button pressed was cancel

	batchlist = []
	directory = batchDir.get()
	if not directory:
		tkMessageBox.showinfo('No batch directory!', 'Please chose a directory for batch reconstruction')
		return 0
	for R, S, F in os.walk(directory):
		for file in F:
			fullpath = os.path.join(R, file)
			if isRawSIMfile(fullpath):
				batchlist.append(fullpath)

	def callback(mode):

		if Server['busy']:
			root.after(700, callback, mode)
		else:
			if Server['status'] == 'canceled':
				statusTxt.set("Batch job canceled... closing server connection")
				#reset_server()
				return 0

			elif Server['status'] == None or Server['status']=='getDone':
				if len(batchlist) == 0:
					print("Batch reconstruction finished")
					statusTxt.set("Batch reconstruction finished")
				else:
					item = batchlist.pop(0)
					setRawFile(item)
					V = entriesValid(silent=True)
					if V[0]:
						print("Current File: %s" % item)
						runReconstruct(mode)
					else:
						print("Invalid settings on file: %s" % item)
						textArea.insert(Tk.END, "Batch job skipping file: %s\n" % item)
						[textArea.insert(Tk.END, ": ".join(e) + "\n" ) for e in V[1]]
						textArea.insert(Tk.END, "\n")
					root.after(600, callback, mode)
			else:
				print("Unexpected server status in batch job: %s" % Server['status'])
				root.after(600, callback, mode)

	if len(batchlist):
		print("Starting batch on: %s" % directory)
		callback(mode)
	else:
		statusTxt.set('No raw SIM files in directory!')




Tk.Button(batchFrame, text="Batch Optimized Recon", command=partial(dobatch, 'optimal')).grid(row=1, column=1, columnspan=3, ipady=6, ipadx=6, sticky='w')
Tk.Button(batchFrame, text="Batch Recon with Specified OTFs", command=partial(dobatch, 'single')).grid(row=1, column=4, columnspan=3, ipady=6, ipadx=6, sticky='e')
Tk.Label(batchFrame, text='(Settings on the respective tabs will be used for batch reconstructions)').grid(row=2, column=1, columnspan=6, sticky='e')

# Help Frame


helpText = ScrolledText(helpFrame, wrap='word')
helpText.pack(fill='both')

helpText.tag_configure("heading", font=('Helvetica', 12, 'bold'))
helpText.tag_configure("paragraph", font=('Helvetica', 10, 'normal'))
helpText.tag_configure("code", font=('Monaco', 10, 'bold'))
helpText.tag_configure("italics", font=('Helvetica', 12, 'italic'))

helpText.insert('insert', 'Input File\n', 'heading')
helpText.insert('insert', 'Select a raw SIM .dv file to process and choose the ', 'paragraph')
helpText.insert('insert', 'Channels ', 'code')
helpText.insert('insert', 'that you would like to include in the reconstructions. ', 'paragraph')
helpText.insert('insert', 'When you open a new file, the channels will be automatically populated based on the available channels in the image. \n', 'paragraph')
helpText.insert('insert', '\n')
helpText.insert('insert', 'Optimized Reconstruction \n', 'heading')
helpText.insert('insert', 'Use this tab to search the folder of OTFs specified on the server tab for the optimal OTF for each channel. ', 'paragraph')
helpText.insert('insert', 'Adjust the OTF search parameters in the optimized reconstruction tab and hit the ', 'paragraph')
helpText.insert('insert', 'Run OTF Search ', 'code')
helpText.insert('insert', 'button. \n', 'paragraph')
helpText.insert('insert', '\n')
helpText.insert('insert', 'Specify OTFs\n', 'heading')
helpText.insert('insert', 'This tab can be used to specifiy OTFs for each channel present in the file, then perform a single reconstruction. \n ', 'paragraph')
helpText.insert('insert', '\n')
helpText.insert('insert', 'Server\n', 'heading')
helpText.insert('insert', 'The Server tab specifies important folders on the server used in the reconstructions. \n ', 'paragraph')
helpText.insert('insert', '\n')
helpText.insert('insert', "If you are getting bugs or unexpected results, don't hesistate to ask for help!\n", 'italics')
helpText.insert('insert', '\n')
helpText.insert('insert', "Created by Talley Lambert, (c) 2016", 'paragraph')

helpText.config(height=17, state='disabled')

# TEXT AREA
textArea = ScrolledText(textAreaFrame)
textArea.config(height=10)
textArea.pack(side='bottom', fill='both')

Tk.Button(textAreaFrame, text="Clear", command=lambda: textArea.delete(1.0, 'end'), relief='flat', padx=7, pady=4).place(
	relx=1.0, rely=1.0, x=-23, y=-5, anchor="se")


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