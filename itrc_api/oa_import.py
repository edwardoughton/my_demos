import requests
import json
import os, sys
import configparser
import csv
import glob

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), 'script_config.ini'))
BASE_PATH = CONFIG['file_locations']['base_path']

DATA_RAW_INPUTS = os.path.join(BASE_PATH)
DATA_RAW_OUTPUTS = os.path.join(BASE_PATH, 'prems_by_oa')

#oa_ids
def get_oa_id_list():

    area_list = []
    
    pathlist = glob.iglob(os.path.join(DATA_RAW_INPUTS, 'oa_lut') + '/*.csv', recursive=True)

    for path in pathlist:
        with open(path, 'r') as system_file:
            reader = csv.reader(system_file)
            next(reader, None)
            for line in reader:
                area_list.append(line[0])

    return area_list

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

area_ids = get_oa_id_list()
area_ids.reverse()
#run loop
for area_id in area_ids:

    first_part = 'https://www.nismod.ac.uk/api/data/mastermap/buildings?scale=oa&building_year=2017&area_codes='

    full_address = first_part + area_id

    response = requests.get(full_address, auth=('neo4936','f67eRT2##i7HyH'))

    data = json.loads(response.text)

    if len(data) >0:
        csv_writer(data, '{}.csv'.format(area_id))
    else:
        print('{} did not contain data'.format(area_id))
        pass
