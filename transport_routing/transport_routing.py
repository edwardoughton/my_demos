import sys, os
import configparser
import fiona
import osmnx as ox
import networkx as nx
from shapely.geometry import shape, Polygon, mapping 
from shapely.ops import split
from collections import OrderedDict
from rtree import index
from pyproj import Proj, transform

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), 'script_config.ini'))
BASE_PATH = CONFIG['file_locations']['base_path']

#data soruces locations
DATA_SHAPE_INPUTS = os.path.join(BASE_PATH)
DATA_OUTPUTS = os.path.join(BASE_PATH, 'results')

#projections for use
projOSGB1936 = Proj(init='epsg:27700')
projWGS84 = Proj(init='epsg:4326')

def load_area_shapes():
    with fiona.open(os.path.join(DATA_SHAPE_INPUTS, 'tempro2_cambridge', 'tempore2_cambridge_27700.shp'), 'r') as source:
        return [shape for shape in source]

def change_crs(data, existing_proj, desired_proj):
    """
    Changes Coordinate Reference System from existing projection to desired projection.
    """

    changed_crs_data = []
    new_coords = []

    #convert from existing proj to desired proj
    for datum in data:
        for coord in datum['geometry']['coordinates']:
            x, y = transform(existing_proj, desired_proj, coord[0], coord[1])
            new_coords.append((x,y))
        
        changed_crs_data.append({
            'type': datum['type'],
            'geometry': {
                "type": datum['geometry']['type'],
                "coordinates": new_coords, 
            },
            'properties': datum['properties']
        })

    return changed_crs_data

def generate_link_shortest_path(origin, destination):

    ox.config(log_file=False, log_console=False, use_cache=True)

    #get coordinates
    origin_x = shape(origin['geometry']).bounds[0]
    origin_y = shape(origin['geometry']).bounds[1]

    dest_x = shape(destination['geometry']).bounds[0]
    dest_y = shape(destination['geometry']).bounds[1]

    #now sort coordinates to get bbox edges
    x_coordinates = []
    y_coordinates = []

    x_coordinates.extend([origin_x, dest_x])
    y_coordinates.extend([origin_y, dest_y])

    x_min, x_max = min(x_coordinates), max(x_coordinates) 
    y_min, y_max = min(y_coordinates), max(y_coordinates)

    #create OSMnx graph
    G = ox.graph_from_bbox(y_max, y_min, x_max, x_min, network_type='all', truncate_by_edge=True, clean_periphery=True)

    point1 = (origin_y, origin_x)
    point2 = (dest_y, dest_x)

    origin_node = ox.get_nearest_node(G, point1)
    destination_node = ox.get_nearest_node(G, point2)

    try:
        if origin_node != destination_node:
            # Find the shortest path over the network between these nodes
            route = nx.shortest_path(G, origin_node, destination_node, weight='length')

            # Retrieve route nodes and lookup geographical location
            routeline = []
            routeline.append((origin_x, origin_y))
            for node in route:
                routeline.append((G.nodes[node]['x'], G.nodes[node]['y']))
            routeline.append((dest_x, dest_y))
            line = routeline
        else:
            line = [(origin_x, origin_y), (dest_x, dest_y)]
    except nx.exception.NetworkXNoPath:
        line = [(origin_x, origin_y), (dest_x, dest_y)]

    # Map to line
    output = {
        'type': "Feature",
        'geometry': {
            "type": "LineString",
            "coordinates": line
        },
        'properties': {
            "origin": origin['properties']['id'],
            "dest": destination['properties']['id'],
            "volume": origin['properties']['volume'],
        }
    }

    return output

def find_line_length(data):

    output = []

    for datum in data:
        datum_shape = shape(datum['geometry'])
        output.append({
        'type': "Feature",
        'geometry': {
            "type": "LineString",
            "coordinates": datum['geometry']['coordinates']
        },
        'properties': {
            "origin": datum['properties']['origin'],
            "dest": datum['properties']['dest'],
            "volume": datum['properties']['volume'],
            "length": int(round(datum_shape.length, 0)),
            "vehicle_density": round(datum['properties']['volume']/datum_shape.length, 5)
        }
    })

    return output

