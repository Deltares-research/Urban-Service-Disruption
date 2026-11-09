import numpy as np
import geopandas as gpd
from tqdm.auto import tqdm
import pandas as pd
import shapely
from pyproj import Geod


def create_demand_to_Critical_Infra(nb_origins, nb_destinations, distance_matrix, node_pop_origin):
    """This function creates a demand matrix from the equation:
    
    Demand_a,b = Population_a * Population_b * e^ [-p * Distance_a,b] 
    
    -p is set to 1, populations represent the grid square of the origin,
    and destinations represent Critical_Infra.

    Args:
        nb_origins (int): number of origin nodes
        nb_destinations (int): number of destination nodes
        distance_matrix (np.matrix): A shortest path matrix used for the distance calculation
        node_pop_origin (list): population per origin node

    Returns:
        demand (np.ndarray) : A matrix with demand calculations for each OD pair
    """    
    demand = np.zeros((nb_origins, nb_destinations))

    dist_decay = 1
    maxtrips = 25000
    normalized_dist = distance_matrix / distance_matrix.max()
    
    # NO EXPONENTIAL DECAY FOR TRIP FROM POP CENTER TO Critical_Infra
    for o in tqdm(range(0, nb_origins), total=nb_origins):
        for d in range(0, nb_destinations):
            demand[o][d] = ((node_pop_origin[o] * 1))

    demand = ((demand / demand.max()) * maxtrips)
    demand = np.ceil(demand).astype(int)
    return demand


def run_shortest_path_edges_fast(graph, vertex_O_ids: list[int], vertex_D_ids, weight='time'):
    """
    Returns a matrix where entry M[i,j] is the list of edge IDs
    travelled in the shortest path from OD_nodes[i] to OD_nodes[j].
    """

    path_edges_id_matrix = np.zeros((len(vertex_O_ids), 1), dtype=object)
    for i,vertex_i in enumerate(tqdm(vertex_O_ids, desc="Computing shortest paths")):
        distances = graph.distances((vertex_i), vertex_D_ids, weights='time')
        min_index = np.argmin(distances)
        edges_path = graph.get_shortest_path(
            vertex_i,
        to=vertex_D_ids[min_index], 
        weights='time', mode='in', output='epath'
        )    
        path_edges_id_matrix[i, 0] = edges_path  
    return path_edges_id_matrix


#### Helper functions for category workflow (no logic changes)

def category_slug(cat):
    return str(cat).strip().lower().replace(' ', '_').replace('/', '_')


def canonical_geometry_key(geom):
    """Direction-independent geometry key: identical for a line and its
    reversed (opposite-direction) counterpart, so forward/reverse copies
    of the same physical road segment collapse into a single group when
    aggregating edge-level demand instead of being counted separately."""
    coords = tuple(geom.coords)
    if coords[0] > coords[-1]:
        coords = coords[::-1]
    return geom.__class__(coords).wkt


def prepare_grouped_destinations_for_category(Critical_Infra, cat, nodes, nodes_sindex, crs_wgs84, crs_metric):
    Critical_Infra_cat = Critical_Infra[Critical_Infra['category'] == cat].copy()
    destinations_gdf_cat = Critical_Infra_cat[['geometry', 'Critical_Infra_id']].copy()
    destinations_gdf_cat['type'] = 'destination'
    destinations_gdf_cat['population'] = 1
    destinations_gdf_cat['category'] = cat

    destinations_metric_cat = gpd.GeoDataFrame(
        destinations_gdf_cat.copy(), geometry='geometry', crs=crs_wgs84
    ).to_crs(crs_metric)

    destinations_gdf_cat['vertex_id'] = destinations_metric_cat.geometry.progress_apply(
        lambda x: nodes.iloc[nodes_sindex.nearest(x)].vertex_id
    ).values

    grouped_destinations_cat = destinations_gdf_cat.groupby('vertex_id').agg({
        'geometry': 'first',
        'population': 'sum',
        'category': 'first',
        # multiple Critical_Infra can snap to the same node - keep all their ids
        'Critical_Infra_id': lambda ids: ';'.join(map(str, ids))
    }).reset_index()
    grouped_destinations_cat['vertex_id'] = grouped_destinations_cat['vertex_id'].astype(int)

    return grouped_destinations_cat


