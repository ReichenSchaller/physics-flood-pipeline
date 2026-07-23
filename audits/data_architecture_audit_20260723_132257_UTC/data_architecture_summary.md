# Data Architecture Audit Summary

**Created:** `2026-07-23T13:25:51.152294+00:00`
**Data root:** `/users/e/p/epsilon/Data/Data/harris_county`
**Output folder:** `/proj/zefflab/projects/Flooding/Github/physics-flood-pipeline/audits/data_architecture_audit_20260723_132257_UTC`

## Event plan

- Working events: **35**
- Complete current catalogs: **14**
- Next-step catalogs: **21**
- Complete catalog folders currently present: **14**

## Measured catalog sizes

- `harris_county` source-oriented static data: **21.277 GiB**
- `harris_county_ppp_latest` trusted native package: **3.350 GiB**
- Mean apparent size of present complete event catalogs: **0.563 GiB**

Public documentation will use the rounded project descriptions:

```text
PPP static package: about 2 GB
source-oriented static data: about 24 GB
typical complete event catalog: about 1-2 GB
```

## Validation holdings

- Validation-related active files found in complete catalogs: **42**
- Distinct USGS gauge identifiers evidenced in the archive: **479**

The supplied site-specific NAVD88 transition table must be merged
with `gauge_archive_inventory.csv` during documentation drafting.

## External-source evidence

- Sources with direct path or metadata evidence: **USGS, NOAA, MRMS, AORC, HCFCD, NLCD, DesignSafe**

The source evidence is intentionally cautious. A source should not be
named publicly merely because it is plausible.

## Path portability

- Absolute path references found: **37984**
- References classified for inspection: **4434**

Historical and provenance references are not automatically runtime bugs.
Review the classification before editing any catalog.

## Files to return

Upload this entire audit folder or at minimum:

```text
data_architecture_summary.md
data_tree_compact.txt
event_master_plan.csv
event_catalog_inventory.csv
static_package_inventory.csv
validation_file_inventory.csv
gauge_archive_inventory.csv
gauge_metadata_sources.csv
external_source_evidence.csv
path_portability_findings.csv
file_format_summary.csv
public_data_page_decisions.md
```
