import requests
import json
import os, sys

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), 'script_config.ini'))
BASE_PATH = CONFIG['file_locations']['base_path']


#oa_ids
oa_ids=['E00009380',
        'E00009182',
        'E00009218',
        'E00009429',
        'E00009274',
        'E00009328',
        'E00009381',
        'E00009183',
        'E00009219',
]

#write csv
def csv_writer(data, filename):
    """
    Write data to a CSV file path
    """
    prop_schema = []
    for name, value in data[0].items():
        prop_schema.append(name)

    # Create path
    directory = os.path.join(DATA_INTERMEDIATE)
    if not os.path.exists(directory):
        os.makedirs(directory)

    name = os.path.join(DATA_INTERMEDIATE, filename)

    with open(name, 'w') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames, lineterminator = '\n')
        writer.writeheader()
        writer.writerows(data)

loop_length_fieldnames = ['landparcel_i','exchange_id','geotype']

#run loop
for oa_id in oa_ids:

    first_part = 'https://www.nismod.ac.uk/api/data/mastermap/buildings?scale=oa&building_year=2017&area_codes='

    full_address = first_part + oa_id 

    response = requests.get(full_address, auth=('neo4936','f67eRT2##i7HyH'))
    
    data = json.loads(response.text)

    csv_writer(data, '{}.csv'.format(oa_id))
