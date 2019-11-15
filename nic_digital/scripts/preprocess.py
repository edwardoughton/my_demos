import os
import sys
import configparser
import csv
import fiona
import time

import numpy as np
from shapely.geometry import shape, Point, LineString, mapping
from shapely.ops import  cascaded_union, polygonize, split
from scipy.spatial import Voronoi, voronoi_plot_2d

from rtree import index

from collections import OrderedDict

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), 'script_config.ini'))
BASE_PATH = CONFIG['file_locations']['base_path']

#####################################
# setup file locations and data files
#####################################

DATA_RAW = os.path.join(BASE_PATH, 'raw')
DATA_INTERMEDIATE = os.path.join(BASE_PATH, 'intermediate')

#####################################
# READ MAIN DATA
#####################################

def read_lads():
    """
    Read in all lad shapes.

    """
    lad_shapes = os.path.join(
        DATA_RAW, 'shapes', 'lad_uk_2016-12.shp'
        )

    with fiona.open(lad_shapes, 'r') as lad_shape:
        return [lad for lad in lad_shape if
        not lad['properties']['name'].startswith((
            'E06000053',
            'S12000027',
            'N09000001',
            'N09000002',
            'N09000003',
            'N09000004',
            'N09000005',
            'N09000006',
            'N09000007',
            'N09000008',
            'N09000009',
            'N09000010',
            'N09000011',
            ))]


def load_population_data(path):
    """
    Load in LAD population data for 2015.

    """
    population_data = []

    with open(path, 'r') as source:
        reader = csv.DictReader(source)
        for line in reader:
            population_data.append({
                'lad': line['lad17cd'],
                'population': int(line['pop']),
            })

    return population_data


def add_population_to_lads(lads, population_data):
    """
    Add the population data to lad shapes.

    """
    output = []

    for item in population_data:
        for lad in lads:
            if item['lad'] == lad['properties']['name']:
                output.append({
                    'type': lad['type'],
                    'geometry': lad['geometry'],
                    'properties':{
                        'id': lad['properties']['name'],
                        'population': item['population'],
                        },
                })

    return output

def lad_lut(lads):
    """
    Yield lad IDs for use as a lookup.

    """
    for lad in lads:

        yield lad['properties']['id']


def read_shapes(path):
    """
    Read all postcode sector shapes.

    """
    with fiona.open(path, 'r') as shapes:
        return [shp for shp in shapes]


def add_lad_to_postcode_sector(postcode_sectors, lads):
    """
    Add the LAD indicator(s) to the relevant postcode sector.

    """
    final_postcode_sectors = []

    idx = index.Index(
        (i, shape(lad['geometry']).bounds, lad)
        for i, lad in enumerate(lads)
    )

    for postcode_sector in postcode_sectors:
        for n in idx.intersection(
            (shape(postcode_sector['geometry']).bounds), objects=True):
            postcode_sector_centroid = shape(postcode_sector['geometry']).centroid
            postcode_sector_shape = shape(postcode_sector['geometry'])
            lad_shape = shape(n.object['geometry'])
            if postcode_sector_centroid.intersects(lad_shape):
                final_postcode_sectors.append({
                    'type': postcode_sector['type'],
                    'geometry': postcode_sector['geometry'],
                    'properties':{
                        'id': postcode_sector['properties']['RMSect'],
                        'lad': n.object['properties']['id'],
                        'lad_pop': n.object['properties']['population'],
                        'area': postcode_sector_shape.area,
                        },
                    })
                break

    return final_postcode_sectors


def load_coverage_data(lad_id):
    """
    Import Ofcom Connected Nations coverage data (2018).

    """
    path = os.path.join(
        DATA_RAW, 'ofcom_2018', '201809_mobile_laua_r02.csv'
        )

    with open(path, 'r') as source:
        reader = csv.DictReader(source)
        for line in reader:
            if line['laua'] == lad_id:
                return {
                    'lad_id': line['laua'],
                    'lad_name': line['laua_name'],
                    '4G_geo_out_0': line['4G_geo_out_0'],
                    '4G_geo_out_1': line['4G_geo_out_1'],
                    '4G_geo_out_2': line['4G_geo_out_2'],
                    '4G_geo_out_3': line['4G_geo_out_3'],
                    '4G_geo_out_4': line['4G_geo_out_4'],
                }

def load_in_weights():
    """
    Load in postcode sector weights.

    """
    path = os.path.join(
        DATA_RAW, 'pcd_sector_weights', 'population_weights.csv'
        )

    output = []

    with open(path, 'r') as source:
        reader = csv.DictReader(source)
        for line in reader:
                output.append({
                    'id': line['postcode_sector'],
                    'domestic_delivery_points': int(line['domestic_delivery_points']),
                })

    return output