def compute_distance_matrices(graph, source_vertex_ids, target_vertex_ids):
    distance_matrix_cat = np.matrix(graph.distances(
        source=source_vertex_ids,
        target=target_vertex_ids,
        weights='time'
    ))
    od_distances_cat = np.where(np.isinf(distance_matrix_cat), 0, distance_matrix_cat)
    distance_origin_to_nearest_Critical_Infra_cat = np.asarray(distance_matrix_cat.min(axis=1)).ravel()
    return distance_matrix_cat, od_distances_cat, distance_origin_to_nearest_Critical_Infra_cat


def accumulate_edge_metrics(edges, path_edges_id_matrix, od_distances, demand_matrix):
    edges_cat = edges.copy()
    edges_cat['demand_origin_to_Critical_Infra'] = 0.0
    edges_cat['number_of_trips_to_Critical_Infra'] = 0.0
    edges_cat['weighted_demand_origin_to_Critical_Infra'] = 0.0

    n_cat = len(path_edges_id_matrix)
    for i in range(n_cat):
        distances_to_dest_cat = od_distances[i, :]
        j_min_cat = np.argmin(distances_to_dest_cat)
        demand_ij_cat = demand_matrix[i, j_min_cat]

        for edge_id in path_edges_id_matrix[i, 0]:
            edges_cat.iloc[edge_id, edges_cat.columns.get_loc('demand_origin_to_Critical_Infra')] += demand_ij_cat
            edges_cat.iloc[edge_id, edges_cat.columns.get_loc('number_of_trips_to_Critical_Infra')] += 1
            edges_cat.iloc[edge_id, edges_cat.columns.get_loc('weighted_demand_origin_to_Critical_Infra')] += (
                demand_ij_cat * od_distances[i, j_min_cat]
            )

    return edges_cat


def aggregate_edges_by_geometry(edges_cat):
    edges_demand_Critical_Infra_cat = edges_cat.copy()
    if 'geometry_wkt' not in edges_demand_Critical_Infra_cat.columns:
        # Only compute this once per unique edges_cat - callers that already
        # carry a precomputed 'geometry_wkt' column (e.g. the category loop,
        # which reuses one computed once on the full network) skip this
        # expensive per-edge WKT rebuild entirely.
        edges_demand_Critical_Infra_cat['geometry_wkt'] = edges_demand_Critical_Infra_cat.geometry.apply(canonical_geometry_key)

    edges_demand_Critical_Infra_cat = edges_demand_Critical_Infra_cat.groupby('geometry_wkt').agg({
        'from_id': 'first',
        'to_id': 'first',
        'geometry': 'first',
        'osm_id': 'first',
        'demand_origin_to_Critical_Infra': 'sum',
        'number_of_trips_to_Critical_Infra': 'sum',
        'weighted_demand_origin_to_Critical_Infra': 'sum'
    }).reset_index(drop=False)

    return edges_demand_Critical_Infra_cat


def append_category_metrics(edges_demand_by_cat, edges_demand_Critical_Infra_cat, cat_slug):
    demand_col = f"demand_origin_to_Critical_Infra_{cat_slug}"
    trips_col = f"number_of_trips_to_Critical_Infra_{cat_slug}"
    weighted_col = f"weighted_demand_origin_to_Critical_Infra_{cat_slug}"

    metric_lookup = edges_demand_Critical_Infra_cat.set_index('geometry_wkt')
    edges_demand_by_cat[demand_col] = edges_demand_by_cat['geometry_wkt'].map(metric_lookup['demand_origin_to_Critical_Infra']).fillna(0.0)
    edges_demand_by_cat[trips_col] = edges_demand_by_cat['geometry_wkt'].map(metric_lookup['number_of_trips_to_Critical_Infra']).fillna(0.0)
    edges_demand_by_cat[weighted_col] = edges_demand_by_cat['geometry_wkt'].map(metric_lookup['weighted_demand_origin_to_Critical_Infra']).fillna(0.0)

    return edges_demand_by_cat, demand_col, trips_col, weighted_col

