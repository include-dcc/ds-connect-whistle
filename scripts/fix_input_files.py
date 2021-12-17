#!/usr/bin/env python

"""Attempt to modify dataset and data-dictionaries to match the expections of 
   the whistler system. This may include: 
    * Stripping out characters that have a specific meaning in data 
      dictionaries (the semicolon)
    * creating more appropriate varnames to suit our needs (these data have 
      full questions as part of the column names) These will be short, 
      incremental column names with formal question used as the description 
      component.

The data we got for DS Connect is a bit difficult to work with since it uses 
very long column names and responses. Because of the way whistle works, those 
would make writing our projectors cumbersome and error prone, so we are 
shortening those columns to something more compact. The original column names 
will be available through the updated dictionaries as well as being part of 
the final FHIR representation. 

There are also some inconsistencies between the dataset and the data-dictionary
which must also be corrected, since the data dictionary plays a central role 
in defining certain parts of the final output. 

The final results of this script will result in a directory which should be 
used for the final whistler run. I've been using the default, which is 
data/ds-connect/updated. The data dictionary updates are written to a sub-
directory named dd inside the updated directory. 

For Check-Box type columns, we are aggregating those using Whistler's 
column aggregation function. The end result for those actual column names
will be:  
agg_varname vXXXXXX - Where agg_varname is the aggregated "question" name 
the vXXXXXX is the simplified checkbox id (v followed by 0-prefixed 
incremental value)
    """

from argparse import ArgumentParser, FileType
from pathlib import Path
from yaml import safe_load
import csv
from copy import deepcopy
from collections import defaultdict
from wstlr.extractor import BuildAggregators, TestAggregatable
import pdb

MAX_COLNAME_SIZE = 40

# Inconsistencies between DD and actual dataset
wonky_colnames = {
    "register_year": "registration_year",
    "How was the diagnosis of Down syndrome made? (Select all that apply.) - Genetic testing in baby after birth (such as chromosome analysis, cytogenomic array, or fluorescence in situ hybridization (FISH))": 
    "How was the diagnosis of Down syndrome made? (Select all that apply.) - Genetic testing in baby after birth (such as chromosome analysis, cytogenomic array, or fluorescence in situ hybridization (FISH)"
}

# Keep track of our new column names
_codes_produced=defaultdict(int)

# Build new column names. Our script uses 'q' long question names and
# 'v' for the columns which represent checkboxes. 
def build_code(prefix, varwidth=6):
    global _codes_produced
    _codes_produced[prefix] += 1
    return f"{prefix}{str(_codes_produced[prefix]).zfill(varwidth)}"


# The original column name's text => variable instance
variable_lookup = {}

# Variable can be either an aggregate variable that contains 2 or
# more Checkbox variables (inside self.values) or an independant
# column. 
# 
# This is largely responsible for generating data dictionary
# entries, and will absorb all aggregated "Check Boxes" into the 
# values field as needed. For independent variables, if there
# were values specified in the original data dictionary, those
# are kept, however, they may be reformatted to match whistler's 
# expecations (code=desc;other_code=other_desc;...)
class Variable:
    def __init__(self, varname, desc, row=None, comment=""):
        self.varname = varname
        self.desc = desc

        self.comment = comment
        self.row = row
        if self.row is not None:
            self.row = deepcopy(row)
        self.translation = {}
        self.values = []

        if row is not None and row['data type'][0:7] == "varchar" and row['valid values'].strip() != "":
            idx = 0
            for value in row['valid values'].strip().split("\n"):
                self.values.append(f"{value}={value}")
                self.translation[value] = value
                idx += 1

    # Provide mechanism for transforming a data value into it's corresponding
    # code (or return value unchanged if it isn't found)
    def translate(self, value):
        if value in self.translation:
            return self.translation[value]
        return value

    # Aggregate in those checkbox columns. For these, we rename them
    # to something easier to work with. 
    def add_value(self, parent, varname):
        newvarname = build_code('v')

        # Colname is what we'll replace the column header with in the actual dataset CSV
        colname = f"{parent} {newvarname}"
        self.values.append(f"{newvarname}={varname}")
        self.translation[varname] = newvarname
        return colname

    @classmethod
    def header(cls, writer):
        writer.writerow(["Field",
                        "Description",
                        "Data Type",
                        "Valid Values",
                        "NULL Allowed",
                        "comment"])

    # Write the data out to the CSV writer
    def writerow(self, writer):
        data_type = ""
        null_allowed = ""
        if self.row is not None:
            data_type = self.row['data type']
            null_allowed = self.row['null allowed']
        writer.writerow([
            self.varname, 
            self.desc,
            data_type,
            ";".join(self.values),
            null_allowed,
            self.comment
        ])

parser = ArgumentParser()
parser.add_argument("config",
                    type=FileType('rt', encoding='utf-8-sig'),
                    nargs=1,
                    help="YAML file containing configuration details")
