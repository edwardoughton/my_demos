import shutil
import sys, os
import csv
import configparser
import glob
import shutil

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), 'script_config.ini'))
BASE_PATH = CONFIG['file_locations']['base_path']

DATA_PREMS_BY_OA = os.path.join(BASE_PATH, 'prems_by_oa')
DATA_LUTS = os.path.join(BASE_PATH, 'oa_to_lad_luts')
DATA_OUTPUT = os.path.join(BASE_PATH, 'prems_by_lad')

def import_luts(path):
    """Imports existing output area lookup table by local authority district.
    Directly yields the output area codes for a specific lad file path.
    """
    with open(path, 'r') as system_file:
        reader = csv.DictReader(system_file)
        next(reader)
        try:
            for line in reader:
                yield line['oa_code']
        except:
            print('problem with {}'.format(path))

def get_list_of_files(path):
    """Creates a list of all .csv output area files in existing directory
    """
    return glob.iglob(path + '/*.csv', recursive=True)

def move_oa_files_into_lad_folders(oa_to_lad_luts):
    """
    """
    #import each lut at the lad level
    for lut in oa_to_lad_luts:

        #create output folder if it doesn't already exist
        new_directory = os.path.join(DATA_OUTPUT, os.path.basename(lut)[:-4])
        if not os.path.exists(new_directory):
            os.makedirs(new_directory)

        #import
        for oa in import_luts(lut):
            existing_path = os.path.join(DATA_PREMS_BY_OA, oa + '.csv')
            if os.path.exists(existing_path):
                #if rewriting over existing defective file, delete file first
                if os.path.exists(new_directory):
                    to_remove = os.path.join(new_directory, oa + '.csv')
                    if os.path.exists(to_remove):
                        os.remove(os.path.join(new_directory, oa + '.csv'))
                # find and move oa file into folder
                shutil.move(existing_path, new_directory)
            else:
                pass

    return print('completed')

##########################################################################
# DEGBUG MISSING LADS
##########################################################################

def find_non_matching_oa_to_lads():
    """Some OAs were left in DATA_PREMS_BY_OA.
    There seem to be some issues with the LAD codes.
    This function finds the LAD codes for remaining OAs, and prints them

    """
    lad_codes = []

    pathlist = glob.iglob(DATA_PREMS_BY_OA + '/*.csv', recursive=True)

    for path in pathlist:
         with open(path, 'r') as system_file:
            reader = csv.DictReader(system_file)
            for line in reader:
                lad_codes.append(line['lad'])

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

def rename_2011_lad_folders_to_2016(missing_lads):

    dirlist  = os.listdir(DATA_OUTPUT)

    for directory in dirlist:
        if directory == 'E07000097':
            try:
                os.rename(os.path.join(DATA_OUTPUT,'E07000097'), os.path.join(DATA_OUTPUT,'E07000242'))
            except:
                print('directory already exists')
        if directory == 'E06000048':
            try:
                os.rename(os.path.join(DATA_OUTPUT,'E06000048'), os.path.join(DATA_OUTPUT,'E06000057'))
            except:
                print('directory already exists')
        if directory == 'E41000052':
            try:
                os.rename(os.path.join(DATA_OUTPUT,'E41000052'), os.path.join(DATA_OUTPUT,'E06000052'))
            except:
                print('directory already exists')
        if directory == 'E08000020':
            try:
                os.rename(os.path.join(DATA_OUTPUT,'E08000020'), os.path.join(DATA_OUTPUT,'E08000037'))
            except:
                print('directory already exists')
        if directory == 'E07000101':
            try:
                os.rename(os.path.join(DATA_OUTPUT,'E07000101'), os.path.join(DATA_OUTPUT,'E07000242'))
            except:
                print('directory already exists')
        if directory == 'E07000104':
            try:
                os.rename(os.path.join(DATA_OUTPUT,'E07000104'), os.path.join(DATA_OUTPUT,'E07000241'))
            except:
                print('directory already exists')
        if directory == 'E07000100':
            try:
                os.rename(os.path.join(DATA_OUTPUT,'E07000100'), os.path.join(DATA_OUTPUT,'E07000240'))
            except:
                print('directory already exists')
        if directory == 'E41000324':
            try:
                os.rename(os.path.join(DATA_OUTPUT,'E41000324'), os.path.join(DATA_OUTPUT,'E09000001'))
            except:
                print('directory already exists')
        if directory == 'E07000101':
            try:
                os.rename(os.path.join(DATA_OUTPUT,'E07000101'), os.path.join(DATA_OUTPUT,'E07000243'))
            except:
                print('directory already exists')

    return print('renaming complete')

def move_residuals():
    """
    Some OA data is being left in prems_by_oa. This function opens them, gets their LAD
    and then moves them into the relevant folder in prems_by_lad.

    """
    DIRECTORY = os.path.join(DATA_PREMS_BY_OA)
    PATHS = glob.iglob(DIRECTORY + '/*.csv', recursive=True)

    #move residuals
    for PATH in PATHS:
        with open(PATH, 'r') as source:
            reader = csv.DictReader(source)
            first_row = next(reader)
            my_list = dict(first_row)
            lad = my_list['lad']
        filename = os.path.basename(PATH)
        new_path = os.path.join(DATA_OUTPUT, lad, filename)
        shutil.move(PATH, new_path)
        #os.remove(os.path.join(PATH))

    return print('completed')

#################################################################

if __name__ == "__main__":

    #get a list of all oa_to_lad_luts
    oa_to_lad_luts = get_list_of_files(DATA_LUTS)

    #Cyle through all luts in oa_to_lad_luts
    move_oa_files_into_lad_folders(oa_to_lad_luts)

    missing_lads = find_non_matching_oa_to_lads()

    missing_lads.extend([
        'E07000097', 'E06000048', 'E41000052', 'E08000020',
        'E07000101', 'E07000104', 'E41000324', 'E07000100'
        ])

    missing_paths = convert_to_directory_paths(DATA_LUTS, missing_lads)

    move_oa_files_into_lad_folders(missing_paths)

    rename_2011_lad_folders_to_2016(missing_lads)

    move_residuals()

    print('complete')