def load_and_clip_network(road_file,node_file,area_file,crs_wgs84,crs_metric,area_buffer_m):
    """
    Load road and node network, repair mislabeled CRS if needed,
    reproject everything to a metric CRS, and clip the network
    to an AOI.

    Returns
    -------
    roads : GeoDataFrame
        Clipped road network.
    nodes : GeoDataFrame
        Clipped node network.
    aoi : GeoDataFrame
        Buffered AOI geometry.
    """

    # ====================================================
    # Load road network and nodes
    # ====================================================
    roads = gpd.read_file(road_file)
    nodes = gpd.read_file(node_file)

    print("Road CRS (raw):", roads.crs)
    print("Node CRS (raw):", nodes.crs)
    print("Node bounds (raw):", nodes.total_bounds)

    # ====================================================
    # Fix mislabelled node CRS
    # ====================================================
    xmin, ymin, xmax, ymax = nodes.total_bounds

    looks_like_wgs84 = (
        -180 <= xmin <= 180 and
        -90 <= ymin <= 90 and
        -180 <= xmax <= 180 and
        -90 <= ymax <= 90
    )

    if looks_like_wgs84:
        print("Nodes look like WGS84 but are mislabelled - fixing CRS.")
        nodes = nodes.set_crs(crs_wgs84, allow_override=True)
        nodes = nodes.to_crs(crs_metric)
    else:
        if nodes.crs is None:
            raise RuntimeError("Node CRS is missing.")
        if nodes.crs.to_epsg() != crs_metric:
            raise RuntimeError(f"Unexpected node CRS: {nodes.crs}")

    # Reproject roads if needed
    if roads.crs is None:
        raise RuntimeError("Road CRS is missing.")

    if roads.crs.to_epsg() != crs_metric:
        print(f"Roads are in {roads.crs} - reprojecting to EPSG:{crs_metric}.")
        roads = roads.to_crs(crs_metric)

    print("Node CRS (fixed):", nodes.crs)
    print("Node bounds (fixed):", nodes.total_bounds)
    print("Road CRS (fixed):", roads.crs)

    # ====================================================
    # Enforce integer node IDs
    # ====================================================
    roads["u"] = roads["u"].astype(int)
    roads["v"] = roads["v"].astype(int)
    nodes["node_id"] = nodes["osmid"].astype(int)

    print("Original roads:", len(roads))
    print("Original nodes:", len(nodes))

    # ====================================================
    # Create buffered AOI
    # ====================================================
    area = gpd.read_file(area_file).to_crs(crs_metric)

    aoi_geom = area.geometry.union_all().buffer(area_buffer_m)
    aoi = gpd.GeoDataFrame(
        geometry=[aoi_geom],
        crs=f"EPSG:{crs_metric}"
    )

    print("AOI bounds:", aoi.total_bounds)

    # ====================================================
    # Clip nodes spatially
    # ====================================================
    nodes = (
        gpd.sjoin(
            nodes,
            aoi,
            predicate="intersects",
            how="inner"
        )
        .drop(columns="index_right")
    )

    print("Nodes after clipping:", len(nodes))

    if len(nodes) == 0:
        raise RuntimeError(
            "No nodes intersect AOI - AOI or network is wrong."
        )

    allowed_node_ids = set(nodes["node_id"])

    # ====================================================
    # Clip roads by topology
    # ====================================================
    roads = roads[
        roads["u"].isin(allowed_node_ids) &
        roads["v"].isin(allowed_node_ids)
    ].copy()

    print("Road edges after clipping:", len(roads))

    if len(roads) == 0:
        raise RuntimeError("No roads after topology clip.")

    # Ensure igraph edge indices == roads row indices
    roads = roads.reset_index(drop=True)

    print("Road index reset. Max index:", roads.index.max())

    # Diagnostics
    print("Nodes CRS:", nodes.crs)
    print("AOI CRS:", area.crs)
    print("Nodes bounds:", nodes.total_bounds)
    print("AOI bounds:", area.total_bounds)

    return roads, nodes, aoi