def add_weights_to_postcode_sector(postcode_sectors, weights):
    """
    Add weights to postcode sector

    """
    output = []

    for postcode_sector in postcode_sectors:
        pcd_id = postcode_sector['properties']['id'].replace(' ', '')
        for weight in weights:

            weight_id = weight['id'].replace(' ', '')

            weight = (
                    weight['domestic_delivery_points'] /
                    postcode_sector['properties']['lad_pop']
                )

            if pcd_id == weight_id:
                output.append({
                    'type': postcode_sector['type'],
                    'geometry': postcode_sector['geometry'],
                    'properties': {
                        'id': pcd_id,
                        'lad': postcode_sector['properties']['lad'],
                        'lad_pop': postcode_sector['properties']['lad_pop'],
                        'weight': weight,
                        'population': round(
                            postcode_sector['properties']['lad_pop'] * weight
                        ),
                        'area_km2': (postcode_sector['properties']['area'] / 1e6),
                        'pop_density_km2': round(
                            (postcode_sector['properties']['lad_pop'] * weight) /
                            (postcode_sector['properties']['area'] / 1e6)
                        )
                    }
                })

    return output


def disaggregate(forecast, postcode_sectors):
    """

    """
    output = []

    seen_lads = set()

    for line in forecast:
        forecast_lad_id = line['lad']
        for postcode_sector in postcode_sectors:
            pcd_sector_lad_id = postcode_sector['properties']['lad']
            if forecast_lad_id == pcd_sector_lad_id:
                # print(postcode_sector)
                seen_lads.add(line['lad'])
                seen_lads.add(postcode_sector['properties']['lad'])
                output.append({
                    'year': line['year'],
                    'lad': line['lad'],
                    'id': postcode_sector['properties']['id'],
                    'population': int(
                        float(line['population']) *
                        float(postcode_sector['properties']['weight'])
                        )
                })

    return output


def allocate_4G_coverage(postcode_sectors, lad_lut):

    output = []

    for lad_id in lad_lut:

        sectors_in_lad = get_postcode_sectors_in_lad(postcode_sectors, lad_id)

        total_area = sum([s['properties']['area_km2'] for s in \
            get_postcode_sectors_in_lad(postcode_sectors, lad_id)])

        coverage_data = load_coverage_data(lad_id)

        coverage_amount = float(coverage_data['4G_geo_out_4'])

        covered_area = total_area * (coverage_amount/100)

        ranked_postcode_sectors = sorted(
            sectors_in_lad, key=lambda x: x['properties']['pop_density_km2'], reverse=True
            )

        area_allocated = 0

        for sector in ranked_postcode_sectors:

            area = sector['properties']['area_km2']
            total = area + area_allocated

            if total < covered_area:

                sector['properties']['lte'] = 1
                output.append(sector)
                area_allocated += area

            else:

                sector['properties']['lte'] = 0
                output.append(sector)

                continue

    return output


def get_postcode_sectors_in_lad(postcode_sectors, lad_id):

    for postcode_sector in postcode_sectors:
        if postcode_sector['properties']['lad'] == lad_id:
            if isinstance(postcode_sector['properties']['pop_density_km2'], float):
                yield postcode_sector


def import_sitefinder_data(path):
    """
    Import sitefinder data, selecting desired asset types.
        - Select sites belonging to main operators:
            - Includes 'O2', 'Vodafone', BT EE (as 'Orange'/'T-Mobile') and 'Three'
            - Excludes 'Airwave' and 'Network Rail'
        - Select relevant cells:
            - Includes 'Macro', 'SECTOR', 'Sectored' and 'Directional'
            - Excludes 'micro', 'microcell', 'omni' or 'pico' antenna types.

    """
    asset_data = []

    site_id = 0

    with open(os.path.join(path), 'r') as system_file:
        reader = csv.DictReader(system_file)
        next(reader, None)
        for line in reader:
            # if line['Operator'] != 'Airwave' and line['Operator'] != 'Network Rail':
            if line['Operator'] == 'O2' or line['Operator'] == 'Vodafone':
                # if line['Anttype'] == 'MACRO' or \
                #     line['Anttype'] == 'SECTOR' or \
                #     line['Anttype'] == 'Sectored' or \
                #     line['Anttype'] == 'Directional':
                asset_data.append({
                    'type': "Feature",
                    'geometry': {
                        "type": "Point",
                        "coordinates": [float(line['X']), float(line['Y'])]
                    },
                    'properties':{
                        'name': 'site_' + str(site_id),
                        'Operator': line['Operator'],
                        'Opref': line['Opref'],
                        'Sitengr': line['Sitengr'],
                        'Antennaht': line['Antennaht'],
                        'Transtype': line['Transtype'],
                        'Freqband': line['Freqband'],
                        'Anttype': line['Anttype'],
                        'Powerdbw': line['Powerdbw'],
                        'Maxpwrdbw': line['Maxpwrdbw'],
                        'Maxpwrdbm': line['Maxpwrdbm'],
                        'Sitelat': float(line['Sitelat']),
                        'Sitelng': float(line['Sitelng']),
                    }
                })

            site_id += 1

        else:
            pass

    return asset_data


