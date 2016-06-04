import Tkinter as Tk
import tkFileDialog
import tkMessageBox
import sys
import config as C
import os
from __init__ import isRawSIMfile
from ScrolledText import ScrolledText

try:
	import paramiko
except ImportError as e:
	print 'paramiko not installed'
	print 'Please install paramiko by typing "pip install paramiko" in terminal'
	sys.exit()

def transferFile(inputFile, remotepath, server, username):
	statusTxt.set( "connecting to" + C.server + "..." )
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) 
	ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
	try:
		ssh.connect(server, username=username)
	except paramiko.ssh_exception.PasswordRequiredException as e:
		print "Password required"
		print e

	statusTxt.set( "Connection successful, copying: " + os.path.basename(inputFile))
	sftp = ssh.open_sftp()
	try:
		remoteFile=os.path.join(remotepath,os.path.basename(inputFile))
		response = sftp.put(inputFile, remoteFile)
	except:
		statusTxt.set( e )
	statusTxt.set( "File transferred to remote host")
	print(response)

	sftp.close()
	ssh.close()
	return remoteFile


def triggerRemoteOTFsearch(remoteFile):
	statusTxt.set( "sending reconstruction command to host ..." )
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) 
	ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
	try:
		ssh.connect(server, username=username)
	except paramiko.ssh_exception.PasswordRequiredException as e:
		statusTxt.set( "Password required" )
	except paramiko.AuthenticationException:
		statusTxt.set("Authentication failed when connecting to %s" % host)
		sys.exit(1)
	except:
		statusTxt.set("Could not SSH to %s" % host)
		sys.exit(1)


	import os
	print os.path.realpath(__file__)
	statusTxt.set( "Connection successful, copying: " + os.path.basename(inputFile))
	
	# Send the command (non-blocking)
	command = ['python', C.remotescript, remoteFile, '-a', maxOTFage.get(), '-n', maxOTFnum.get(), '-l', oilMin.get(), '-m', oilMax.get(), '-p', 
				cropsize.get() '--otfdir', OTFdir.get(), '--regfile', RegFile.get(), '-r', RefChannel.geT(), '-x', str(doMax.get()), '-g', str(doReg.get())]
	stdin, stdout, stderr = ssh.exec_command(" ".join(command))

	# Wait for the command to terminate
	while not stdout.channel.exit_status_ready():
		# Only print data if there is data to read in the channel
		if stdout.channel.recv_ready():
			rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
			if len(rl) > 0:
				# Print data from stdout
				statusTxt.set(stdout.channel.recv(1024))
				print stdout.channel.recv(1024)

	statusTxt.set("Command done, closing SSH connection")
	ssh.close()


def getRawFile():
	filename = tkFileDialog.askopenfilename()
	rawFilePath.set( filename )
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
	sys.exit()
	#textArea.insert(Tk.END, "lots of text")

def doit():
	inputFile = rawFilePath.get()
	if not os.path.exists(inputFile):
		tkMessageBox.showinfo("Input file Error", "Input file does not exist")
		return 0

	if not isRawSIMfile(inputFile):
		response = tkMessageBox.askquestion("Input file Error", "Input file doesn't appear to be a raw SIM file... Do it anyway?")
		if response == "no":
			return 0

#	tkMessageBox.showinfo("Copying", "Copying...")
	remoteFile = transferFile(inputFile, C.remotepath, C.server, C.username)
	triggerRemoteOTFsearch(remoteFile)


root = Tk.Tk()
root.title('Reconstruction Optimizer')
root.geometry('{}x{}'.format(660, 450))

# create all of the main containers
top_frame = Tk.Frame(root, bg='cyan', width = 450, height=50, pady=3)
center = Tk.Frame(root, bg='white', width=450, height=20, padx=3, pady=3)
btm_frame = Tk.Frame(root, bg='white', width = 450, height = 45, pady=3)
statusFrame = Tk.Frame(root, bg='lavender', width = 450, height = 20, pady=3)

# layout all of the main containers
root.grid_rowconfigure(1, weight=1)
root.grid_columnconfigure(0, weight=1)

#top_frame.grid(row=0, sticky="ew")
center.grid(row=1, sticky="ew", padx=20, pady=10)
#btm_frame.grid(row = 3, sticky="ew")
statusFrame.grid(row = 4, sticky="ew")


# center widgets

Tk.Label(center, text="Raw File:").grid(row=0, sticky='E')
rawFilePath = Tk.StringVar()
rawFileEntry = Tk.Entry(center, textvariable=rawFilePath, width=40).grid(row=0, columnspan=2, column=1)
chooseFileButton = Tk.Button(center, text ="Choose File", command = getRawFile).grid(row=0, column=3, ipady=3, ipadx=10, padx=2)