def _is_truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(['1', 'true', 'yes', 'y'])


def prepare_main_network_from_road_file(roads_gdf, nodes_gdf, speed_column, fallback_speed, CRS_Metric, CRS_Wgs84=4326) -> gpd.GeoDataFrame:
    base_network = roads_gdf.copy()

    # Ensure directed endpoint columns exist from the ROAD_FILE graph structure.
    if 'u' not in base_network.columns or 'v' not in base_network.columns:
        raise KeyError("Expected 'u' and 'v' columns in ROAD_FILE.")

    base_network['from_id'] = pd.to_numeric(base_network['u'], errors='coerce').astype('Int64')
    base_network['to_id'] = pd.to_numeric(base_network['v'], errors='coerce').astype('Int64')
    base_network = base_network[base_network['from_id'].notna() & base_network['to_id'].notna()].copy()
    base_network['from_id'] = base_network['from_id'].astype(int)
    base_network['to_id'] = base_network['to_id'].astype(int)

    # Normalize direction-related fields.
    if 'oneway' not in base_network.columns:
        base_network['oneway'] = 'no'
    base_network['oneway'] = base_network['oneway'].astype(str).str.strip().str.lower()

    if 'reversed' in base_network.columns:
        reversed_flag = _is_truthy(base_network['reversed'])
        # If marked reversed, flip endpoints so edge direction follows intended travel direction.
        swap_from = base_network.loc[reversed_flag, 'from_id'].copy()
        base_network.loc[reversed_flag, 'from_id'] = base_network.loc[reversed_flag, 'to_id'].values
        base_network.loc[reversed_flag, 'to_id'] = swap_from.values
        base_network.loc[reversed_flag, 'geometry'] = base_network.loc[reversed_flag, 'geometry'].apply(
            lambda geom: shapely.LineString(list(geom.coords)[::-1]) if geom is not None else geom
        )

    # Safety net: on a small fraction of ROAD_FILE edges, from_id/to_id end up
    # backwards relative to their own geometry even though 'reversed' is falsy
    # (a pre-existing data issue, not something the 'reversed' flag captures).
    # This makes from_id sit at the far end of the line - e.g. a Critical_Infra/origin
    # point that later snaps near that far end gets a "from_id" that looks very
    # far away and in the wrong direction on the map. Detect and correct any
    # remaining mismatch by comparing geometry endpoints to actual node coordinates.
    if nodes_gdf is not None and 'node_id' in nodes_gdf.columns:
        node_xy = dict(zip(nodes_gdf['node_id'], nodes_gdf.geometry.values))
        endpoint_tol_m = 2.0

        def _backwards(row):
            from_pt = node_xy.get(row['from_id'])
            to_pt = node_xy.get(row['to_id'])
            geom = row.geometry
            if from_pt is None or to_pt is None or geom is None:
                return False
            start = shapely.Point(geom.coords[0])
            end = shapely.Point(geom.coords[-1])
            if from_pt.distance(start) <= endpoint_tol_m and to_pt.distance(end) <= endpoint_tol_m:
                return False  # already consistent
            return from_pt.distance(end) <= endpoint_tol_m and to_pt.distance(start) <= endpoint_tol_m

        backwards_mask = base_network.apply(_backwards, axis=1)
        if backwards_mask.any():
            print(f"Correcting {backwards_mask.sum()} edge(s) where from_id/to_id were backwards relative to their geometry.")
            # Geometry is the ground truth here (unlike the 'reversed' branch above,
            # this is a genuine data mislabel), so only swap the id labels - do NOT
            # touch the geometry, or the correction cancels itself out.
            swap_from = base_network.loc[backwards_mask, 'from_id'].copy()
            base_network.loc[backwards_mask, 'from_id'] = base_network.loc[backwards_mask, 'to_id'].values
            base_network.loc[backwards_mask, 'to_id'] = swap_from.values

    # Add reverse edges only for roads that are not one-way.
    two_way_mask = base_network['oneway'].isin(['no', 'false', '0', 'both', 'two_way', 'twoway'])
    reverse_edges = base_network.loc[two_way_mask].copy()
    swap_from = reverse_edges['from_id'].copy()
    reverse_edges['from_id'] = reverse_edges['to_id'].values
    reverse_edges['to_id'] = swap_from.values
    reverse_edges['geometry'] = reverse_edges['geometry'].apply(
        lambda geom: shapely.LineString(list(geom.coords)[::-1]) if geom is not None else geom
    )

    base_network = pd.concat([base_network, reverse_edges], ignore_index=True)

    # Keep a stable OSM identifier if present.
    if 'osm_id' not in base_network.columns:
        if 'osmid' in base_network.columns:
            base_network['osm_id'] = base_network['osmid']
        else:
            base_network['osm_id'] = np.arange(len(base_network))

    # Use only the selected speed column; if missing or invalid, fall back to fallback_speed.
    if speed_column not in base_network.columns:
        print(f"Column '{speed_column}' not found. Using fallback speed {fallback_speed} km/h for all edges.")
        base_network[speed_column] = fallback_speed

    base_network[speed_column] = pd.to_numeric(base_network[speed_column], errors='coerce')
    base_network[speed_column] = base_network[speed_column].fillna(0).replace(0, fallback_speed)

    # Length to km, then compute minutes.
    if 'length' in base_network.columns:
        base_network['road_length'] = pd.to_numeric(base_network['length'], errors='coerce') / 1e3
    else:
        geod = Geod(ellps='WGS84')
        base_network['road_length'] = base_network.geometry.apply(
            lambda line_string: geod.geometry_length(line_string) / 1e3 if line_string is not None else np.nan
        )

    base_network['time'] = (base_network['road_length'] / base_network[speed_column]) * 60.0
    base_network['time'] = base_network['time'].replace([np.inf, -np.inf], np.nan).fillna(0.01)
    base_network.loc[base_network['time'] <= 0, 'time'] = 0.01

    base_network['id'] = np.arange(len(base_network), dtype=int)
    base_network = gpd.GeoDataFrame(base_network, geometry='geometry', crs=CRS_Metric).to_crs(CRS_Wgs84)

    print(f"Prepared directed edges from ROAD_FILE: {len(base_network)}")
    print(f"One-way edges: {(~two_way_mask).sum()}, two-way source edges: {two_way_mask.sum()}")
    if 'reversed' in roads_gdf.columns:
        print(f"Reversed edges in source: {_is_truthy(roads_gdf['reversed']).sum()}")

    return base_network


