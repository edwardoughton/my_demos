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


def move_oa_files_into_lad_folders(oa_to_lad_luts):
    
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

    return print('completed')

##########################################################################
# DEGBUG MISSING LADS
##########################################################################

def find_non_matching_oa_to_lads():
    """Some OAs were left in DATA_OUTPUT_AREAS. 
    There seem to be some issues with the LAD codes.
    This function finds the LAD costs for remaining OAs, and prints them
    """

    lad_codes = []

    pathlist = glob.iglob(DATA_OUTPUT_AREAS + '/*.csv', recursive=True)

    for path in pathlist:
         with open(path, 'r') as system_file:
            reader = csv.reader(system_file)
            for line in reader:
                lad_codes.append(line[12])

    unique_lad_codes = list(set(lad_codes))

    final_lad_codes = []

    for lad in unique_lad_codes:
        PATH = os.path.join(DATA_OUTPUT, lad)
        if os.path.exists(PATH):
            print('{} has lad data'.format(lad))
        else:
            final_lad_codes.append(lad)        

    return final_lad_codes

def convert_to_directory_paths(directory, data):

    output = []

    for datum in data:
        PATH = os.path.join(directory, datum + '.csv')
        output.append(PATH)

    return output

if __name__ == "__main__":

    oa_to_lad_luts = get_list_of_files(DATA_LUTS)
    
    move_oa_files_into_lad_folders(oa_to_lad_luts)

    missing_lads = find_non_matching_oa_to_lads()

    missing_lads = ['E07000097', 'E06000048', 'E41000052', 'E08000020', 'E07000101', 'E07000104', 'E41000324', 'E07000100']
    
    missing_paths = convert_to_directory_paths(DATA_LUTS, missing_lads)

    move_oa_files_into_lad_folders(missing_paths)

    print('complete')


