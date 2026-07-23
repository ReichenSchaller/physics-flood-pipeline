# Data

The project data system organizes the spatial inputs, event forcing, validation observations, source archives, and native SFINCS files used by the current Harris County research workflow. The data are kept outside this GitHub repository because the full collection is much larger than the source code and includes products derived from external data providers.

This page explains the current data architecture and catalog contract. It does not provide a step-by-step catalog-building tutorial. A practical **how-to for creating and checking new data catalogs will be maintained in the SFINCS Web Launcher Guide**.


---

## Availability

The complete project datasets are stored in the maintainer's Longleaf user-space data area under `/users`. They are not committed to GitHub because of their size and because some inputs remain subject to the terms of their original data providers.

Rounded working sizes are:

| Data group | Approximate size |
|---|---:|
| Source-oriented Harris County static data | 24 GB |
| Current trusted native PPP static package | 2 GB |
| Typical completed event catalog | 1–2 GB |

Data and associated catalog products are available upon reasonable request from:

**Reichen Schaller**  
**epsilon@unc.edu**

The repository's MIT license applies to repository code and documentation. It does not relicense USGS, NOAA, MRMS, AORC, HCFCD, NLCD, DesignSafe, or other third-party data.

---

## Data architecture

The active data collection follows a staged structure rather than placing every source file directly in a runtime catalog.

```text
Harris County data root
├── raw/                     Original or minimally processed source downloads
├── processed/               Merged, normalized, adjusted, or reusable derivatives
├── catalogs/
│   ├── static/              Domain-wide spatial and native SFINCS inputs
│   └── events/              Event-specific forcing and validation inputs
├── processed_catalog_work/  Staging area before catalog promotion
├── analysis/                Investigations, plots, comparisons, and one-off studies
├── metadata/                Inventories, manifests, source notes, and provenance
├── qa/                      Quality-control products
├── logs/                    Data-preparation logs
└── scripts/                 Data-preparation and audit scripts
```

Only a subset of this tree is used directly during a model run.

```text
Raw or external source
    ↓
Processed and quality-controlled derivative
    ↓
Active static or event catalog product
    ↓
Web Launcher detection and run configuration
    ↓
Frozen run_config.json
    ↓
Generated or imported SFINCS model input
```

The `analysis`, `metadata`, `qa`, and staging branches preserve how a product was constructed and checked. The active runtime interface is primarily the `catalogs/static/` and `catalogs/events/` tree.

---

## Static data

Static data describe the model domain and normally remain unchanged between events. The current implementation contains two different kinds of static authority because Manual and Override workflows prepare models differently.

### Source-oriented static catalog

```text
catalogs/static/harris_county/
```

This approximately 24 GB catalog contains the source-oriented spatial data used by Manual/HydroMT-style model construction. Major categories include:

```text
region geometry
DEM and topobathymetry
grid templates
active-mask products
land cover and Manning reclassification
roughness
curve number and infiltration
open-boundary outlines
static boundary and source points
observation points and cross-section lines
thin dams, levees, weirs, and drainage structures
subgrid source material
vertical-datum notes
metadata, manifests, notes, and audits
```

The source catalog contains files such as rasters, vector layers, reclassification tables, and manifests. HydroMT and the Python backend use these sources to construct a model rather than simply copying a finished SFINCS model package.

### Native SFINCS static package

```text
catalogs/static/harris_county_ppp_latest/
```

This approximately 2 GB package is the current trusted native static authority for Override/Hybrid workflows. Its active model inputs include:

```text
sfincs.dep
sfincs.ind
sfincs.msk
sfincs.manning
sfincs.scs
sfincs.thd
sfincs_subgrid.nc
```

These files already encode the accepted grid, sparse-cell indexing, elevation, mask, Manning roughness, infiltration, thin-dam, and subgrid setup. Override Mode can import them while still generating event-specific dynamic forcing from the selected event catalog.

