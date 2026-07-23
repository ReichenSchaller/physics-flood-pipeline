# Public `docs/data.md` decisions

## Availability

The complete project datasets are stored in the maintainer's Longleaf
user-space data area. They are not committed to GitHub because the full
collection is substantially larger than the source-code repository.

Data and associated catalog products are available upon reasonable request
from:

- Reichen Schaller
- epsilon@unc.edu

## Public size summary

- Current trusted native PPP static package: approximately 2 GB.
- Source-oriented static data collection: approximately 24 GB.
- Typical completed event catalog: approximately 1-2 GB.

The audit's measured apparent sizes should be retained as internal evidence.
The public page may use the rounded figures above.

## Event status language

There are 35 events in the working event plan.

- 14 have complete current data catalogs for the present research scope.
- 21 are next-step event catalogs.

"Complete current data catalog" does not mean that all resulting simulations
have completed scientific validation or that the catalog can never be revised.

## Documentation boundary

`docs/data.md` explains data architecture, catalog structure, authority,
availability, validation holdings, and source lineage.

Step-by-step instructions for constructing a new data catalog will be placed
in the SFINCS Web Launcher Guide.

## Scope boundary

The named folders and Harris County products represent the project's current
research implementation. The Web Launcher and backend pipeline can support
other domains, events, forcing combinations, grids, and catalog organizations.

## External-source policy

Only name an external source publicly when direct evidence exists in active
filenames, manifests, metadata, or catalog records. The cautious candidate
list is USGS, NOAA, MRMS, AORC, HCFCD, NLCD, and DesignSafe.

## Validation coverage

The final page should explain:

- the master USGS gauge archive;
- parameters 00065 and 00060 where available;
- the full gauge inventory;
- event-specific validation derivatives;
- 59 promoted point locations;
- 29 promoted line locations;
- site-specific NAVD88 transition dates and offsets;
- separate coastal-boundary datum handling;
- preservation of accepted gap-fill and datum-adjustment decisions.
