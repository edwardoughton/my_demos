import geopandas
import matplotlib.pyplot
import snkit
import networkx

from shapely.geometry import shape
from geopy.distance import vincenty
from boltons.iterutils import pairwise
from heapq import heappush, heappop
from itertools import count

PREMISES = [
    {
        "type": "Feature",
        "geometry":{
            "type": "Point",
            "coordinates": [0.129960, 52.220977]
        },
        "properties": {
            "name": "premises_1",
            "link": "distribution_point"
        }
    },
    {
        "type": "Feature",
        "geometry":{
            "type": "Point",
            "coordinates": [0.130056, 52.220895]
        },
        "properties": {
            "name": "premises_2",
            "link": "distribution_point"
        }
    },
    {
        "type": "Feature",
        "geometry":{
            "type": "Point",
            "coordinates": [0.130318, 52.220782]
        },
        "properties": {
            "name": "premises_3",
            "link": "distribution_point"
        }
    },
]

DISTRIBUTION_POINT = [
    {
        "type": "Feature",
        "geometry":{
            "type": "Point",
            "coordinates": [0.130258, 52.220494]
        },
        "properties": {
            "name": "distribution_point",
            "link": ""
        }
    }
]

ROADS = [
    {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [0.129671, 52.220926],
                [0.130470, 52.220341]
            ]
        }
    }
]

def main():
    edges = geopandas.GeoDataFrame.from_features(ROADS)
    nodes = geopandas.GeoDataFrame.from_features(DISTRIBUTION_POINT + PREMISES)
    network = snkit.Network(nodes, edges)
    print("\n# init\n")
    print(network.nodes)
    print(network.edges)
    plot(network)

    # add endpoints
    network = snkit.network.add_endpoints(network)

    # snap to nearest edge
    print("\n# snap to nearest edge\n")
    network = snkit.network.link_nodes_to_nearest_edge(network)

    # add node ids and edge to_id/from_id
    network = snkit.network.add_ids(network)
    network = snkit.network.add_topology(network)
    print(network.nodes)
    print(network.edges)
    plot(network)

    # approx min tree

    # construct graph
    edges = list(network.edges.iterfeatures())
    nodes = list(network.nodes.iterfeatures())
    graph = networkx.Graph()
    for node in nodes:
        graph.add_node(node['properties']['id'], **node['properties'])
    for edge in edges:
        graph.add_edge(
            edge['properties']['from_id'],
            edge['properties']['to_id'],
            length=line_length(shape(edge['geometry']))
        )

    source_id = None
    sink_ids = []
    for node in nodes:
        if node['properties']['name'] == 'distribution_point':
            source_id = node['properties']['id']
        if node['properties']['name'] in ['premises_1', 'premises_2', 'premises_3']:
            sink_ids.append(node['properties']['id'])

    # key function - uses shortest paths over network, but deduplicated
    tree = shortest_path_tree(graph, source_id, sink_ids)

    print(tree.nodes)  # node ids
    print(tree.edges)  # edges as from-to node ids

    # recover features
    tree_nodes = [
        node for node in nodes
        if node['properties']['id'] in tree.nodes
    ]

    tree_edges = []
    for edge in edges:
        a = edge['properties']['from_id']
        b = edge['properties']['to_id']

        if (a, b) in tree.edges or (b, a) in tree.edges:
            tree_edges.append(edge)

    # as gdf again for ease of plotting
    network = snkit.Network(
        geopandas.GeoDataFrame.from_features(tree_nodes),
        geopandas.GeoDataFrame.from_features(tree_edges)
    )
    plot(network)
    print(tree_edges)
    print(tree_nodes)

def shortest_path_tree(G, source, sinks):
    """Shortest path tree through a graph from source to sinks

    Based on networkx omplementation of Dijkstra's algorithm
    (see https://networkx.github.io/documentation/networkx-1.10/_modules/networkx/algorithms/shortest_paths/weighted.html)

    """
    G_succ = G.succ if G.is_directed() else G.adj

    push = heappush
    pop = heappop
    dist = {}  # dictionary of final distances
    pred = {source: []}  # dictionary of predecessors
    seen = {source: 0}
    c = count()
    fringe = []  # use heapq with (distance,label) tuples
    push(fringe, (0, next(c), source))
    targets = set(sinks)

    def get_weight(v, u, e):
        return e['length']

    # could parameterise and set to total distance cutoff if not essential to hit all targets
    cutoff = None

    while fringe:
        (d, _, v) = pop(fringe)
        if v in dist:
            continue  # already searched this node.
        dist[v] = d
        if v in targets:
            targets.remove(v) # reached a target
            if not targets:
                break # stop if all reached

        for u, e in G_succ[v].items():
            cost = get_weight(v, u, e)
            if cost is None:
                continue
            vu_dist = dist[v] + get_weight(v, u, e)
            if cutoff is not None:
                if vu_dist > cutoff:
                    continue
            if u in dist:
                if vu_dist < dist[u]:
                    raise ValueError('Contradictory paths found:',
                                     'negative weights?')
            elif u not in seen or vu_dist < seen[u]:
                seen[u] = vu_dist
                push(fringe, (vu_dist, next(c), u))
                pred[u] = [v]

            elif vu_dist == seen[u]:
                pred[u].append(v)

    # work back from targets through their predecessors
    tree = networkx.Graph()
    for u in sinks:
        tree.add_node(u)
        while True:
            v = pred[u][0]
            tree.add_node(v)
            tree.add_edge(v, u)
            if v == source:
                break
            u = v

    return tree

def line_length(line, ellipsoid='WGS-84'):
    """Length of a line in meters, given in geographic coordinates.

    Adapted from https://gis.stackexchange.com/questions/4022/looking-for-a-pythonic-way-to-calculate-the-length-of-a-wkt-linestring#answer-115285

    Args:
        line: a shapely LineString object with WGS-84 coordinates.
        ellipsoid: string name of an ellipsoid that `geopy` understands
            (see http://geopy.readthedocs.io/en/latest/#module-geopy.distance).
    Returns:
        Length of line in kilometers.

    Depends on:
        from geopy.distance import vincenty
        from boltons.iterutils import pairwise
    """

    if line.geometryType() == 'MultiLineString':
        return sum(line_length(segment) for segment in line)

    return sum(
        vincenty(tuple(reversed(a)), tuple(reversed(b)), ellipsoid=ellipsoid).kilometers
        for a, b in pairwise(line.coords)
    )

def plot(network):
    fig, ax = matplotlib.pyplot.subplots()
    ax.set_aspect('equal')
    network.edges.plot(ax=ax, color='black', zorder=1)
    network.nodes.plot(ax=ax, marker='o', color='red', markersize=9, zorder=2)
    matplotlib.pyplot.show()



if __name__ == '__main__':
    main()