import os, sys
from pprint import pprint
import configparser
import csv
import glob
import gc
from collections import defaultdict

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), 'script_config.ini'))
BASE_PATH = CONFIG['file_locations']['base_path']

DATA_RAW_INPUTS = os.path.join(BASE_PATH)
DATA_RAW_OUTPUTS = os.path.join(BASE_PATH, 'processed_output')

def read_in_oa_to_lad_lut():

    lut = []
    
    with open(os.path.join(DATA_RAW_INPUTS, 'oa_lut', 'oa_lut.csv'), 'r') as system_file:
        reader = csv.reader(system_file)
        next(reader)
        for line in reader:
            lut.append({
                'oa': line[0],
                'lad': line[5],
                })
    
    return lut

def read_in_lad_to_region_lut():

    intermediate_lut = []
    
    with open(os.path.join(DATA_RAW_INPUTS, 'oa_lut', 'lad_to_region_lut.csv'), 'r') as system_file:
        reader = csv.reader(system_file)
        next(reader)
        for line in reader:
            intermediate_lut.append({
                'lad': line[0],
                'region': line[3],
                })

    return intermediate_lut

def merge_luts(lad_lut, region_lut):

    mega_lut = [] 

    for area in lad_lut:
        for area_2 in region_lut:
            if area['lad'] == area_2['lad']:
                mega_lut.append({
                    'oa': area['oa'],
                    'lad': area_2['lad'],
                    'region': area_2['region']
                })

    return mega_lut

def write_lut_to_csv(lut, fieldnames):
    """
    Write data to a CSV file path
    """

    lads = []

    for entry in lut:
        lads.append(entry['region'])

    unique_lads = set(lads)

    # Create path
    for lad in unique_lads:
        
        data_to_write = []
        
        for entry in lut:
            if lad == entry['region']:
                data_to_write.append(entry)
        
        with open(os.path.join(DATA_RAW_INPUTS,'oa_lut', lad + '.csv'), 'w') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames, lineterminator = '\n')
            writer.writeheader()
            writer.writerows(data_to_write)

def read_premises_data(path, filename):
    """
    Reads in premises points from the OS AddressBase data (.csv).

    Data Schema
    ----------
    * id: :obj:`int`
        Unique Premises ID
    * oa: :obj:`str`
        ONS output area code
    * residential address count: obj:'str'
        Number of residential addresses
    * non-res address count: obj:'str'
        Number of non-residential addresses
    * postgis geom: obj:'str'
        Postgis reference
    * E: obj:'float'
        Easting coordinate
    * N: obj:'float'
        Northing coordinate

    """
    premises_data = []
    
    with open(os.path.join(path), 'r') as system_file:
        reader = csv.reader(system_file)
        next(reader)
        for line in reader:
            premises_data.append({
                'uid': line[0],
                'oa': line[1],
                'gor': line[2],
                'res_count': line[3],
                'nonres_count': line[4],
                'function': line[5],
                'geom': line[6],
                'N': line[7],
                'E':line[8],
                })

    return premises_data

def read_regional_lut(regional_lut_id):

    lut = []
    
    with open(os.path.join(DATA_RAW_INPUTS, 'oa_lut', regional_lut_id), 'r') as system_file:
        reader = csv.reader(system_file)
        next(reader)
        for line in reader:
            lut.append({
                'oa': line[0],
                'lad': line[1],
                })
    
    return lut

def allocate_prems_to_area(prems_data, lut):

    reallocated_prems = defaultdict(list)

    for area in lut:
        for premises in prems_data:
            if area['oa'] == premises['oa']:
                reallocated_prems[area['lad']].append(premises)

    return reallocated_prems

def write_premises_to_csv(premises_by_lad, fieldnames):
    """
    Write data to a CSV file path
    """
    # Create path
    directory = os.path.join(DATA_RAW_OUTPUTS)
    if not os.path.exists(directory):
        os.makedirs(directory)

    for key, value in premises_by_lad.items():

        print('finding prem data for {}'.format(key))
        filename = key
        
        with open(os.path.join(directory, filename + '.csv'), 'w') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames, lineterminator = '\n')
            writer.writeheader()
            writer.writerows(value)

############################
# run functions
############################

#read in output area to lad lookup table
lad_lut = read_in_oa_to_lad_lut()

#read in lad to region lookup table
region_lut = read_in_lad_to_region_lut()

#merge the two lookup tables using the lad field
final_lut = merge_luts(lad_lut, region_lut)

#write the lut to the lut folder, separated by region
fieldnames = ['oa','lad','region']
write_lut_to_csv(final_lut, fieldnames)

# pathlist = glob.iglob(os.path.join(DATA_RAW_INPUTS, 'layer_5_premises') + '/*.csv', recursive=True)

pathlist = []
pathlist.append(os.path.join(DATA_RAW_INPUTS, 'layer_5_premises', 'blds_with_functions_en_E12000006.csv'))

for path in pathlist:

    file_name = path.split("premises\\", 1)[1]
    
    print('reading prem data for {}'.format(file_name))
    premises = read_premises_data(path, file_name)

    #get regional lut name
    regional_lut_id = file_name[23:]

    #import regional lut
    regional_lut = read_regional_lut(regional_lut_id)

    prems_by_area = allocate_prems_to_area(premises, regional_lut)

    print('writing premises data for {}'.format(file_name))
    fieldnames = ['uid','oa','gor','res_count','nonres_count','function','geom','N','E']
    write_premises_to_csv(prems_by_area, fieldnames)

    gc.collect()

print('script completed')