def route_generation(flows):

    results = []

    for flow in flows:

        origin = {
                    'type': "Feature",
                    'geometry': {
                        "type": "Point",
                        "coordinates": [float(flow['node_a_lon']), float(flow['node_a_lat'])]
                    },
                    'properties': {
                        'id': flow['id'],
                        'volume': flow['volume']
                    }
                }

        destination = {
            'type': "Feature",
            'geometry': {
                "type": "Point",
                "coordinates": [float(flow['node_b_lon']), float(flow['node_b_lat'])]
            },
            'properties': {
                'id': flow['id'],
                'volume': flow['volume']
            }
        }

        results.append(generate_link_shortest_path(origin, destination))

    return results

def cut_routes_by_area(routes, areas):
    
    cut_routes = []

    # Initialze Rtree
    idx = index.Index()
    [idx.insert(0, shape(route['geometry']).bounds, route) for route in routes]

    for area in areas:
        for n in idx.intersection((shape(area['geometry']).bounds), objects=True):
            area_shape = shape(area['geometry'])
            route_shape = shape(n.object['geometry'])
            split_routes = split(route_shape, area_shape)
            for route in split_routes:
                if area_shape.contains(route):             
                    cut_routes.append({
                        'type': n.object['type'],
                        'geometry': mapping(route), 
                        'properties': n.object['properties']
                        })

    print('cut_routes is {} long'.format(len(cut_routes)))
    return cut_routes

def intersect_routes_with_shapes(routes, areas):

    joined_routes_and_areas = []

    # Initialze Rtree
    idx = index.Index()
    [idx.insert(0, shape(route['geometry']).bounds, route) for route in routes]

    for area in areas:
        for n in idx.intersection((shape(area['geometry']).bounds), objects=True):
            area_shape = shape(area['geometry'])
            route_shape = shape(n.object['geometry'])
            if area_shape.contains(route_shape):
                length = n.object['properties']['length']
                vehicle_density = n.object['properties']['vehicle_density']
                vehicles = length * vehicle_density
                n.object['properties']['vehicles'] += vehicles 
                joined_routes_and_areas.append(n.object)

    return joined_routes_and_areas

####################
#### WRITE OUT FILES
####################

def write_shapefile(data, crs, filename):
    print(data[0]['properties'].items())
    # Translate props to Fiona sink schema
    prop_schema = []
    for name, value in data[0]['properties'].items():
        fiona_prop_type = next((fiona_type for fiona_type, python_type in fiona.FIELD_TYPES_MAP.items() if python_type == type(value)), None)
        prop_schema.append((name, fiona_prop_type))

    sink_driver = 'ESRI Shapefile'
    sink_crs = {'init': crs}
    sink_schema = {
        'geometry': data[0]['geometry']['type'],
        'properties': OrderedDict(prop_schema)
    }

    # Create path
    directory = os.path.join(DATA_OUTPUTS)
    if not os.path.exists(directory):
        os.makedirs(directory)

    print(os.path.join(directory, filename))
    # Write all elements to output file
    with fiona.open(os.path.join(directory, filename), 'w', driver=sink_driver, crs=sink_crs, schema=sink_schema) as sink:
        [sink.write(feature) for feature in data]

####################
#### TEST DATA
####################

flows = [
    {
        'id': 1,
        'node_a_lat': 52.210981,
        'node_a_lon': 0.091767,
        'node_b_lat': 52.216866,
        'node_b_lon': 0.123119,
        'volume': 200,
    },
    {
        'id': 2,
        'node_a_lat': 52.216866,
        'node_a_lon': 0.123119,
        'node_b_lat': 52.210981,
        'node_b_lon': 0.091767,
        'volume': 200,
    }
]

####################
#### RUN SCRIPT
####################

#load shapes
area_shapes = load_area_shapes()

#generate routes
routes = route_generation(flows)

#change from Euclidean Distance/Linear distance to Great-circle distance
routes = change_crs(routes, projWGS84, projOSGB1936)

#add the length and density property to each route
routes = find_line_length(routes)

routes = cut_routes_by_area(routes, area_shapes)

# #inersect routes with areas
# output = intersect_routes_with_shapes(routes, area_shapes)

#write shapes
write_shapefile(routes, 'epsg:27700', 'routing.shp')