Other static branches have narrower roles:

| Package | Current role |
|---|---|
| `harris_county` | Source-oriented authority for Manual/HydroMT construction |
| `harris_county_ppp_latest` | Current trusted native static authority for Override/Hybrid runs |
| `harris_county_ppp` | Older or reference native package |
| `_quarantine_outside_detected_sources` | Quarantined material; not an active runtime source |

### Static authority by workflow

| Workflow | Static source | What happens |
|---|---|---|
| Manual | `harris_county` | The backend builds the grid and model inputs from source-oriented data |
| Override/Hybrid | `harris_county_ppp_latest` | Trusted native static files are imported into the run |
| Existing run review | Run-local `model/` files | Review reads the files frozen into that run rather than the current catalog |

A catalog update does not retroactively change an existing run. Each run retains its own configuration, copied or generated model files, scripts, logs, and outputs.

---

## Event catalogs

Event catalogs contain the time-dependent inputs and validation products associated with one flood or storm period.

A typical event catalog follows this structure:

```text
catalogs/events/<event_key>/
├── event_boundary_table/
├── event_discharge/
├── event_discharge_points/
├── event_forcing_qc/
├── event_metadata/
├── event_precip/
├── event_pressure/
├── event_runtime_window/
├── event_source_table/
├── event_validation_gauges/
├── event_validation_lines/
├── event_validation_points/
├── event_waterlevel/
├── event_waterlevel_points/
├── event_wind/
└── _misc/
```

Not every event activates every forcing family. For example, tropical-cyclone catalogs may contain atmospheric wind and pressure forcing, while a non-tropical rainfall event normally leaves those inputs inactive.

The folder layout also exists for future events as a catalog skeleton. A directory existing does not by itself mean that the catalog is ready for a production run.

### Active and administrative products

The runtime convention is:

```text
active top-level files
    current products eligible for catalog detection and model preparation

_misc/
    prior versions, backups, source copies, investigations, and provenance

event_forcing_qc/
    coverage and quality-control evidence

event_metadata/
    event descriptions, source notes, and machine-readable metadata

manifests and inventory reports
    evidence about selection and portability; not model forcing by themselves
```

The active file content is authoritative. Historical filenames may retain older labels or counts for compatibility and should not be interpreted without reading the selected file.

### Complete current catalogs

Fourteen event catalogs are complete for the present Harris County research scope. In this context, **complete** means that the active catalog has the current event forcing, boundary structure, validation inputs, and runtime metadata required by the established workflow.

It does not mean that every simulation has passed scientific validation, that every uncertainty has been removed, or that the catalog can never be revised.

| Event key | Active catalog folder | Working name | Model window |
|---|---|---|---|
| `ike_2008` | `ike_2008` | Hurricane Ike | 2008-09-09 21:00:00 to 2008-09-18 05:00:00 |
| `flood_2009_04` | `flood_2009_04` | April 2009 flood | 2009-04-16 17:00:00 to 2009-04-21 09:00:00 |
| `flood_2012_01` | `flood_2012_01` | January 2012 flood | 2012-01-07 20:00:00 to 2012-01-12 11:00:00 |
| `heavy_rain_2012_07` | `heavy_rain_2012_07` | July 2012 Cypress / northern Harris heavy rainfall | 2012-07-06 17:00:00 to 2012-07-22 05:00:00 |
| `heavy_rain_2014_08` | `heavy_rain_2014_08` | August 2014 heavy rainfall | 2014-07-28 19:00:00 to 2014-09-24 07:00:00 |
| `memorial_2015` | `memorial_2015` | 2015 Memorial Day Flood | 2015-05-20 18:00:00 to 2015-06-02 18:00:00 |
| `halloween_2015` | `halloween_2015` | 2015 Halloween Flood | 2015-10-29 14:00:00 to 2015-11-04 10:00:00 |
| `tax_day_2016` | `tax_day_2016` | 2016 Tax Day Flood | 2016-04-15 23:00:00 to 2016-04-24 02:00:00 |
| `memorial_2016` | `memorial_2016` | 2016 Memorial Day Flood | 2016-05-30 22:00:00 to 2016-06-10 03:00:00 |
| `harvey_2017` | `harvey_2017_mrms` | Hurricane Harvey | 2017-08-22 00:00 to 2017-09-17 01:00:00 |
| `flood_2019_05` | `flood_2019_05` | May 7, 2019 Kingwood / Sugar Land flooding | 2019-05-05 21:00:00 to 2019-05-13 05:00:00 |
| `imelda_2019` | `imelda_2019` | Tropical Storm Imelda | 2019-09-07 09:00:00 to 2019-09-27 13:00:00 |
| `heavy_rain_2024_04_05` | `heavy_rain_2024_04_05` | April-May 2024 heavy rainfall / northeast Harris flooding | 2024-04-28 15:00:00 to 2024-05-08 07:00:00 |
| `beryl_2024` | `beryl_2024` | Hurricane Beryl | 2024-06-21 14:00:00 to 2024-08-03 00:00 |

