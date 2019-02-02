import networkx
from geopy.distance import vincenty

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

def main():
    # create complete graph
    graph = networkx.complete_graph(len(PREMISES) + len(DISTRIBUTION_POINT))

    # relabel nodes
    mapping = {}
    for i, node in enumerate(PREMISES + DISTRIBUTION_POINT):
        mapping[i] = node['properties']['name']
    graph = networkx.relabel_nodes(graph, mapping)

    node_lookup = {}
    for node in PREMISES + DISTRIBUTION_POINT:
        name = node['properties']['name']
        node_lookup[name] = node

    # set up edges with distance
    for u, v in graph.edges:
        u_geom = node_lookup[u]['geometry']['coordinates']
        v_geom = node_lookup[v]['geometry']['coordinates']
        graph.edges[u, v]['weight'] = distance(u_geom, v_geom)

    # print complete graph with distances
    print(list(graph.edges(data=True)))

    # print mst
    mst = networkx.minimum_spanning_edges(graph)
    print(list(mst))

def distance(a, b):
    return vincenty(tuple(a), tuple(b)).kilometers

if __name__ == '__main__':
    main()