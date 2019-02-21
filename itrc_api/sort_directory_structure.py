import shutil
import sys, os
import csv
import configparser
import glob
import shutil

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), 'script_config.ini'))
BASE_PATH = CONFIG['file_locations']['base_path']

DATA_OUTPUT_AREAS = os.path.join(BASE_PATH, 'prems_by_oa')
DATA_LUTS = os.path.join(BASE_PATH, 'oa_to_lad_luts')
DATA_OUTPUT = os.path.join(BASE_PATH, 'prems_by_lad')

def import_luts(path):
    """Imports existing output area lookup table by local authority district.
    Directly yields the output area codes for a specific lad file path.
    """
    with open(path, 'r') as system_file:
        reader = csv.reader(system_file)
        next(reader)
        try:
            for line in reader:
                yield line[2]
        except:
            print('problem with {}'.format(path))

def get_list_of_files(path):
    """Creates a list of all .csv output area files in existing directory
    """
    return glob.iglob(path + '/*.csv', recursive=True)


#oa_to_lad_luts = [os.path.join(DATA_LUTS, 'E06000001.csv')]
oa_to_lad_luts = get_list_of_files(DATA_LUTS)

#import each lut at the lad level
for lut in oa_to_lad_luts:
    
    #create output folder if it doesn't already exist
    new_directory = os.path.join(DATA_OUTPUT, os.path.basename(lut)[:-4])
    if not os.path.exists(new_directory):
        os.makedirs(new_directory)
    
    #import
    for oa in import_luts(lut):
        existing_path = os.path.join(DATA_OUTPUT_AREAS, oa + '.csv')
        if os.path.exists(existing_path):
            # find and move oa file into folder
            shutil.move(existing_path, new_directory)
        else:
            pass







