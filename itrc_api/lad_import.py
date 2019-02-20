import requests
import json
import os, sys
import configparser
import csv
import glob
import fiona

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), 'script_config.ini'))
BASE_PATH = CONFIG['file_locations']['base_path']

DATA_RAW_INPUTS = os.path.join(BASE_PATH)
DATA_RAW_OUTPUTS = os.path.join(BASE_PATH, 'oa_to_lad_luts')

#lad_ids
def get_lads():
    
    pathlist = glob.iglob(os.path.join(DATA_RAW_INPUTS, 'lad_uk_2016-12') + '/*.shp', recursive=True)

    for path in pathlist:
        with fiona.open(path, 'r') as source:
            return [lad for lad in source]
                
def get_lad_ids(data):

    lad_ids = []

    for lad in data:
        lad_ids.append(lad['properties']['name'])
    
    return lad_ids


#write csv
def csv_writer(data, filename):
   """
   Write data to a CSV file path
   """
   prop_schema = []
   for name, value in data[0].items():
       prop_schema.append(name)

   # Create path
   directory = os.path.join(DATA_RAW_OUTPUTS)
   if not os.path.exists(directory):
       os.makedirs(directory)

   name = os.path.join(DATA_RAW_OUTPUTS, filename)

   with open(name, 'w') as csv_file:
       writer = csv.DictWriter(csv_file, prop_schema, lineterminator = '\n')
       writer.writeheader()
       writer.writerows(data)

lads = get_lads()

lad_ids = get_lad_ids(lads)

#run loop
for area_id in lad_ids:

    first_part = 'http://www.nismod.ac.uk/api/data/boundaries/oas_in_lad?lad_codes='

    full_address = first_part + area_id

    response = requests.get(full_address, auth=('neo4936','f67eRT2##i7HyH'))

    data = json.loads(response.text)

    if len(data) >0:
        csv_writer(data, '{}.csv'.format(area_id))
    else:
        print('{} did not contain data'.format(area_id))
        pass