parser.add_argument("-o",
                    "--output",
                    default='data/ds-connect/updated')
args = parser.parse_args()

config = safe_load(args.config[0])
output_directory = Path(args.output)
output_directory.mkdir(parents=True, exist_ok=True)
(output_directory / "dd").mkdir(parents=True, exist_ok=True)

for table_name in config['dataset']:
    # original colname => new colname (where new name may be totally new name or a cleaned up version)
    column_lookup = {}
    aggregators = BuildAggregators(config['dataset'][table_name]['aggregators'])
    agg_splitter =  config['dataset'][table_name].get('aggregator-splitter')

    # For each normal var, we'll push it into the queue as we finish it up
    data_dictionary_vars = []
    # For the aggregated vars, we will need a way to find them as we encounter related values
    aggregatedvars = {}

    variables = {}
    dd_filename = Path(config['dataset'][table_name]['data_dictionary']['filename'])
    #pdb.set_trace()
    with dd_filename.open('rt') as ddfile:
        splitter = config['dataset'][table_name].get('aggregator-splitter')

        ddreader = csv.DictReader(ddfile, delimiter=',', quotechar='"')
        
        # Drop case for the colnames to avoid case issues
        ddreader.fieldnames = [x.lower() for x in ddreader.fieldnames]

        for row in ddreader:
            varname = row['field']
            print(varname)
            #pdb.set_trace()
            if varname in wonky_colnames:
                varname = wonky_colnames[varname]
            orig_name = varname
            name_components = [varname]
            if splitter is not None:
                name_components = varname.split(splitter)

            container_var = TestAggregatable(aggregators, varname)

            if container_var is not None:
                container_desc = container_var
                if len(name_components) > 0:
                    if splitter is not None:
                        container_desc = name_components[0]
                        varname = splitter.join(name_components[1:])

                if container_var not in aggregatedvars:
                    newvar = Variable(container_var, container_desc)
                    data_dictionary_vars.append(newvar)
                    aggregatedvars[container_var] = newvar
                varname = aggregatedvars[container_var].add_value(container_var, varname.replace(";", ""))
            else:
                comment = ""
                if len(varname) > MAX_COLNAME_SIZE:
                    #comment = "Original Question: " + varname
                    comment = "Original Description: " + row['description']
                    varname = build_code("q")
                    #pdb.set_trace()
                newvar = Variable(varname, orig_name, row=row, comment=comment)
                data_dictionary_vars.append(newvar)
            
            variables[varname] = data_dictionary_vars[-1]
            column_lookup[orig_name] = varname

    # This is going to be useful for     
    colname_lookup = output_directory / "dd" / f"{Path(config['dataset'][table_name]['data_dictionary']['filename']).name}-colnames.csv"
    with colname_lookup.open('wt') as outf:
        writer = csv.writer(outf, delimiter=',', quotechar='"')
        writer.writerow(['original_name', 'varname'])

        for colname in sorted(column_lookup.keys()):
            writer.writerow([colname, column_lookup[colname]])
            
    # Finished reading in the data-dictionary, let's write an updated version up
    ddoutfn = output_directory / "dd" / Path(config['dataset'][table_name]['data_dictionary']['filename']).name

    # Just make sure we aren't about to overwrite the file we were using to load the data
    assert(dd_filename != ddoutfn)

    with ddoutfn.open('wt') as outf:
        writer = csv.writer(outf, delimiter=',', quotechar='"')
        Variable.header(writer)

        for var in data_dictionary_vars:
            var.writerow(writer)

    # Now, just change the first row in the dataset to match the updated versions of those
    # colnames
    ds_filename = Path(config['dataset'][table_name]['filename'])
    with ds_filename.open('rt', encoding='utf-8-sig') as inf:
        reader = csv.reader(inf, delimiter=',', quotechar='"')

        updated_ds_fn = output_directory / ds_filename.name 
        assert(updated_ds_fn != ds_filename)

        with updated_ds_fn.open('wt') as outf:
            writer = csv.writer(outf, delimiter=',', quotechar='"')

            rownum = 0
            header = None
            for row in reader:
                if rownum == 0:
                    newrow = []

                    for varname in row:
                        if varname in wonky_colnames:
                            varname = wonky_colnames[varname]

                        if varname in column_lookup:
                            newrow.append(column_lookup[varname])
                        else:
                            print(f"{varname} doesn't seem to be there in our list of columns")
                            pdb.set_trace()
                            newrow.append(varname)
                    header = [x for x in newrow]
                    writer.writerow(newrow)
                else:
                    newrow = []
                    for idx in range(len(header)):
                        varname = header[idx]
                        value = variables[varname].translate(row[idx])
                        newrow.append(value)
                    writer.writerow(newrow)
                rownum += 1 
        