def process_asset_data(data):
    """
    Add buffer to each site, dissolve overlaps and take centroid.

    """
    buffered_assets = []

    for asset in data:
        asset_geom = shape(asset['geometry'])
        buffered_geom = asset_geom.buffer(50)

        asset['buffer'] = buffered_geom
        buffered_assets.append(asset)

    output = []
    assets_seen = set()

    for asset in buffered_assets:
        if asset['properties']['Opref'] in assets_seen:
            continue
        assets_seen.add(asset['properties']['Opref'])
        touching_assets = []
        for other_asset in buffered_assets:
            if asset['buffer'].intersects(other_asset['buffer']):
                touching_assets.append(other_asset)
                assets_seen.add(other_asset['properties']['Opref'])

        dissolved_shape = cascaded_union([a['buffer'] for a in touching_assets])
        final_centroid = dissolved_shape.centroid
        output.append({
            'type': "Feature",
            'geometry': {
                "type": "Point",
                "coordinates": [final_centroid.coords[0][0], final_centroid.coords[0][1]],
            },
            'properties':{
                'name': asset['properties']['name'],
            }
        })

    return output


def generate_perimeter(lads):

    geoms = []

    for lad in lads:
        geoms.append(shape(lad['geometry']))

    geom_union = list(cascaded_union(geoms))

    boundary = []
    for item in geom_union:
        if item.area > 10000000:
            boundary.append({
                'type': 'Polygon',
                'geometry': mapping(item),
                'properties': {
                    'id': 'perimeter'
                    },
                })

    return boundary


def generate_site_areas(processed_sites, perimeter):

    points = []

    for item in processed_sites:
        points.append((item['geometry']['coordinates']))

    vor = Voronoi(points)

    lines = [
        LineString(vor.vertices[line])
        for line in vor.ridge_vertices
        if -1 not in line
    ]

    site_areas = []

    for poly in polygonize(lines):
        for area in perimeter:
            area_geom = shape(area['geometry'])
            site_areas.append(split(poly.boundary, area_geom))

    idx = index.Index(
        (i, shape(site['geometry']).bounds, site)
        for i, site in enumerate(site_areas)
    )

    output = []

    for site in processed_sites:
        for n in idx.intersection(
            (shape(site['geometry']).bounds), objects=True):
            site_point = shape(site['geometry'])
            site_shape = shape(n.object['geometry'])
            if site_point.intersects(site_shape):
                output.append({
                    'type': 'Feature',
                    'geometry': n.object['geometry'],
                    'properties':{
                        'id': site['name'],
                        }
                    })

    return site_areas


def add_coverage_to_sites(sitefinder_data, postcode_sectors):

    final_sites = []

    idx = index.Index(
        (i, shape(site['geometry']).bounds, site)
        for i, site in enumerate(sitefinder_data)
    )

    for postcode_sector in postcode_sectors:
        for n in idx.intersection(
            (shape(postcode_sector['geometry']).bounds), objects=True):
            postcode_sector_shape = shape(postcode_sector['geometry'])
            site_shape = shape(n.object['geometry'])
            if postcode_sector_shape.intersects(site_shape):
                final_sites.append({
                    'type': 'Feature',
                    'geometry': n.object['geometry'],
                    'properties':{
                        'id': postcode_sector['properties']['id'],
                        'name': n.object['properties']['name'],
                        'lte_4G': postcode_sector['properties']['lte']
                        }
                    })

    return final_sites


def estimate_site_population(processed_sites, lads):

    idx = index.Index(
        (i, shape(lad['geometry']).bounds, lad)
        for i, lad in enumerate(lads)
        )

    output = []

    for site in processed_sites:
        for n in idx.intersection((shape(site['geometry']).bounds), objects=True):
            site_centroid = shape(site['geometry']).centroid
            lad_shape = shape(n.object['geometry'])
            if site_centroid.intersects(lad_shape):
                area_weight = (shape(site['geometry']).area / lad_shape.area)
                output.append({
                    'type': site['type'],
                    'geometry': site['geometry'],
                    'properties':{
                        'id': site['properties']['id'],
                        'name':site['properties']['name'],
                        'lte_4G': site['properties']['lte'],
                        'population': n.object['properties']['population'] * area_weight
                        },
                    })

    return output