def prepare_walking_network_from_road_file(roads_gdf, nodes_gdf, walking_speed_kmh, CRS_Metric, CRS_Wgs84=4326) -> gpd.GeoDataFrame:
    """
    Same as prepare_main_network_from_road_file, but for a mode (walking) where
    direction is irrelevant: oneway/reversed flags are ignored, no reverse
    duplicate edges are created (the routing graph is built as undirected),
    and every edge is assigned the same walking_speed_kmh regardless of any
    'avgspeed'-style column.
    """
    base_network = roads_gdf.copy()

    if 'u' not in base_network.columns or 'v' not in base_network.columns:
        raise KeyError("Expected 'u' and 'v' columns in ROAD_FILE.")

    base_network['from_id'] = pd.to_numeric(base_network['u'], errors='coerce').astype('Int64')
    base_network['to_id'] = pd.to_numeric(base_network['v'], errors='coerce').astype('Int64')
    base_network = base_network[base_network['from_id'].notna() & base_network['to_id'].notna()].copy()
    base_network['from_id'] = base_network['from_id'].astype(int)
    base_network['to_id'] = base_network['to_id'].astype(int)

    # Keep a stable OSM identifier if present.
    if 'osm_id' not in base_network.columns:
        if 'osmid' in base_network.columns:
            base_network['osm_id'] = base_network['osmid']
        else:
            base_network['osm_id'] = np.arange(len(base_network))

    speed_column = 'walk_speed'
    base_network[speed_column] = walking_speed_kmh

    # Length to km, then compute minutes.
    if 'length' in base_network.columns:
        base_network['road_length'] = pd.to_numeric(base_network['length'], errors='coerce') / 1e3
    else:
        geod = Geod(ellps='WGS84')
        base_network['road_length'] = base_network.geometry.apply(
            lambda line_string: geod.geometry_length(line_string) / 1e3 if line_string is not None else np.nan
        )

    base_network['time'] = (base_network['road_length'] / base_network[speed_column]) * 60.0
    base_network['time'] = base_network['time'].replace([np.inf, -np.inf], np.nan).fillna(0.01)
    base_network.loc[base_network['time'] <= 0, 'time'] = 0.01

    base_network['id'] = np.arange(len(base_network), dtype=int)
    base_network = gpd.GeoDataFrame(base_network, geometry='geometry', crs=CRS_Metric).to_crs(CRS_Wgs84)

    print(f"Prepared undirected walking edges from ROAD_FILE: {len(base_network)} (walking speed = {walking_speed_kmh} km/h)")

    return base_network


