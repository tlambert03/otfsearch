#!/usr/bin/python
# -*- coding: iso-8859-1 -*-

from Tkinter import *
import tkFileDialog
import config as C

class App(Tk):
	def __init__(self,parent):
		Tk.__init__(self,parent)
		self.parent = parent
		self.initialize()

	def initialize(self):

		Label(self, text="Raw File:").grid(row=0, sticky=E)
		Label(self, text="Max OTF age(day):").grid(row=1, sticky=E)
		Label(self, text="Max number OTFs:").grid(row=2, sticky=E)
		Label(self, text="Crop Size (px):").grid(row=3, sticky=E)
		Label(self, text="Oil Min RI:").grid(row=4, sticky=E)
		Label(self, text="Oil Max RI:").grid(row=5, sticky=E)
		Label(self, text="OTF Directory:").grid(row=6, sticky=E)
		Label(self, text="SIRconfig Dir:").grid(row=7, sticky=E)
		Label(self, text="Register Channels:").grid(row=8, sticky=E)
		Label(self, text="Registration File:").grid(row=9, sticky=E)
		Label(self, text="Reference Channel:").grid(row=10, sticky=E)
		Label(self, text="Do Max Projection").grid(row=11, sticky=E)

		self.rawFilePath = StringVar()
		self.rawFileEntry = Entry(self, textvariable=self.rawFilePath, width=40).grid(row=0, column=1)
		self.chooseFileButton = Button(self, text ="Choose File", command = self.getRawFile).grid(row=0, column=2)
		
		self.maxOTFage = StringVar()
		self.maxOTFage.set(C.maxAge)
		self.maxOTFageEntry = Entry(self, textvariable=self.maxOTFage, width=15).grid(row=1, column=1, sticky=W)
		
		self.maxOTFnum = StringVar()
		self.maxOTFnum.set(C.maxNum)
		self.maxOTFnumEntry = Entry(self, textvariable=self.maxOTFnum, width=15).grid(row=2, column=1, sticky=W)

		self.cropsize = StringVar()
		self.cropsize.set(C.cropsize)
		self.cropsizeEntry = Entry(self, textvariable=self.cropsize, width=15).grid(row=3, column=1, sticky=W)
		
		self.OilMin = StringVar()
		self.OilMin.set(C.oilMin)
		self.OilMin = Entry(self, textvariable=self.OilMin, width=15).grid(row=4, column=1, sticky=W)
		
		self.OilMax = StringVar()
		self.OilMax.set(C.oilMax)
		self.OilMax = Entry(self, textvariable=self.OilMax, width=15).grid(row=5, column=1, sticky=W)
		
		self.OTFdir = StringVar()
		self.OTFdirEntry = Entry(self, textvariable=self.OTFdir, width=40).grid(row=6, column=1, sticky=W)
		self.chooseOTFdirButton = Button(self, text ="Choose File", command = self.getOTFdir).grid(row=6, column=2)
		self.OTFdir.set( C.OTFdir )

		self.SIRconfigDir = StringVar()
		self.SIRconfigDirEntry = Entry(self, textvariable=self.SIRconfigDir, width=40).grid(row=7, column=1, sticky=W)
		self.chooseSIRconfigdirButton = Button(self, text ="Choose File", command = self.getSIRconfigDir).grid(row=7, column=2)
		self.SIRconfigDir.set( C.SIconfigDir )

		self.doReg = IntVar()
		self.doReg.set(C.doReg)
		self.doRegButton = Checkbutton(self, variable=self.doReg).grid(row=8, column=1, sticky=W)

		self.RegFile = StringVar()
		self.RegFileEntry = Entry(self, textvariable=self.RegFile, width=40).grid(row=9, column=1, sticky=W)
		self.chooseRegFileButton = Button(self, text ="Choose File", command = self.getRegFile).grid(row=9, column=2)
		self.RegFile.set( C.regFile )

		self.RefChannel = StringVar()
		self.RefChannel.set(C.refChannel)
		self.RefChannel = Entry(self, textvariable=self.RefChannel, width=15).grid(row=10, column=1, sticky=W)
		
		self.doMax = IntVar()
		self.doMax.set(C.doMax)
		self.doMaxButton = Checkbutton(self, variable=self.doMax).grid(row=11, column=1, sticky=W)

		self.doit = Button(self, text ="Choose File", command = self.doit).grid(row=12, column=1)


	def getRawFile(self):
		filename = tkFileDialog.askopenfilename()
		self.rawFilePath.set( filename )
	def getOTFdir(self):
		filename = tkFileDialog.askopenfilename()
		self.OTFdir.set( filename )
	def getSIRconfigDir(self):
		filename = tkFileDialog.askopenfilename()
		self.SIRconfigDir.set( filename )
	def getRegFile(self):
		filename = tkFileDialog.askopenfilename()
		self.maxOTFage.set( filename )


	def doit(self):
		makeBestReconstruction()


if __name__ == "__main__":
	app = App(None)
	app.title('OTF optimizer')
	app.mainloop()