def read_exchanges():
    """
    Reads in exchanges from 'final_exchange_pcds.csv'.

    """
    path = os.path.join(
        DATA_RAW, 'exchanges', 'final_exchange_pcds.csv'
        )

    with open(path, 'r') as source:
        reader = csv.DictReader(source)
        for line in reader:
            yield {
                'type': "Feature",
                'geometry': {
                    "type": "Point",
                    "coordinates": [float(line['E']), float(line['N'])]
                },
                'properties': {
                    'exchange_id': 'exchange_' + line['OLO'],
                    'exchange_name': line['Name'],
                    'id': line['exchange_pcd'],
                }
            }


def read_exchange_areas():
    """
    Read exchange polygons

    """
    path = os.path.join(
        DATA_RAW, 'exchanges', '_exchange_areas_fixed.shp'
        )

    with fiona.open(path, 'r') as source:
        for area in source:
            yield area


def return_object_coordinates(object):
    """
    Function for returning the coordinates of a type of object.

    """
    if object['geometry']['type'] == 'Polygon':
        origin_geom = object['representative_point']
        x = origin_geom.x
        y = origin_geom.y
    elif object['geometry']['type'] == 'Point':
        x = object['geometry']['coordinates'][0]
        y = object['geometry']['coordinates'][1]
    else:
        print('non conforming geometry type {}'.format(object['geometry']['type']))

    return x, y


def generate_link_straight_line(origin_points, dest_points):
    """
    Calculate distance between two points.

    """
    idx = index.Index(
        (i, Point(dest_point['geometry']['coordinates']).bounds, dest_point)
        for i, dest_point in enumerate(dest_points)
        )

    processed_sites = []
    links = []

    for origin_point in origin_points:

        try:
            origin_x, origin_y = return_object_coordinates(origin_point)

            exchange = list(idx.nearest(
                Point(origin_point['geometry']['coordinates']).bounds,
                1, objects='raw'))[0]

            dest_x, dest_y = return_object_coordinates(exchange)

            # Get lengthFunction for returning the coordinates of
            # an object given the specific type.
            geom = LineString([
                (origin_x, origin_y), (dest_x, dest_y)
                ])

            processed_sites.append({
                'type': 'Feature',
                'geometry': origin_point['geometry'],
                'properties':{
                    'id': origin_point['properties']['id'],
                    'name': origin_point['properties']['name'],
                    'lte_4G': origin_point['properties']['lte_4G'],
                    'exchange_id': exchange['properties']['exchange_id'],
                    'backhaul_length_m': geom.length * 1.60934
                    }
                })

            links.append({
                'type': "Feature",
                'geometry': mapping(geom),
                'properties': {
                    "origin_id": origin_point['properties']['name'],
                    "dest_id": exchange['properties']['exchange_id'],
                    "length": geom.length * 1.60934
                }
            })

        except:
            print('- Problem with straight line link for:')
            print(origin_point['properties'])

    return processed_sites, links


def estimate_exchange_population(exchanges, lads):

    idx = index.Index(
        (i, shape(lad['geometry']).bounds, lad)
        for i, lad in enumerate(lads)
        )

    output = []

    for exchange in exchanges:
        for n in idx.intersection((shape(exchange['geometry']).bounds), objects=True):
            exchange_centroid = shape(exchange['geometry']).centroid
            lad_shape = shape(n.object['geometry'])
            if exchange_centroid.intersects(lad_shape):
                area_weight = (shape(exchange['geometry']).area / lad_shape.area)
                output.append({
                    'type': exchange['type'],
                    'geometry': exchange['geometry'],
                    'properties':{
                        'id': exchange['properties']['id'],
                        'population': n.object['properties']['population'] * area_weight
                        },
                    })

    return output


def write_shapefile(data, directory, filename, crs):
    """
    Write geojson data to shapefile.

    """
    prop_schema = []
    for name, value in data[0]['properties'].items():
        fiona_prop_type = next((
            fiona_type for fiona_type, python_type in \
                fiona.FIELD_TYPES_MAP.items() if \
                python_type == type(value)), None
            )

        prop_schema.append((name, fiona_prop_type))

    sink_driver = 'ESRI Shapefile'
    sink_crs = {'init': crs}
    sink_schema = {
        'geometry': data[0]['geometry']['type'],
        'properties': OrderedDict(prop_schema)
    }

    if not os.path.exists(directory):
        os.makedirs(directory)

    with fiona.open(
        os.path.join(directory, filename), 'w',
        driver=sink_driver, crs=sink_crs, schema=sink_schema) as sink:
        for datum in data:
            sink.write(datum)