Tk.Label(center, text="Max OTF age(day):").grid(row=1, sticky='E')
maxOTFage = Tk.StringVar()
maxOTFage.set(C.maxAge)
maxOTFageEntry = Tk.Entry(center, textvariable=maxOTFage, width=15).grid(row=1, column=1, sticky='W')
Tk.Label(center, text="(leave blank for no limit)").grid(row=1, column=2, sticky='W')

Tk.Label(center, text="Max number OTFs:").grid(row=2, sticky='E')
maxOTFnum = Tk.StringVar()
maxOTFnum.set(C.maxNum)
maxOTFnumEntry = Tk.Entry(center, textvariable=maxOTFnum, width=15).grid(row=2, column=1, sticky='W')
Tk.Label(center, text="(leave blank for no limit)").grid(row=2, column=2, sticky='W')

Tk.Label(center, text="Crop Size (px):").grid(row=3, sticky='E')
cropsize = Tk.StringVar()
cropsize.set(C.cropsize)
cropsizeEntry = Tk.Entry(center, textvariable=cropsize, width=15).grid(row=3, column=1, sticky='W')
Tk.Label(center, text="(make it a power of 2)").grid(row=3, column=2, sticky='W')

Tk.Label(center, text="Oil Min RI:").grid(row=4, sticky='E')
OilMin = Tk.StringVar()
OilMin.set(C.oilMin)
OilMin = Tk.Entry(center, textvariable=OilMin, width=15).grid(row=4, column=1, sticky='W')

Tk.Label(center, text="Oil Max RI:").grid(row=5, sticky='E')
OilMax = Tk.StringVar()
OilMax.set(C.oilMax)
OilMax = Tk.Entry(center, textvariable=OilMax, width=15).grid(row=5, column=1, sticky='W')

Tk.Label(center, text="OTF Directory:").grid(row=6, sticky='E')
OTFdir = Tk.StringVar()
OTFdirEntry = Tk.Entry(center, textvariable=OTFdir, width=40).grid(row=6, column=1, columnspan=2, sticky='W')
chooseOTFdirButton = Tk.Button(center, text ="Choose File", command = getOTFdir).grid(row=6, column=3, ipady=3, ipadx=10, padx=2)
OTFdir.set( C.OTFdir )

Tk.Label(center, text="SIRconfig Dir:").grid(row=7, sticky='E')
SIRconfigDir = Tk.StringVar()
SIRconfigDirEntry = Tk.Entry(center, textvariable=SIRconfigDir, width=40).grid(row=7, column=1, columnspan=2, sticky='W')
chooseSIRconfigdirButton = Tk.Button(center, text ="Choose File", command = getSIRconfigDir).grid(row=7, column=3, ipady=3, ipadx=10, padx=2)
SIRconfigDir.set( C.SIconfigDir )

Tk.Label(center, text="Register Channels:").grid(row=8, sticky='E')
doReg = Tk.IntVar()
doReg.set(C.doReg)
doRegButton = Tk.Checkbutton(center, variable=doReg).grid(row=8, column=1, sticky='W')

Tk.Label(center, text="Registration File:").grid(row=9, sticky='E')
RegFile = Tk.StringVar()
RegFileEntry = Tk.Entry(center, textvariable=RegFile, width=40).grid(row=9, column=1, columnspan=2, sticky='W')
chooseRegFileButton = Tk.Button(center, text ="Choose File", command = getRegFile).grid(row=9, column=3, ipady=3, ipadx=10, padx=2)
RegFile.set( C.regFile )

Tk.Label(center, text="Reference Channel:").grid(row=10, sticky='E')
RefChannel = Tk.StringVar()
RefChannel.set(C.refChannel)
RefChannel = Tk.Entry(center, textvariable=RefChannel, width=15).grid(row=10, column=1, sticky='W')
Tk.Label(center, text="(435,477,528,541,608, or 683)").grid(row=10, column=2, sticky='W')

Tk.Label(center, text="Do Max Projection").grid(row=11, sticky='E')
doMax = Tk.IntVar()
doMax.set(C.doMax)
doMaxButton = Tk.Checkbutton(center, variable=doMax).grid(row=11, column=1, sticky='W')

Tk.Button(center, text ="Reconstruct", command = doit, width=12).grid(row=12, column=1, ipady=8, ipadx=8, pady=8, padx=8)
Tk.Button(center, text ="Quit", command = quit, width=12).grid(row=12, column=2, ipady=8, ipadx=8, pady=8, padx=8)



textArea = ScrolledText(btm_frame)
textArea.config(height=2, state='disabled')
textArea.pack(side='bottom', fill='x')


statusTxt = Tk.StringVar()
statusBar = Tk.Label(statusFrame, textvariable=statusTxt, bd=1, relief='sunken', anchor='w')
statusBar.pack(side='bottom', fill='x')

root.mainloop()