# Ingest Scripts
Inside this directory is a set of scripts that are intended to be used to clean
the data and massage it to fit into Whistler's expected formats. For now, this
is a manual process, but that can be changed in the future. 

## scripts/fix_input_files.py
(I'm using the configuration file: project/ds-connect-init.yaml)

This file uses a special version of the Whistler configuration to find the 
original data sources and data-dictionary files. It then renames long 
column names, cleans up a few inconsistencies and outputs both new versions
of dataset and data-dictionary files.

Some notable changes are:
The new files should be written to new directories, so the actual whistler 
configuration file will need to point to those new files:
	data/ds-connect/updated/dd/demographics.csv
	data/ds-connect/updated/dd/ds-connect-ihq.csv
	data/ds-connect/updated/dsconnect_demographics_20211022.csv
	data/ds-connect/updated/dsconnect_ihq_20211023.csv

* Column names for questions and checkboxes will be given incremental qXXXXX
and vXXXXX for questions and checkboxes respectively (the names will be fixed
length names padded with zeros)

* Aggregated columns will be prefixed with the parent questions name and a 
space. This will make it possible for aggregation to work properly in the 
actual whistler call. However, it should be noted that the aggregation strings
may differ depending on the original values used for the aggregation target
name. 

* Column names with ";" in them are updated to remove the semi colon. This 
is necessary because the semicolon is the seperator used by the data dictionary
portion of whistler for categorical values. 

* Typos and inconsenstencies between data dictionary and dataset are corrected

# scripts/harmonize_dd.py
This script is a one-off script used to build up the initial data harmonization
CSV file used by whistler to build the concept maps necessary to associate 
do the data transformation of the various values in the dataset to those 
formal terminologies from HP and Mondo (among other things). 

Going forward, we should create something a bit more automated to extract 
changes from the live google sheet and update the data current harmonization
CSV itself. This will make updating much cleaner than trying to reuse this 
one. However, it's here for historical purposes and can probably provide 
some example code for when the rewrite happens. 