The working event key `harvey_2017` maps to the active catalog folder `harvey_2017_mrms`, reflecting the MRMS precipitation product used by the current Harvey catalog.

### Next-step catalogs

The remaining 21 working events have catalog skeletons and, in several cases, partial precipitation or atmospheric preparation products. They remain next steps because the full active runtime and validation contract has not yet been completed.

| Event key | Working name | Model window |
|---|---|---|
| `flood_1979_04` | April 1979 Harris County flood | 1979-04-15 17:00:00 to 1979-04-25 15:00:00 |
| `claudette_1979` | Tropical Storm Claudette | 1979-07-16 00:00 to 1979-08-13 00:00 |
| `flood_1979_09` | September 1979 flood; possible Tropical Storm Elena relationship remains to be verified | 1979-09-15 22:00:00 to 1979-09-22 17:00:00 |
| `flood_1981_04` | April-May 1981 flood | 1981-04-29 00:00 to 1981-05-07 07:00:00 |
| `flood_1981_06` | June 1981 flood | 1981-05-28 19:00:00 to 1981-06-09 08:00:00 |
| `td8_1981` | Possible Tropical Depression Eight / August-September 1981 flood | 1981-08-25 13:00:00 to 1981-09-09 01:00:00 |
| `alicia_1983` | Hurricane Alicia | 1983-07-28 05:00:00 to 1983-08-22 04:00:00 |
| `flood_1983_09` | September 1983 flood | 1983-09-14 14:00:00 to 1983-09-23 17:00:00 |
| `flood_1984_10` | October 21-22, 1984 heavy rain and flooding south of Houston | 1984-10-15 20:00:00 to 1984-10-31 07:00:00 |
| `flood_1989_05` | May 1989 flood | 1989-05-10 13:00:00 to 1989-05-21 03:00:00 |
| `allison_1989` | Tropical Storm Allison, 1989 | 1989-06-17 18:00:00 to 1989-07-12 03:00:00 |
| `flood_1989_07` | Late July / early August 1989 flood | 1989-07-30 00:00 to 1989-08-04 18:00:00 |
| `flood_1992_03` | March 4, 1992 Houston/Harris County flood | 1992-03-02 13:00:00 to 1992-03-08 21:00:00 |
| `flood_1994_10` | Southeast Texas Floods of October 1994 | 1994-10-13 08:00:00 to 1994-10-25 03:00:00 |
| `frances_1998` | Tropical Storm Frances | 1998-09-01 20:00:00 to 1998-09-22 15:00:00 |
| `flood_1998_10` | October 1998 flood / post-Frances fall storm | 1998-10-15 11:00:00 to 1998-10-23 04:00:00 |
| `allison_2001` | Tropical Storm Allison | 2001-05-23 04:00:00 to 2001-06-14 05:00:00 |
| `flood_2002_10` | October 28-29, 2002 Houston/Harris flooding | 2002-10-17 11:00:00 to 2002-10-31 17:00:00 |
| `flood_2003_11` | November 17, 2003 flood / severe-weather event | 2003-11-14 17:00:00 to 2003-11-20 17:00:00 |
| `heavy_rain_2006_06` | June 2006 heavy rainfall | 2006-06-14 12:00:00 to 2006-06-25 05:00:00 |
| `erin_2007` | Tropical Storm Erin / August 2007 flood | 2007-08-10 23:00:00 to 2007-09-20 23:00:00 |

