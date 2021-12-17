#!/usr/bin/env python

"""
Build a harmony CSV based off of the Data-Dictionary details found 
inside the whistle input json file. Initially, this was intended
to be a run once sort of script, a new version should be written
to pull data from the live google sheet folks are actively updating
to update the current DD. That new script will come into being 
very soon (but after the holidays)

"""

from wstlr.harmony import ParseJSON
from csv import DictReader
from enum import Enum
from collections import defaultdict
import pdb

no_harmony = set([
    'consents',  
])
predefined_codings = {
    'race_american_indian': {'code': '1002-5','display': 'American Indian or Alaska Native','system': 'urn:oid:2.16.840.1.113883.6.238'},
    'race_asian': {'code': '2028-9','display': 'Asian','system': 'urn:oid:2.16.840.1.113883.6.238'},
    'race_black': {'code': '2054-5','display': 'Black or African American','system': 'urn:oid:2.16.840.1.113883.6.238'},
    'race_pacific_islander': {'code': '2076-8','display': 'Native Hawaiian or Other Pacific Islander','system': 'urn:oid:2.16.840.1.113883.6.238'},
    'race_white': {'code': '2028-9','display': 'White','system': 'urn:oid:2.16.840.1.113883.6.238'},
    'race_unknown': {'code': 'UNK','display': 'Unknown','system': 'http://terminology.hl7.org/CodeSystem/v3-NullFlavor'}
}

class VocabularyType(Enum):
    HPO = 1
    MONDO = 2

class Annotation:
    def __init__(self, code, display, vocab_type):
        self.code = code.replace("HP_", "HP:").split(":")[-1]
        self.display = display
        if self.display[-1] == "'":
            self.display = display[:-1]

        if vocab_type == VocabularyType.HPO:
            self.system = "http://purl.obolibrary.org/obo/hp.owl"
        elif vocab_type == VocabularyType.MONDO:
            self.system = "http://purl.obolibrary.org/obo/mondo.owl"   
        else: 
            self.system = vocab_type     

class Annotator:
    def do_filter(self, var):
        return var.system in no_harmony

    def __init__(self, translation_file, colnames_files):
        self.translation_file = translation_file
        self.annotations = defaultdict(list)

        self.colnames = {}
        for filename in colnames_files:
            with open(filename, 'rt') as f:
                reader = DictReader(f, delimiter=',', quotechar='"')
                
                for row in reader:
                    self.colnames[row['original_name']] = row['varname']

        with open(self.translation_file, 'rt') as f:
            reader = DictReader(f, delimiter=',', quotechar='"')
            print(reader.fieldnames)
            for line in reader:
                question = line['Source Text (i.e. from original data)']
                if question in self.colnames:
                    question = self.colnames[question]

                hpo_code = line['HPO ID']
                hpo_display = line['HPO Label']
                mondo_code = line['Mondo ID']
                mondo_display = line['Mondo Label']

                if hpo_code.strip() != "":
                    assert(";" not in hpo_code)
                    self.annotations[question.lower()].append(Annotation(hpo_code, hpo_display, VocabularyType.HPO))
                if mondo_code.strip() != "":
                    assert(";" not in hpo_code)
                    self.annotations[question.lower()].append(Annotation(mondo_code, mondo_display, VocabularyType.MONDO))
        for question in predefined_codings:
            anot = predefined_codings[question]
            self.annotations[question].append(Annotation(anot['code'], anot['display'], anot['system']))

    def consume_var(self, var):
        vardesc = var.desc.lower()

        if vardesc not in self.annotations:
            vardesc = f"{var.system.lower()} {var.varname.lower()}"

        if vardesc in self.annotations:
            #pdb.set_trace()
            for annotation in self.annotations[vardesc]:
                print(f"Annotating {vardesc}")
                var.add_annotation(annotation.code, annotation.display, annotation.system, "https://docs.google.com/spreadsheets/d/1cHSburUDg6CR4az5FZR82FI992h7cyv-22pLVTFLZvE/edit#gid=1746314807")
        else:
            print(vardesc)

            if vardesc.split()[-1][0] in ['XY']: #['v']:
                print(f"No match for the variable: {vardesc}")
                #pdb.set_trace()
# include-pheno-codes-... is a slightly modified version of the google sheet
# provided by Pirrette. The files named *-colnames.csv are biproducts of the 
# fix_input_files.py script and are used to tie those entries in the google
# sheet to the new column names. 
annotator = Annotator("project/include-pheno-codes-ds-connect.csv", ["data/ds-connect/updated/dd/demographics.csv-colnames.csv", "data/ds-connect/updated/dd/ds-connect-ihq.csv-colnames.csv"])

input_json = open("output/whistle-input/ds-connect.json", 'rt')
with open("output/ds-connect-harmony-skeleton.csv", 'wt') as output_json:
    ParseJSON(input_json, output_json, variable_consumers=[annotator.consume_var], filter=[annotator.do_filter])

