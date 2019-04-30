"""
This script downloads all output area information for each local authority district

"""
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

    pathlist = glob.iglob(
        os.path.join(DATA_RAW_INPUTS, 'lad_uk_2016-12') + '/*.shp', recursive=True
        )

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
#    prop_schema.append('oa_code')
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

def get_output_areas_by_lad(lad_ids):
    #run loop
    for area_id in lad_ids:
        print('working on {}'.format(area_id))
        first_part = 'http://www.nismod.ac.uk/api/data/boundaries/oas_in_lad?lad_codes='

        full_address = first_part + area_id

        response = requests.get(full_address, auth=('neo4936','f67eRT2##i7HyH'))

        data = json.loads(response.text)

        oa_codes = []

        for datum in data:
            oa_codes.append({
                'oa_code': datum['oa_code']
                })

        if len(data) >0:
            csv_writer(oa_codes, '{}.csv'.format(area_id))
        else:
            print('{} did not contain data'.format(area_id))
            pass

    return print('initial tranche complete')

#############################################################

if __name__ == "__main__":

    #first attempt
    get_output_areas_by_lad(lad_ids)
    print('completed step 1')
    #second attempt
    missing_lads = [
        'E07000097',
        'E06000048',
        'E41000052',
        'E08000020',
        'E07000101',
        'E07000104',
        'E41000324',
        'E07000100'
    ]
    get_output_areas_by_lad(missing_lads)
    print('completed step 2')
    #third attempt
    missing_lads = [
        'E07000074',
        'S12000006',
        'S12000008',
        'S12000017',
        'S12000035',
        'E09000033',
        'E41000324'
    ]
    get_output_areas_by_lad(missing_lads)
    print('completed step 3')
    #third attempt
    missing_lads = [
        'E07000004',
        'E07000046',
        'E07000074',
        'S12000006',
        'S12000008',
        'S12000013',
        'S12000017',
        'S12000023',
        'S12000024',
        'S12000027',
        'S12000030',
        'S12000035',
        'W06000008',
        'W06000009',
        'W06000010'
    ]
    get_output_areas_by_lad(missing_lads)
    print('completed step 4')
