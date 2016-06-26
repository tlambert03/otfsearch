<!-- features to add -->
work on cleaning up and formatting response from update_status
save results to master CSV file
add opt-out button for scoring
allow single image registration option without reconstruction
allow to create batch job for just image registration
make regfile optional in gui
allow batch process for max projection only 

add options to channel registration calibration command
make timepoints a string that can accept start:stop:step
add background to single reconstruct
allow option to only do optimized search for first file in batch


<!-- nice but low priority -->
calculate more things for score dict...
	add more raw data indices to score, such as snr? max/min/mean?
give more feedback on raw data to the user
	saturation check
	snr check
	bleaching check
	PSF check??
change cropsize box in gui to option box? -> make it a class
OTF names in specific OTF tab might not need full path
add fourier ring correlation when timelapse data available?
* redo whole thing as Classes *
rethink where stuff goes on configuration tab and others
add more help
consider using a smart regisatration file choice
	create dictionary of regisration files that knows waves, daves, et...
add ability to subsection Z-divs

<!-- bugs -->

prevent registration when only a single channel is selected in a multichannel file
invalid switch for -nimm in makeotf when nimm!=1.515...