Working labels that contain words such as “possible,” “unnamed,” or “verify” are intentionally provisional. They describe the current event-identification state rather than a finalized meteorological classification.

---

## Event forcing

The current event-catalog design separates forcing by physical role.

| Catalog component | Purpose |
|---|---|
| `event_precip` | Gridded precipitation over the event runtime |
| `event_waterlevel` | Time-varying open-boundary water levels |
| `event_waterlevel_points` | Coordinates and identities associated with water-level series |
| `event_boundary_table` | Canonical boundary order and model coordinates |
| `event_discharge` | Time-varying discharge where the workflow uses source forcing |
| `event_discharge_points` / `event_source_table` | Source-point identities and locations |
| `event_wind` | Gridded wind forcing for applicable events |
| `event_pressure` | Gridded atmospheric pressure forcing for applicable events |
| `event_runtime_window` | Approved reference, start, and stop times |
| `event_forcing_qc` | Coverage and preparation evidence |

The current source pattern is intentionally described cautiously:

- **MRMS** supplies the active radar-based precipitation product for Hurricane Harvey.
- **AORC** supplies precipitation and, where applicable, atmospheric forcing used in many other event preparations.
- **NOAA** supplies coastal water-level observations.
- **USGS** supplies inland gauge-height and discharge records.
- **HCFCD** contributes Harris County spatial and hydrologic source material and inherited project references.
- **NLCD** supplies land-cover information used in static roughness preparation.
- **DesignSafe** is the source of the curated elevation product used by the current Harris County setup.

Only sources evidenced in current filenames, manifests, metadata, or catalog records are named here.

---

## Canonical water-level boundary setup

The 14 complete event catalogs use the same three active water-level boundary identities and order:

| Order | Station | Role | Modeled boundary coordinate |
|---:|---|---|---|
| 1 | `8771013` — Eagle Point | Coastal water-level boundary | `306350.0, 3268250.0` |
| 2 | `8770613` — Morgan's Point / Barbours Cut | Coastal water-level boundary | `308450.0, 3285050.0` |
| 3 | `08072050` — Lake Houston / San Jacinto near Sheldon | Inland water-level boundary | `297850.0, 3306950.0` |

The active event-water-level table uses:

```text
time,8771013,8770613,08072050
```

Manchester station `8770777` is not an active boundary in the current contract. It may remain useful as an observation, comparison location, or provenance source, but it is excluded from the active generated boundary geometry and water-level forcing.

The boundary series preserve event-specific hydrographs and event windows. The standardization applies to station identity, order, coordinates, and accepted datum handling; it does not replace every event with one universal water-level time series.

### Coastal datum conventions

The current boundary conventions are:

```text
Eagle Point:
    NOAA MSL + 0.10668 m → project NAVD88 convention

Morgan's Point:
    NOAA NAVD series as supplied for the project workflow

Lake Houston:
    USGS parameter 00065 with accepted event-specific gap handling
```

The physical NOAA instrument coordinates do not have to coincide with the modeled boundary coordinates. Boundary points are placed on the model's active open boundary, while the observed time series represents the selected physical station.

---

## Validation data

Validation data are maintained as a separate but connected data layer. They are not model forcing merely because they live in an event catalog.