def csv_writer(data, directory, filename):
    """
    Write data to a CSV file path

    """
    # Create path
    if not os.path.exists(directory):
        os.makedirs(directory)

    fieldnames = []
    for name, value in data[0].items():
        fieldnames.append(name)

    with open(os.path.join(directory, filename), 'w') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames, lineterminator = '\n')
        writer.writeheader()
        writer.writerows(data)


if __name__ == "__main__":

    start = time.time()

    crs = 'epsg:27700'
    directory = os.path.join(BASE_PATH, 'processed')
    print('Output directory will be {}'.format(directory))

    print('Loading local authority district shapes')
    lads = read_lads()#[:20]

    print('Loading lad population data')
    path = os.path.join(DATA_RAW, 'population', 'lad_demand2015.csv')
    population_data = load_population_data(path)

    print('Adding population to lads')
    lads = add_population_to_lads(lads, population_data)

    print('Loading lad lookup')
    lad_lut = lad_lut(lads)

    if not os.path.exists(os.path.join(directory, 'postcode_sectors.shp')):

        print('Loading raw postcode sector shapes')
        path = os.path.join(DATA_RAW, 'shapes', 'PostalSector.shp')
        postcode_sectors = read_shapes(path)

        print('Adding lad IDs to postcode sectors... might take a few minutes...')
        postcode_sectors = add_lad_to_postcode_sector(postcode_sectors, lads)

        print('Writing postcode sectors to shapefile')
        write_shapefile(postcode_sectors, directory, 'postcode_sectors.shp', crs)

    else:

        print('Loading processed postcode sector shapes')
        path = os.path.join(directory, 'postcode_sectors.shp')
        postcode_sectors = read_shapes(path)

    print('Loading in population weights' )
    weights = load_in_weights()

    print('Adding weights to postcode sectors')
    postcode_sectors = add_weights_to_postcode_sector(postcode_sectors, weights)

    print('Disaggregate 4G coverage to postcode sectors')
    postcode_sectors = allocate_4G_coverage(postcode_sectors, lad_lut)

    # print('Importing sitefinder data')
    # folder = os.path.join(DATA_RAW, 'sitefinder')
    # sitefinder_data = import_sitefinder_data(os.path.join(folder, 'sitefinder.csv'))[:200]

    # print('Preprocessing sitefinder data with 50m buffer')
    # sitefinder_data = process_asset_data(sitefinder_data)

    # if not os.path.exists(os.path.join(directory, 'perimeter.shp')):

    #     print('Generating perimeter')
    #     perimeter = generate_perimeter(lads)

    #     print('Writing perimeter to shapefile')
    #     write_shapefile(perimeter, directory, 'perimeter.shp', crs)

    # else:

    #     print('Loading processed perimeter')
    #     path = os.path.join(directory, 'perimeter.shp')
    #     perimeter = read_shapes(path)

    # print('Calculate population by site')
    # voronoi_site_areas = generate_site_areas(sitefinder_data, perimeter)

    # print('Writing processed sites to shapefile')
    # write_shapefile(voronoi_site_areas, directory, 'site_areas.shp', crs)

    # print('Allocate 4G coverage to sites from postcode sectors')
    # processed_sites = add_coverage_to_sites(sitefinder_data, postcode_sectors)

    # print('Calculate population by site')
    # processed_sites = estimate_site_population(processed_sites, lads)


    print('Reading exchanges')
    exchanges = read_exchanges()

    # print('Generating straight line distance from each site to the nearest exchange')
    # processed_sites, backhaul_links = generate_link_straight_line(processed_sites, exchanges)

    print('Reading exchange areas')
    exchange_areas = read_exchange_areas()

    print('Calculate population by exchange')
    exchange_areas = estimate_exchange_population(exchange_areas, lads)

    print('Writing processed exchange areas to shapefile')
    write_shapefile(exchange_areas, directory, 'exchange_areas.shp', crs)

    # print('Writing processed sites to shapefile')
    # write_shapefile(processed_sites, directory, 'processed_sites.shp', crs)

    # print('Writing backhaul links to shapefile')
    # write_shapefile(backhaul_links, directory, 'backhaul_links.shp', crs)

    end = time.time()
    print('time taken: {} minutes'.format(round((end - start) / 60,2)))
