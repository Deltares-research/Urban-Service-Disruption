# Accessibility and road-disruption analyses

This folder contains exploratory analyses of how disruption to the road network
can affect access to critical services and how demand is distributed across
roads. The work uses the [Deltares RA2CE repository](https://github.com/Deltares/ra2ce)
as its modelling context.

## Analyses

| Notebook | Scenario and purpose |
| --- | --- |
| `population_accessibility_driving.ipynb` | Baseline accessibility by driving. |
| `population_accessibility_walking.ipynb` | Baseline accessibility by walking. Treats the network as undirected and assigns a uniform walking speed to road segments. |
| `Hazard_population_accessibility_driving.ipynb` | Accessibility by driving under a flood-disruption scenario. Applies the notebook's flood threshold and removes disrupted roads from the routing network. |
| `Hazard_population_accessibility_walking.ipynb` | Accessibility by walking under the same hazard scenario. Uses an undirected network and uniform walking speed; reuses hazard-prepared inputs from the driving analysis. |
| `road_prioritization.ipynb` | Exploratory road cleanup and prioritization, with a focus on roads that are both flood-exposed and in high demand, and on equity considerations. |

The accessibility notebooks connect population-bearing hexagons (origins) and
critical infrastructure (destinations) to a road network, calculate shortest
paths weighted by travel time, and aggregate population demand onto road
segments. They also report network distance and accessibility by service
category.

## Shared code

- `functions.py` provides reusable network preparation, point-to-network
  connection, shortest-path, demand-aggregation, and category-specific
  accessibility helpers.
- `simplify.py` provides GeoDataFrame geometry-cleanup helpers, including
  removing small polygons and duplicate or contained features.

## Inputs and outputs

The notebooks expect study-area data that is not stored in this folder. Inputs
include a road graph and study-area boundary, a population hex grid, critical
infrastructure locations, and flood exposure data for hazard scenarios. The
notebooks write derived network, demand, and accessibility layers (GeoPackage
and GeoJSON) to the configured outputs directory.

## Running the notebooks

1. Set up a Python environment with the geospatial and network-analysis packages
   imported by the notebooks, including GeoPandas, Shapely, igraph, xarray,
   `snkit`, and `exactextract`.
2. Update the `root_dir` and any input/output paths in each notebook to point
   to your local study-area data. The current notebooks contain
   machine-specific paths, so they will not run unchanged on another machine.
3. Run the baseline notebook for the selected travel mode. For hazard scenarios,
   prepare the flood-related inputs first; run the driving hazard notebook
   before the walking hazard notebook, which reuses its hazard-prepared data.
4. Review the configured coordinate reference systems, travel speeds, and flood
   threshold before interpreting results.

The notebooks are research workflows rather than a packaged command-line
pipeline: their inputs, parameters, and intermediate outputs are configured in
notebook cells and may need adjustment for a different study area.