The current setup combines:

```text
a reusable USGS master archive
site and parameter inventories
datum metadata and adjustment rules
event-specific observed time-series derivatives
universal model observation points
cross-section / flow-comparison lines
```

### USGS master archive

The reusable archive contains annual and continuous records for the project's selected surface-water gauges across the working event period. It preserves both original source material and normalized derivatives.

The two primary USGS parameter codes are:

| Parameter | Meaning in this project |
|---|---|
| `00065` | Gauge height / water level |
| `00060` | Discharge |

The archive includes raw downloads, source metadata, normalized records, merged pre-datum records, site inventories, audit products, and datum-adjusted derivatives. Raw records and metadata are retained so later corrections do not erase the original evidence.

The broad audit encountered 479 distinct eight-digit identifiers across all archive paths and metadata products. That number is not the active validation-gauge count; it includes identifiers appearing in wider source inventories, metadata, and audit records. The current selected validation archive is based on **89 surface-water sites** that intersect the project selection criteria and have evidence of parameter `00065`, parameter `00060`, or both.

### Universal model validation geometry

The current promoted model geometry contains:

```text
59 point-observation locations
29 cross-section / line locations
```

Point locations are selected for water-level comparison within the usable model domain. Discharge-only locations are not automatically treated as point water-level observations. Cross-section lines support flow-oriented comparisons where suitable discharge observations exist.

Each completed event catalog contains three validation product groups:

```text
event_validation_points/
event_validation_lines/
event_validation_gauges/
```

The geometry is broadly shared across events, while `event_validation_gauges` contains the event-specific observed time-series slice. Actual observed coverage varies by gauge and event. A location may exist in the universal model geometry even when no suitable observed record is available for a particular event.

The promotion workflow used a high-coverage rule for event derivatives rather than assuming every archive gauge was suitable for every event. Catalog readiness, model completion, and scientific skill remain separate questions.

---

## Vertical datum harmonization

Gauge-height records cannot be compared safely by treating every number as though it shares one vertical reference.

Several complications occur in the project data:

- A USGS station may use a local gage datum rather than NAVD88.
- Station metadata may record a change to NAVD88 on a particular date.
- The value required to reconcile pre-change records is site-specific.
- Offsets may be positive or negative.
- Some offsets are large because they reconcile local reference elevations, not because the water surface physically jumped by that amount.
- Metadata can be incomplete, ambiguous, or internally inconsistent.
- Automated step detection is useful evidence but is not sufficient by itself.
- Coastal NOAA stations follow separate datum conventions from the inland USGS table.
- Event-specific gaps may require an accepted interpolation, regression, or other documented fill method.

For sites with an authorized transition rule, the project construction applies:

```text
adjusted pre-transition value
    =
original pre-transition value
    +
site-specific offset_to_add_before_change_m
```

Values on and after the recorded transition date are not given that pre-transition correction.

A blank date or offset in the table below means **no explicit transition rule is currently recorded in this project table**. It does not prove that the station has no datum uncertainty, no metadata history, or no need for future review.

The datum-adjusted master derivative is used to construct event-specific validation gauge files. Original raw data, source metadata, comparison outputs, and adjustment evidence remain preserved separately.

<details>
<summary><strong>Selected 89-site validation inventory and recorded NAVD88 transition rules</strong></summary>