from shapely.ops import substring
from tqdm.auto import tqdm


def connect_points_to_edges(points_gdf, edges_gdf, start_node_id, endpoint_tol_m=1.0,
                             cluster_tol_m=0.0, transfer_speed_kmh=30.0,speed_column='avg_speed'):
    """
    Snap each point to the nearest directed road edge, project it onto that
    edge, and split the edge - and its reverse counterpart, if one exists -
    at the projected location. This creates a real routable node exactly
    where each point connects to the network, while keeping the from_id ->
    to_id direction of every resulting edge segment consistent with the
    edge it was cut from.

    Parameters
    ----------
    points_gdf : GeoDataFrame of points to connect (same CRS as edges_gdf)
    edges_gdf : directed edges GeoDataFrame with 'from_id', 'to_id',
        'geometry' columns (plus any number of attribute columns)
    start_node_id : int, first node id to assign to newly created nodes
    endpoint_tol_m : float, if the nearest point on an edge falls within
        this distance of one of its existing endpoints, the point is
        snapped directly to that existing node instead of creating a new one
    cluster_tol_m : float, default 0.0 (disabled). Some networks contain
        near-duplicate/parallel one-way edges (e.g. a two-way street mapped
        as two separate one-way ways with different node ids, so they are
        not detected as a forward/reverse pair). When > 0, a point that
        lies within `cluster_tol_m` of more than one distinct edge is
        connected to *all* of them, instead of only the single nearest one.
        The extra connections are made via a tiny bidirectional "transfer"
        edge linking the point's primary node to each additional node, so
        the router can freely use whichever direction/edge is cheaper.
    transfer_speed_kmh : float, assumed travel speed used to give the
        synthetic transfer edges (see `cluster_tol_m`) a small, non-zero
        travel time proportional to their (usually tiny) length.

    Returns
    -------
    edges_out : GeoDataFrame, edges_gdf with snapped-to edges replaced by
        their split segments (plus any synthetic transfer edges)
    point_node_ids : list[int], node id each input point connects to
        (aligned with points_gdf row order)
    new_nodes : list[dict], newly created nodes as {'node_id', 'geometry'}
    """
    if points_gdf.crs != edges_gdf.crs:
        raise ValueError("points_gdf and edges_gdf must share the same CRS")

    edges_gdf = edges_gdf.reset_index(drop=True)

    # Group directed edges into (forward, reverse) pairs sharing the same two nodes.
    pair_keys = [tuple(sorted((int(u), int(v))))
                 for u, v in zip(edges_gdf['from_id'], edges_gdf['to_id'])]
    pair_groups = {}
    for pos, key in enumerate(pair_keys):
        pair_groups.setdefault(key, []).append(pos)

    rep_keys = list(pair_groups.keys())
    rep_geoms = [edges_gdf.geometry.iloc[pair_groups[k][0]] for k in rep_keys]
    edge_sindex = shapely.STRtree(rep_geoms)

    next_node_id = start_node_id
    new_nodes = []
    node_geom_lookup = {}
    point_node_ids = [None] * len(points_gdf)
    # All node ids connected for each point, in discovery order (index 0 = primary/nearest).
    node_ids_by_point = [[] for _ in range(len(points_gdf))]
    multi_connect_count = 0

    # Requested split distances (along the representative geometry) per rep index.
    # Each request is (point_i, proj_dist).
    splits_per_rep = {}

    for i, point in enumerate(tqdm(points_gdf.geometry.values, desc="Snapping points to edges")):
        rep_idx = int(edge_sindex.nearest(point))
        candidate_idxs = [rep_idx]

        if cluster_tol_m > 0:
            nearest_dist = shapely.distance(point, rep_geoms[rep_idx])
            nearby = edge_sindex.query(point, predicate="dwithin", distance=nearest_dist + cluster_tol_m)
            extra = sorted(int(j) for j in nearby if int(j) != rep_idx)
            if extra:
                multi_connect_count += 1
                candidate_idxs.extend(extra)

        for cidx in candidate_idxs:
            rep_line = rep_geoms[cidx]
            proj_dist = rep_line.project(point)
            rep_length = rep_line.length

            if proj_dist <= endpoint_tol_m:
                node_id = int(edges_gdf.iloc[pair_groups[rep_keys[cidx]][0]]['from_id'])
                node_geom_lookup.setdefault(node_id, shapely.Point(rep_line.coords[0]))
                node_ids_by_point[i].append(node_id)
            elif proj_dist >= rep_length - endpoint_tol_m:
                node_id = int(edges_gdf.iloc[pair_groups[rep_keys[cidx]][0]]['to_id'])
                node_geom_lookup.setdefault(node_id, shapely.Point(rep_line.coords[-1]))
                node_ids_by_point[i].append(node_id)
            else:
                splits_per_rep.setdefault(cidx, []).append((i, proj_dist))

    replaced_positions = set()
    new_edge_rows = []

    for rep_idx, requests in splits_per_rep.items():
        rep_key = rep_keys[rep_idx]
        rep_line = rep_geoms[rep_idx]
        member_positions = pair_groups[rep_key]

        requests.sort(key=lambda t: t[1])
        merged = []  # list of [distance, [point_indices]]
        for point_i, dist in requests:
            if merged and abs(dist - merged[-1][0]) < endpoint_tol_m:
                merged[-1][1].append(point_i)
            else:
                merged.append([dist, [point_i]])

        split_distances = []
        split_node_ids = []
        for dist, point_indices in merged:
            node_id = next_node_id
            next_node_id += 1
            node_geom = rep_line.interpolate(dist)
            new_nodes.append({'node_id': node_id, 'geometry': node_geom})
            node_geom_lookup[node_id] = node_geom
            for point_i in point_indices:
                node_ids_by_point[point_i].append(node_id)
            split_distances.append(dist)
            split_node_ids.append(node_id)

        for pos in member_positions:
            edge_row = edges_gdf.iloc[pos]
            line = edge_row.geometry
            length = line.length
            same_orientation = line.coords[0] == rep_line.coords[0]

            local_distances = split_distances if same_orientation else [length - d for d in split_distances]
            ordered = sorted(zip(local_distances, split_node_ids), key=lambda t: t[0])

            node_chain = [int(edge_row['from_id'])] + [nid for _, nid in ordered] + [int(edge_row['to_id'])]
            boundary_distances = [0.0] + [d for d, _ in ordered] + [length]

            for k in range(len(node_chain) - 1):
                seg = edge_row.copy()
                seg['from_id'] = node_chain[k]
                seg['to_id'] = node_chain[k + 1]
                seg['geometry'] = substring(line, boundary_distances[k], boundary_distances[k + 1])
                if 'road_length' in seg.index:
                    seg['road_length'] = seg['geometry'].length / 1000.0
                if 'time' in seg.index:
                    spd = seg[speed_column] if speed_column in seg.index and seg[speed_column] else transfer_speed_kmh
                    seg['time'] = max((seg['geometry'].length / 1000.0 / spd) * 60.0, 0.01)
                new_edge_rows.append(seg)

        replaced_positions.update(member_positions)

    # Resolve the primary node id per point (first discovered = nearest edge) and,
    # when cluster_tol_m connected a point to more than one distinct edge, build a
    # tiny bidirectional transfer edge linking the primary node to each extra node
    # so the router can use whichever edge/direction is actually cheaper.
    transfer_rows = []
    template_row = edges_gdf.iloc[0]
    seen_transfer_pairs = set()
    for i, ids in enumerate(node_ids_by_point):
        deduped = list(dict.fromkeys(ids))  # preserve discovery order, drop duplicates
        if not deduped:
            continue
        primary_id = deduped[0]
        point_node_ids[i] = primary_id
        for other_id in deduped[1:]:
            pair_key = tuple(sorted((primary_id, other_id)))
            if pair_key in seen_transfer_pairs:
                continue
            seen_transfer_pairs.add(pair_key)

            primary_geom = node_geom_lookup.get(primary_id)
            other_geom = node_geom_lookup.get(other_id)
            length_km = (primary_geom.distance(other_geom) / 1000.0) if primary_geom is not None and other_geom is not None else 0.0
            time_min = max((length_km / transfer_speed_kmh) * 60.0, 0.01)
            transfer_geom = shapely.LineString([primary_geom, other_geom]) if primary_geom is not None and other_geom is not None else None

            for a, b in ((primary_id, other_id), (other_id, primary_id)):
                seg = template_row.copy()
                seg['from_id'] = a
                seg['to_id'] = b
                seg['geometry'] = transfer_geom
                if 'road_length' in seg.index:
                    seg['road_length'] = length_km
                if 'time' in seg.index:
                    seg['time'] = time_min
                if 'osm_id' in seg.index:
                    seg['osm_id'] = -1
                transfer_rows.append(seg)

    if transfer_rows:
        print(f"cluster_tol_m connected {multi_connect_count} point(s) to more than one edge; "
              f"added {len(transfer_rows)} synthetic transfer edge(s).")
        new_edge_rows.extend(transfer_rows)

    keep_mask = np.ones(len(edges_gdf), dtype=bool)
    if replaced_positions:
        keep_mask[list(replaced_positions)] = False

    if new_edge_rows:
        new_edges_gdf = gpd.GeoDataFrame(new_edge_rows, columns=edges_gdf.columns, crs=edges_gdf.crs)
        edges_out = pd.concat([edges_gdf.loc[keep_mask], new_edges_gdf], ignore_index=True)
    else:
        edges_out = edges_gdf.copy()

    edges_out = gpd.GeoDataFrame(edges_out, geometry='geometry', crs=edges_gdf.crs).reset_index(drop=True)
    if 'id' in edges_out.columns:
        edges_out['id'] = np.arange(len(edges_out), dtype=int)

    print(f"Connected {len(points_gdf)} points: {len(new_nodes)} new node(s) created, "
          f"{len(replaced_positions)} edge(s) split into {len(new_edge_rows) - len(transfer_rows)} segments.")

    return edges_out, point_node_ids, new_nodes


