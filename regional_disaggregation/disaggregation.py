import os, sys
from pprint import pprint
import configparser
import csv
import fiona
import glob
from rtree import index
from shapely.geometry import shape, mapping, MultiPolygon
from collections import OrderedDict
import gc
from itertools import chain

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), 'script_config.ini'))
BASE_PATH = CONFIG['file_locations']['base_path']

DATA_RAW_INPUTS = os.path.join(BASE_PATH)
DATA_RAW_OUTPUTS = os.path.join(BASE_PATH, 'processed_output')

def read_lads():
    """
    Read in ONS Local Authority District shapes
    """
    
    # with fiona.open(os.path.join(DATA_RAW_INPUTS, 'lad_uk_2016-12', 'lad_uk_2016-12.shp'), 'r') as source:
    #     return [lad for lad in source if lad['properties']['desc'] == 'Cambridge']

    with fiona.open(os.path.join(DATA_RAW_INPUTS, 'lad_uk_2016-12', 'lad_uk_2016-12.shp'), 'r') as source:
        return [lad for lad in source]

def read_regions():
    """
    Read in European Region shapes (previously ONS govenment office regions)
    """

    regions = []

    with fiona.open(os.path.join(DATA_RAW_INPUTS, 'boundaryline_2755120', 'european_region_region.shp'), 'r') as source:
        return [region for region in source]

        
def convert_multishapes_to_single_shapes(data):

    area_id_list = []
    single_regions = []

    for region in data:
        area_id_list.append(region['properties']['CODE'])

    unique_ids = list(set(area_id_list))

    final_shapes = []

    for area_id in unique_ids:
        geometry = []
        for region in data:
            if area_id == region['properties']['CODE']:        
                coords = shape(region['geometry'])
                #coords = [val for sublist in coords for val in sublist]
                geometry.append(coords)      

        final_shapes.append({
            'type': "Feature",
            'geometry': mapping(MultiPolygon(geometry)),
            'properties': {
                'id': area_id,
            }
        })

    return final_shapes

def get_lad_list(lads):

    lads_ids = []

    for lad in lads:
        lad_id = lad['properties']['name']
        lads_ids.append(lad_id)

    unique_set = list(set(lads_ids))

    return unique_set

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
                'type': "Feature",
                'geometry': {
                    "type": "Point",
                    "coordinates": [float(line[8]), float(line[7])]
                },
                'properties': {
                    'uid': line[0],
                    'oa': line[1],
                    'gor': line[2],
                    'residential_address_count': line[3],
                    'non_residential_address_count': line[4],
                    'function': line[5],
                    'postgis_geom': line[6],
                    # 'N': line[7],
                    # 'E':line[8],
                }
            })

    return premises_data

def add_lad_to_premises(premises, lads):
    
    joined_premises = []

    # Initialze Rtree
    idx = index.Index()
    [idx.insert(0, shape(premise['geometry']).bounds, premise) for premise in premises]

    # Join the two
    for lad in lads:
        for n in idx.intersection((shape(lad['geometry']).bounds), objects=True):
            lad_shape = shape(lad['geometry'])
            premise_shape = shape(n.object['geometry'])
            if lad_shape.contains(premise_shape):
                n.object['properties']['lad'] = lad['properties']['name']
                joined_premises.append(n.object)

    return joined_premises

def write_shapefile(data, directory, filename):
    
    # Translate props to Fiona sink schema
    prop_schema = []
    for name, value in data[0]['properties'].items():
        fiona_prop_type = next((fiona_type for fiona_type, python_type in fiona.FIELD_TYPES_MAP.items() if python_type == type(value)), None)
        prop_schema.append((name, fiona_prop_type))

    sink_driver = 'ESRI Shapefile'
    sink_crs = {'init': 'epsg:27700'}
    sink_schema = {
        'geometry': data[0]['geometry']['type'],
        'properties': OrderedDict(prop_schema)
    }

    if not os.path.exists(directory):
        os.makedirs(directory)

    print('path is {}'.format(os.path.join(directory, filename, '.shp')))
    # Write all elements to output file
    with fiona.open(os.path.join(directory, filename + '.shp'), 'w', driver=sink_driver, crs=sink_crs, schema=sink_schema) as sink:
        [sink.write(feature) for feature in data]


    # if len(data) >= 1:
    
    #     # Translate props to Fiona sink schema
    #     prop_schema = []
    #     for name, value in data[0]['properties'].items():
    #         fiona_prop_type = next((fiona_type for fiona_type, python_type in fiona.FIELD_TYPES_MAP.items() if python_type == type(value)), None)
    #         prop_schema.append((name, fiona_prop_type))

    #     sink_driver = 'ESRI Shapefile'
    #     sink_crs = {'init': 'epsg:27700'}
    #     sink_schema = {
    #         'geometry': data[0]['geometry']['type'],
    #         'properties': OrderedDict(prop_schema)
    #     }

    #     if not os.path.exists(directory):
    #         os.makedirs(directory)

    #     print('path is {}'.format(os.path.join(directory, filename, '.shp')))
    #     # Write all elements to output file
    #     with fiona.open(os.path.join(directory, filename + '.shp'), 'w', driver=sink_driver, crs=sink_crs, schema=sink_schema) as sink:
    #         [sink.write(feature) for feature in data]
    
    # else: 
    #     print('no data to write for {}'.format(filename))

def write_final_output(premises, lads):
    
    directory = DATA_RAW_OUTPUTS
    if not os.path.exists(directory):
        os.makedirs(directory)

    for lad in lads:
        prems_by_lad = []
        print('finding prem data for {}'.format(lad['properties']['desc']))
        filename = lad['properties']['name']
        
        if not os.path.exists(os.path.join(directory, filename, '.shp')):

            for prem in list(premises):
                if filename == prem['properties']['lad']:
                    prems_by_lad.append(prem)
                    premises.remove(prem)

            write_shapefile(prems_by_lad, directory, filename)    
        
        else:
            pass

#####################################
# RUN FUNCTIONS
#####################################

lads = read_lads()

regions = read_regions()

regions = convert_multishapes_to_single_shapes(regions)

geometry = []
for region in regions:
    geometry = region['geometry']['coordinates']
    print('id is {} and len is {}'.format(region['properties']['id'], len(geometry)))
    #for geom in geometry:

#print(regions[1])
write_shapefile(regions, os.path.join(DATA_RAW_OUTPUTS, 'test_outputs'), 'convert_multipolygons')

# lad_list = get_lad_list(lads)

# pathlist = glob.iglob(os.path.join(DATA_RAW_INPUTS, 'layer_5_premises') + '/*.csv', recursive=True)

# pathlist = []
# pathlist.append(os.path.join(DATA_RAW_INPUTS, 'layer_5_premises', 'blds_with_functions_en_E12000006.csv'))

# for path in pathlist:

#     file_name = path.split("premises\\", 1)[1]

#     print('reading prem data for {}'.format(file_name))
#     premises = read_premises_data(path, file_name)

#     print('adding lad to premises for {}'.format(file_name))
#     premises = add_lad_to_premises(premises, lads)

#     print('writing premises data for {}'.format(file_name))
#     write_final_output(premises, lads)

#     gc.collect()

print('script completed')