| USGS site | Recorded NAVD88 transition | Offset added before transition (m) |
|---|---:|---:|
| `08067520` | — | — |
| `08067525` | 10/1/2016 | -0.688848 |
| `08068275` | — | — |
| `08068300` | — | — |
| `08068305` | — | — |
| `08068310` | — | — |
| `08068325` | 10/1/2008 | 30.233112 |
| `08068390` | 10/1/2010 | 38.002464 |
| `08068400` | 10/1/2010 | 37.926264 |
| `08068450` | 10/1/2011 | -0.185928 |
| `08068500` | — | — |
| `08068520` | — | — |
| `08068700` | 10/1/2010 | 29.407104 |
| `08068720` | 10/1/2012 | 30.223968 |
| `08068740` | 10/1/2012 | 30.00756 |
| `08068780` | — | — |
| `08068800` | 10/1/2011 | 23.71344 |
| `08068900` | 10/1/2011 | 20.81784 |
| `08069000` | 10/1/2011 | 18.522696 |
| `08072050` | — | — |
| `08072150` | — | — |
| `08072300` | 10/1/2008 | 22.597872 |
| `08072350` | — | — |
| `08072400` | — | — |
| `08072470` | — | — |
| `08072520` | — | — |
| `08072600` | — | — |
| `08072680` | — | — |
| `08072700` | — | — |
| `08072730` | 10/1/2008 | 29.891736 |
| `08072760` | 10/1/2008 | 25.813512 |
| `08072800` | 10/1/2008 | -1.179576 |
| `08073100` | — | — |
| `08073500` | 10/1/2008 | 0.957072 |
| `08073600` | 10/1/2008 | 0.926592 |
| `08073630` | — | — |
| `08073700` | 10/1/2008 | 1.136904 |
| `08073750` | — | — |
| `08073800` | — | — |
| `08074000` | 10/1/2008 | 0.755904 |
| `08074020` | 10/1/2016 | 8.180832 |
| `08074100` | — | — |
| `08074150` | 10/1/2016 | -1.636776 |
| `08074200` | — | — |
| `08074250` | 10/1/2016 | -1.727302 |
| `08074500` | 10/1/2008 | -2.715768 |
| `08074540` | 10/1/2016 | -0.338328 |
| `08074598` | 10/1/2008 | -0.774192 |
| `08074600` | — | — |
| `08074610` | — | — |
| `08074710` | 10/1/2016 | -0.09144 |
| `08074760` | — | — |
| `08074780` | — | — |
| `08074800` | — | — |
| `08074810` | — | — |
| `08074850` | — | — |
| `08074900` | — | — |
| `08074910` | — | — |
| `08075000` | — | — |
| `08075110` | — | — |
| `08075300` | — | — |
| `08075400` | 10/1/2012 | -0.908304 |
| `08075500` | 10/1/2016 | -1.379525 |
| `08075550` | — | — |
| `08075600` | — | — |
| `08075605` | — | — |
| `08075650` | — | — |
| `08075700` | — | — |
| `08075730` | 10/1/2016 | -1.03632 |
| `08075750` | — | — |
| `08075760` | — | — |
| `08075763` | — | — |
| `08075770` | 10/1/2009 | -1.335024 |
| `08075780` | 10/1/2010 | 1.4478 |
| `08075900` | — | — |
| `08076000` | — | — |
| `08076180` | 10/1/2008 | -0.414528 |
| `08076200` | — | — |
| `08076500` | 10/1/2009 | -1.807464 |
| `08076700` | 10/1/2016 | -1.078992 |
| `08076900` | — | — |
| `08076990` | — | — |
| `08076997` | — | — |
| `08077000` | — | — |
| `08077100` | — | — |
| `08077540` | — | — |
| `08077550` | — | — |
| `08077600` | — | — |
| `08077630` | — | — |

</details>

Of the 89 selected sites, 34 currently have a recorded transition date and pre-transition offset in this table. The remaining 55 do not have an explicit rule recorded here.

---

## Catalog discovery and authority

The data system distinguishes discovery from final run authority.

```text
1. The user selects static and event catalogs in the Web Launcher.
2. The launcher detects active files and reads valid manifests.
3. The page assembles an explicit JSON run configuration.
4. The Python backend validates and freezes that configuration.
5. The run receives its own copied or generated model files.
```

The practical authority order is:

| Level | Authority |
|---:|---|
| 1 | Run-local files and the frozen `run_config.json` for an existing run |
| 2 | Explicit active paths selected for a new run |
| 3 | Active top-level products in the selected static and event catalogs |
| 4 | Valid portable manifest recommendations and catalog-detector suggestions |
| 5 | Administrative, backup, audit, quarantine, and `_misc` material, which is excluded from normal active selection |

A warning from catalog detection does not make a missing or stale path authoritative. Where a manifest points to a colocated file, relative paths are preferred so the catalog can move without embedding one user's full data root.

---

## Path handling and portability

The current deployment intentionally separates data from code and run output:

```text
Longleaf /users space
    active data, catalogs, source archives, and processed derivatives

Longleaf shared project space
    pipeline code, Python environments, containers, and run outputs
```

Machine-specific roots are supplied through Web Launcher Settings rather than duplicated across every page. Once a run is created, the backend freezes explicit paths and configuration values into that run for provenance.

The data audit found many absolute path strings because manifests, source tables, audit outputs, and historical provenance intentionally record where files came from. An absolute path is not automatically an error. Runtime repair should focus on load-bearing active paths, not mass-rewrite every historical reference.

---

## Creating a new data catalog

This page defines what a catalog contains and how it participates in the architecture. The operational workflow for creating one will be documented in the **SFINCS Web Launcher Guide**.

At a high level, a new event catalog requires:

```text
1. Define and approve the event runtime.
2. Gather and quality-check precipitation.
3. Add water-level and, where used, discharge forcing.
4. Add wind and pressure only when the event requires them.
5. Define boundary and source-point identities and coordinates.
6. Slice validation observations from the master archive.
7. Add the shared validation geometry.
8. Record metadata, manifests, and forcing-quality evidence.
9. Keep active products at the expected top level.
10. Move superseded or diagnostic material into _misc.
11. Run catalog detection and preflight checks before submission.
```

Future domains do not have to copy Harris County filenames exactly. They must provide the equivalent physical and configuration contract expected by the selected pipeline workflow.

---

## Updating a catalog

A safe catalog update should preserve three layers:

```text
active product
    the version selected for future runs

provenance
    source data, metadata, manifests, and construction evidence

previous active version
    retained under _misc or another clearly administrative location
```

Updates should be staged and audited before promotion. Existing run directories should not be rewritten merely because a catalog changes. A new or rebuilt run is required to incorporate the updated input.

A completed scheduler job is also not proof that an updated catalog is scientifically correct. Generated SFINCS forcing, model geometry, output dimensions, and validation products still require their own checks.

---

## External data and attribution

The project currently uses or preserves direct evidence for the following external source families:

| Source | Current project role |
|---|---|
| USGS | Inland gauge height, discharge, station metadata, and historical records |
| NOAA | Coastal water-level observations and station metadata |
| MRMS | Radar-based precipitation for the active Harvey catalog |
| AORC | Precipitation and applicable atmospheric forcing for event preparation |
| HCFCD | Harris County spatial, hydrologic, and inherited source material |
| NLCD | Land-cover information used in roughness preparation |
| DesignSafe | Curated elevation data used by the Harris County setup |

This list is intentionally limited to sources evidenced by the current data tree. Individual products retain their original attribution, access conditions, and licenses.

---

## Relationship to the rest of the repository

- [Architecture overview](architecture/overview.md) places data catalogs in the complete modeling system.
- [Web Launcher](architecture/web_launcher/web_launcher.md) explains how browser pages discover and select catalogs.
- [Python Backend](architecture/python_backend/python_backend.md) explains how selected paths become a validated and frozen run configuration.
- [Slurm Execution](architecture/slurm_execution.md) explains how the generated model is executed.
- [Review Mode](architecture/review_mode/review_mode.md) explains how run outputs and validation products are inspected.

The Web Launcher Guide will contain the detailed catalog-construction workflow. This page remains the architectural reference for what the data system contains, which products are authoritative, and how those products move into a run.
