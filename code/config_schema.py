"""
Author: Reichen Schaller
Configuration schema/defaults for the SFINCS pipeline runner.

This file intentionally contains no Slurm submission or model-running logic.
It defines the settings vocabulary that the runner and future launcher app can
share.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


VALID_RUNNER_MODES = {"preflight", "build_scripts", "submit"}

PIPELINE_MODE_BY_RUNNER_MODE = {
    "preflight": "preflight_only",
    "build_scripts": "build_scripts_only",
    "submit": "submit_slurm_chain",
}

VALID_PIPELINE_MODES = set(PIPELINE_MODE_BY_RUNNER_MODE.values())

VALID_PREPROCESS_MODES = {
    "hydromt_build",
    "native_sfincs_assembly",
    "hybrid",
}

VALID_DEPENDENCY_TYPES = {"afterok"}

SFINCS_CONTAINER_FILENAME = "sfincs-v2.3.0-mt-Faber-Release.sif"

FALLBACK_CONDA_PYTHON = "/users/e/p/epsilon/sfincs_project/envs/sfincs/bin/python"
FALLBACK_CONDA_ENV_PATH = "/users/e/p/epsilon/sfincs_project/envs/sfincs"

DEFAULT_DATA_ROOT = "/proj/zefflab/projects/Flooding/Data/harris_county"
DEFAULT_OUTPUT_ROOT = "/proj/zefflab/projects/Flooding/sfincs_runs"
DEFAULT_STATIC_PPP_DIR = (
    "/proj/zefflab/projects/Flooding/Data/harris_county/catalogs/static/harris_county_ppp"
)

# Hybrid catalogs are now path-driven.
#
# Older reduced-event runs used fixed filenames like:
#   event_precip/aorc_precip_event.nc
#   event_waterlevel/selected_bzs_waterlevel_reduced.csv
#   event_runtime_window/event_runtime_window.csv
#
# Current event catalogs may use event-specific FINAL_FOR_NOW products, selected
# through explicit config paths such as rainfall_path, waterlevel_path, wind_path,
# and pressure_path. Do not enforce old fixed filenames here.
HYBRID_ALWAYS_REQUIRED_EVENT_FILES = []

HYBRID_FORCING_EVENT_FILES = {
    "use_rainfall": [],
    "use_waterlevel_boundary": [],
    "use_discharge_boundary": [],
    "use_wind": [],
    "use_pressure": [],
}

# Minimal static package checks only.
#
# Do not require sfincs.bnd/src/obs here:
#   - hybrid writes BND/BZS from event water-level catalog products;
#   - discharge may be disabled;
#   - obs/CRS can come from event validation products;
#   - subgrid may be sfincs.sbg or sfincs_subgrid.nc and is validated by the
#     override resolver when sbgfile is enabled.
HYBRID_STATIC_REQUIRED_FILES = [
    "sfincs.dep",
    "sfincs.msk",
    "sfincs.ind",
    "sfincs.manning",
]


def default_config(pipeline_root: Path) -> dict[str, Any]:
    """Return minimal runner defaults.

    User JSON values override these defaults in runner_core.apply_defaults().
    Runtime paths are resolved again in runner_core.resolve_runtime_paths().
    """
    code_dir = pipeline_root / "code"
    bundle_python = pipeline_root / "envs" / "sfincs" / "bin" / "python"
    conda_python = str(bundle_python) if bundle_python.exists() else FALLBACK_CONDA_PYTHON

    return {
        # Runner behavior
        "prefer_pipeline_bundle_runtime_paths": True,

        # Run identity / paths
        "run_name": "UNSET_RUN_NAME",
        "project_root": str(pipeline_root),
        "data_root": DEFAULT_DATA_ROOT,
        "output_root": DEFAULT_OUTPUT_ROOT,
        "overwrite_existing_run": False,
        "allow_writes_inside_proj": True,
        "allow_missing_model_inputs": False,

        # Pipeline control
        "pipeline_mode": "preflight_only",
        "preprocess_mode": "hybrid",
        "run_preprocessing_job": True,
        "run_sfincs_job": True,
        "run_postprocessing_job": True,
        "submit_with_dependencies": True,
        "dependency_type": "afterok",

        # Runtime machinery
        "preprocess_stage_script": str(code_dir / "preprocess_stage.py"),
        "postprocess_stage_script": str(code_dir / "postprocess_stage.py"),
        "conda_env_path": str(Path(conda_python).parent.parent),
        "conda_python": conda_python,
        "sfincs_container_path": str(pipeline_root / "containers" / SFINCS_CONTAINER_FILENAME),
        "apptainer_module": "apptainer",
        "anaconda_module": "anaconda",
        "bash_strict_mode": True,

        # Slurm general
        "slurm_account": None,
        "slurm_partition": None,
        "slurm_qos": None,
        "slurm_email": None,
        "slurm_mail_type": "END,FAIL",
        "slurm_extra_directives": [],

        # Resources
        "preprocess_time": "01:00:00",
        "preprocess_nodes": 1,
        "preprocess_ntasks": 1,
        "preprocess_cpus_per_task": 4,
        "preprocess_mem": "16G",

        "sfincs_time": "04:00:00",
        "sfincs_nodes": 1,
        "sfincs_ntasks": 1,
        "sfincs_cpus_per_task": 8,
        "sfincs_mem": "32G",
        "sfincs_use_openmp_threads": True,
        "sfincs_omp_proc_bind": "true",
        "sfincs_omp_places": "cores",

        "postprocess_time": "01:00:00",
        "postprocess_nodes": 1,
        "postprocess_ntasks": 1,
        "postprocess_cpus_per_task": 2,
        "postprocess_mem": "24G",

        # Harris/native/hybrid defaults
        # Keep native SFINCS input dirs empty by default.
        # runner_core.apply_defaults() may fill DEFAULT_STATIC_PPP_DIR only for hybrid mode.
        # Manual hydromt_build configs must not inherit native/reference SFINCS artifacts.
        "data_catalogs": [],
        "native_static_sfincs_input_dirs": [],
        "native_event_sfincs_input_dirs": [],
        "native_sfincs_input_dirs": [],

        # Forcing defaults
        "use_rainfall": True,
        "use_waterlevel_boundary": True,
        "use_discharge_boundary": True,
        "use_wind": False,
        "use_pressure": False,
        "require_at_least_one_forcing": True,
        

        # Safety/debug
        "print_config_summary": True,
        "validate_paths_before_submit": True,
        "stop_if_required_path_missing": True,
        "save_config_json": True,
        "save_job_ids": True,
        "print_optional_path_warnings": True,
        "warn_unknown_config_keys": True,
        "strict_schema_validation": False,
        "warn_schema_type_mismatches": True,
        
        # Active mask / Override grid-template defaults
        "active_mask_path": "",
        "active_mask_mode": "sample_to_grid",
        "grid_source": "region",
        "grid_template_path": "",
        "grid_template_mode": "raster_template",
        "grid_template_use_as_active_mask": False,
        "override_locked_config_keys": [],
        "override_locked_sections": [],
        "override_lock_reasons": {},
        "stamp_waterlevel_boundary_on_mask": True,
        "waterlevel_boundary_stamp_search_radius_cells": 3,

        # Manual open-boundary mask classification.
        # point_stamp preserves the current behavior: stamp final sfincs.bnd points.
        # coastal_outline reads a reviewed open-boundary line/polygon and marks
        # matching final sparse-mask cells as msk=2.
        "open_boundary_mask_mode": "point_stamp",
        "open_boundary_outline_path": "",
        "open_boundary_outline_buffer_m": 150.0,
        "open_boundary_min_cells": 50,
        "open_boundary_max_cells": 500,
        "open_boundary_require_edge_adjacency": True,
        "open_boundary_allow_overwrite_special": False,
        
        "store_cumulative_precip": True,
        "store_hmax_subgrid": True,
    }


# ==============================================================================
# GENERATED SCHEMA METADATA
# ==============================================================================
# Generated from:
#   /proj/zefflab/projects/Flooding/sfincs_runs/harris_harvey_2017_runner_submit_001/run_config.json
# Created:
#   2026-05-27T11:33:24
#
# These keys are known to appear in successful config-driven pipeline runs.
# They are separated from default_config() so older/specialized configs can carry
# stage-specific keys without being falsely reported as unknown.

OPTIONAL_CONFIG_KEYS = {
    "active_mask_path",
    "active_mask_mode",
    "open_boundary_mask_mode",
    "open_boundary_outline_path",
    "open_boundary_outline_buffer_m",
    "open_boundary_min_cells",
    "open_boundary_max_cells",
    "open_boundary_require_edge_adjacency",
    "open_boundary_allow_overwrite_special",
    "grid_source",
    "grid_template_path",
    "grid_template_mode",
    "grid_template_use_as_active_mask",
    "override_locked_config_keys",
    "override_locked_sections",
    "override_lock_reasons",
    "override_detection_manifest",
    "override_source_path",
    "override_source_paths",
    "override_geometry_authority_status",
    "override_geometry_authority_id",
    "override_geometry_authority_label",
    "override_geometry_authority_geometry",
    "override_geometry_advanced_config_repaired",
    "override_geometry_advanced_config_repair_detail",
    "override_geometry_warning",
    "strict_native_geometry_validation",
    "event_name",
    "run_series",
    "sfincs_container",
    "hydromt_catalog_paths",
    "_source_config_path",
    "active_zmin",
    "advanced_config",
    "bathy_paths",
    "created_at",
    "created_by_user",
    "culvert_native_file_path",
    "culvert_path",
    "culvert_source_kind",
    "curve_number_path",
    "f0_path",
    "fc_path",
    "kd_path",
    "ks_path",
    "qinf_path",
    "psi_path",
    "seff_path",
    "sigma_path",
    "smax_path",
    "vol_path",
    "dem_paths",
    "dem_zmin",
    "discharge_clip_to_model_time",
    "discharge_points_csv_path",
    "discharge_points_name_column",
    "discharge_points_x_column",
    "discharge_points_y_column",
    "discharge_source",
    "discharge_source_kind",
    "discharge_time_column",
    "discharge_time_format",
    "discharge_timeseries_csv_path",
    "discharge_units",
    "discharge_value_columns",
    "drainage_structure_native_file_path",
    "drainage_structure_path",
    "drainage_structure_source_kind",
    "dthisout_s",
    "dtmaxout_s",
    "dtout_s",
    "dtrstout_s",
    "elevation_buffer_cells",
    "grid_crs",
    "grid_dx_m",
    "grid_dy_m",
    "grid_resolution_m",
    "grid_rotated",
    "grid_rotation_deg",
    "hsg_path",
    "hydrography_path",
    "hydrography_source",
    "hydromt_bathy_sources",
    "hydromt_dem_sources",
    "hydromt_roughness_sources",
    "infiltration_mode",
    "infiltration_path",
    "landcover_path",
    "landcover_reclass_table",
    "landcover_source",
    "launcher_file",
    "launcher_python",
    "launcher_python_version",
    "manning_land",
    "manning_sea",
    "manning_uniform",
    "mask_drop_area_km2",
    "mask_fill_area_km2",
    "meteo_update_interval_s",
    "obs_lines_path",
    "obs_points_path",
    "outflow_boundary_polygon_path",
    "output_format",
    "postprocess_basemap_source",
    "postprocess_basemap_zoomlevel",
    "postprocess_bedlevel_var_candidates",
    "postprocess_create_summary_json",
    "postprocess_create_summary_txt",
    "postprocess_depth_var_candidates",
    "postprocess_list_output_variables",
    "postprocess_make_quicklook_plots",
    "postprocess_matplotlib_backend",
    "postprocess_max_depth_var_candidates",
    "postprocess_max_plot_cells",
    "postprocess_max_waterlevel_var_candidates",
    "postprocess_plot_final_water_level",
    "postprocess_plot_max_flood_depth",
    "postprocess_plot_max_water_level",
    "postprocess_plot_obs_hydrographs",
    "postprocess_result_map_alpha",
    "postprocess_result_map_background_fade_alpha",
    "postprocess_result_map_show_boundaries",
    "postprocess_result_map_show_dep_layer",
    "postprocess_result_map_show_layout_legend",
    "postprocess_result_map_show_model_features",
    "postprocess_result_map_show_obs",
    "postprocess_use_basemap",
    "postprocess_use_basemap_on_result_maps",
    "postprocess_use_rotated_map_plots",
    "postprocess_waterlevel_var_candidates",
    "preprocess_enable_hydromt_file_logging",
    "pressure_path",
    "pressure_source",
    "qinf_mm_hr",
    "qinf_zmin_m",
    "rainfall_clip_to_model_time",
    "rainfall_kind",
    "rainfall_path",
    "rainfall_source",
    "rainfall_uniform_mm_hr",
    "rainfall_variable",
    "region_bbox",
    "region_mode",
    "region_path",
    "reset_outflow_boundary",
    "reset_waterlevel_boundary",
    "roughness_land_level_m",
    "run_description",
    "run_tags",
    "runner_file",
    "runner_python",
    "runner_python_version",
    "save_data_inventory",
    "scs_initial_abstraction_factor",
    "sfincs_file_override_fail_on_multiple_matches",
    "sfincs_file_override_targets",
    "sfincs_file_overrides",
    "soil_storage_path",
    "source_config_path",
    "store_cumulative_precip",
    "store_hmax_subgrid",
    "store_max_flux",
    "store_max_velocity",
    "store_velocity",
    "store_wet_duration",
    "streamflow_data_path",
    "streamflow_site_info_path",
    "strict_schema_validation",
    "subgrid_nr_pixels",
    "subgrid_river_path",
    "subgrid_river_source",
    "subgrid_use_rivers",
    "subgrid_write_dep_tif",
    "subgrid_write_man_tif",
    "thin_dam_native_file_path",
    "thin_dam_path",
    "thin_dam_source_kind",
    "tref",
    "tstart",
    "tstop",
    "use_infiltration",
    "use_landcover_roughness_if_available",
    "use_obs_lines",
    "use_obs_points",
    "use_sfincs_file_overrides",
    "use_spatially_variable_roughness",
    "use_structures",
    "use_subgrid",
    "warn_schema_type_mismatches",
    "warn_unknown_config_keys",
    "waterlevel_boundary_zmax",
    "waterlevel_clip_to_model_time",
    "waterlevel_path",
    "waterlevel_source",
    "waterlevel_source_kind",
    "waterlevel_variable",
    "weir_native_file_path",
    "weir_path",
    "weir_source_kind",
    "wind_path",
    "wind_source",
}

SCHEMA_BOOL_KEYS = {
    "allow_missing_model_inputs",
    "allow_writes_inside_proj",
    "bash_strict_mode",
    "discharge_clip_to_model_time",
    "grid_rotated",
    "grid_template_use_as_active_mask",
    "overwrite_existing_run",
    "override_geometry_advanced_config_repaired",
    "strict_native_geometry_validation",
    "postprocess_create_summary_json",
    "postprocess_create_summary_txt",
    "postprocess_list_output_variables",
    "postprocess_make_quicklook_plots",
    "postprocess_plot_final_water_level",
    "postprocess_plot_max_flood_depth",
    "postprocess_plot_max_water_level",
    "postprocess_plot_obs_hydrographs",
    "postprocess_result_map_show_boundaries",
    "postprocess_result_map_show_dep_layer",
    "postprocess_result_map_show_layout_legend",
    "postprocess_result_map_show_model_features",
    "postprocess_result_map_show_obs",
    "postprocess_use_basemap",
    "postprocess_use_basemap_on_result_maps",
    "postprocess_use_rotated_map_plots",
    "prefer_pipeline_bundle_runtime_paths",
    "preprocess_enable_hydromt_file_logging",
    "print_config_summary",
    "print_optional_path_warnings",
    "rainfall_clip_to_model_time",
    "require_at_least_one_forcing",
    "reset_outflow_boundary",
    "reset_waterlevel_boundary",
    "stamp_waterlevel_boundary_on_mask",
    "open_boundary_require_edge_adjacency",
    "open_boundary_allow_overwrite_special",
    "run_postprocessing_job",
    "run_preprocessing_job",
    "run_sfincs_job",
    "save_config_json",
    "save_data_inventory",
    "save_job_ids",
    "sfincs_file_override_fail_on_multiple_matches",
    "sfincs_use_openmp_threads",
    "stop_if_required_path_missing",
    "store_cumulative_precip",
    "store_hmax_subgrid",
    "store_max_flux",
    "store_max_velocity",
    "store_velocity",
    "store_wet_duration",
    "subgrid_use_rivers",
    "subgrid_write_dep_tif",
    "subgrid_write_man_tif",
    "submit_with_dependencies",
    "use_discharge_boundary",
    "use_infiltration",
    "use_landcover_roughness_if_available",
    "use_obs_lines",
    "use_obs_points",
    "use_pressure",
    "use_rainfall",
    "use_sfincs_file_overrides",
    "use_spatially_variable_roughness",
    "use_structures",
    "use_subgrid",
    "use_waterlevel_boundary",
    "use_wind",
    "validate_paths_before_submit",
    "waterlevel_clip_to_model_time",
}

SCHEMA_INT_KEYS = {
    "dthisout_s",
    "dtout_s",
    "dtrstout_s",
    "elevation_buffer_cells",
    "grid_dx_m",
    "grid_dy_m",
    "grid_resolution_m",
    "waterlevel_boundary_stamp_search_radius_cells",
    "open_boundary_min_cells",
    "open_boundary_max_cells",
    "meteo_update_interval_s",
    "postprocess_cpus_per_task",
    "postprocess_max_plot_cells",
    "postprocess_nodes",
    "postprocess_ntasks",
    "preprocess_cpus_per_task",
    "preprocess_nodes",
    "preprocess_ntasks",
    "sfincs_cpus_per_task",
    "sfincs_nodes",
    "sfincs_ntasks",
    "subgrid_nr_pixels",
}

SCHEMA_FLOAT_KEYS = {
    "active_zmin",
    "dem_zmin",
    "dtmaxout_s",
    "manning_land",
    "manning_sea",
    "manning_uniform",
    "mask_drop_area_km2",
    "mask_fill_area_km2",
    "postprocess_result_map_alpha",
    "postprocess_result_map_background_fade_alpha",
    "qinf_mm_hr",
    "qinf_zmin_m",
    "roughness_land_level_m",
    "scs_initial_abstraction_factor",
    "waterlevel_boundary_zmax",
    "open_boundary_outline_buffer_m",
}

SCHEMA_STR_KEYS = {
    "override_geometry_authority_status",
    "override_geometry_authority_id",
    "override_geometry_authority_label",
    "override_geometry_advanced_config_repair_detail",
    "override_geometry_warning",
    "override_source_path",
    "active_mask_mode",
    "open_boundary_mask_mode",
    "open_boundary_outline_path",
    "event_name",
    "run_series",
    "sfincs_container",
    "_source_config_path",
    "anaconda_module",
    "apptainer_module",
    "conda_env_path",
    "conda_python",
    "created_at",
    "created_by_user",
    "culvert_source_kind",
    "postprocess_basemap_zoomlevel",
    "data_root",
    "dependency_type",
    "discharge_points_name_column",
    "discharge_points_x_column",
    "discharge_points_y_column",
    "discharge_source",
    "discharge_source_kind",
    "discharge_time_column",
    "discharge_time_format",
    "discharge_units",
    "drainage_structure_source_kind",
    "grid_crs",
    "grid_source",
    "grid_template_mode",
    "hydrography_source",
    "infiltration_mode",
    "landcover_reclass_table",
    "landcover_source",
    "launcher_file",
    "launcher_python",
    "launcher_python_version",
    "obs_lines_path",
    "obs_points_path",
    "output_format",
    "output_root",
    "pipeline_mode",
    "postprocess_basemap_source",
    "postprocess_matplotlib_backend",
    "postprocess_mem",
    "postprocess_stage_script",
    "postprocess_time",
    "preprocess_mem",
    "preprocess_mode",
    "preprocess_stage_script",
    "preprocess_time",
    "pressure_source",
    "project_root",
    "rainfall_kind",
    "rainfall_source",
    "rainfall_variable",
    "region_mode",
    "region_path",
    "run_description",
    "run_name",
    "runner_file",
    "runner_python",
    "runner_python_version",
    "sfincs_container_path",
    "sfincs_mem",
    "sfincs_omp_places",
    "sfincs_omp_proc_bind",
    "sfincs_time",
    "slurm_mail_type",
    "source_config_path",
    "subgrid_river_source",
    "thin_dam_source_kind",
    "tref",
    "tstart",
    "tstop",
    "waterlevel_source",
    "waterlevel_source_kind",
    "waterlevel_variable",
    "weir_source_kind",
    "wind_source",
}

SCHEMA_LIST_KEYS = {
    "override_source_paths",
    "bathy_paths",
    "data_catalogs",
    "hydromt_catalog_paths",
    "dem_paths",
    "discharge_value_columns",
    "hydromt_bathy_sources",
    "hydromt_dem_sources",
    "hydromt_roughness_sources",
    "native_event_sfincs_input_dirs",
    "native_sfincs_input_dirs",
    "native_static_sfincs_input_dirs",
    "override_locked_config_keys",
    "override_locked_sections",
    "postprocess_bedlevel_var_candidates",
    "postprocess_depth_var_candidates",
    "postprocess_max_depth_var_candidates",
    "postprocess_max_waterlevel_var_candidates",
    "postprocess_waterlevel_var_candidates",
    "run_tags",
    "slurm_extra_directives",
}

SCHEMA_DICT_KEYS = {
    "override_geometry_authority_geometry",
    "advanced_config",
    "sfincs_file_override_targets",
    "sfincs_file_overrides",
    "override_lock_reasons",
    "override_detection_manifest",
}

SCHEMA_PATH_LIKE_KEYS = {
    "override_source_path",
    "override_source_paths",
    "active_mask_path",
    "open_boundary_outline_path",
    "grid_template_path",
    "hydromt_catalog_paths",
    "sfincs_container",
    "_source_config_path",
    "bathy_paths",
    "conda_env_path",
    "conda_python",
    "culvert_native_file_path",
    "culvert_path",
    "curve_number_path",
    "f0_path",
    "fc_path",
    "kd_path",
    "ks_path",
    "qinf_path",
    "psi_path",
    "seff_path",
    "sigma_path",
    "smax_path",
    "vol_path",
    "data_root",
    "dem_paths",
    "discharge_points_csv_path",
    "discharge_timeseries_csv_path",
    "drainage_structure_native_file_path",
    "drainage_structure_path",
    "hsg_path",
    "hydrography_path",
    "infiltration_path",
    "landcover_path",
    "launcher_file",
    "launcher_python",
    "native_event_sfincs_input_dirs",
    "native_sfincs_input_dirs",
    "native_static_sfincs_input_dirs",
    "obs_lines_path",
    "obs_points_path",
    "outflow_boundary_polygon_path",
    "output_root",
    "postprocess_stage_script",
    "prefer_pipeline_bundle_runtime_paths",
    "preprocess_stage_script",
    "pressure_path",
    "project_root",
    "rainfall_path",
    "region_path",
    "runner_file",
    "runner_python",
    "sfincs_container_path",
    "soil_storage_path",
    "source_config_path",
    "streamflow_data_path",
    "streamflow_site_info_path",
    "subgrid_river_path",
    "thin_dam_native_file_path",
    "thin_dam_path",
    "waterlevel_path",
    "weir_native_file_path",
    "weir_path",
    "wind_path",
}


def known_config_keys(pipeline_root: Path | None = None) -> set[str]:
    """Return all config keys known to the runner schema."""
    root = pipeline_root or Path("/proj/zefflab/projects/Flooding/pipeline")
    return set(default_config(root)) | set(OPTIONAL_CONFIG_KEYS)


def unknown_config_keys(cfg: dict[str, Any], pipeline_root: Path | None = None) -> list[str]:
    """Return config keys not currently known to the runner schema."""
    return sorted(set(cfg) - known_config_keys(pipeline_root))


def schema_type_warnings(cfg: dict[str, Any]) -> list[str]:
    """Return non-fatal type warnings for obviously malformed config values."""
    warnings: list[str] = []

    def warn(key: str, expected: str, actual: Any) -> None:
        warnings.append(
            f"SCHEMA TYPE WARNING: {key} expected {expected}, got {type(actual).__name__}: {actual!r}"
        )

    for key in SCHEMA_BOOL_KEYS:
        if key in cfg and cfg[key] is not None and not isinstance(cfg[key], bool):
            warn(key, "bool", cfg[key])

    for key in SCHEMA_INT_KEYS:
        if key in cfg and cfg[key] is not None and not (isinstance(cfg[key], int) and not isinstance(cfg[key], bool)):
            warn(key, "int", cfg[key])

    for key in SCHEMA_FLOAT_KEYS:
        if key in cfg and cfg[key] is not None and not isinstance(cfg[key], (int, float)):
            warn(key, "float-compatible number", cfg[key])

    for key in SCHEMA_STR_KEYS:
        if key in cfg and cfg[key] is not None and not isinstance(cfg[key], str):
            warn(key, "str", cfg[key])

    for key in SCHEMA_LIST_KEYS:
        if key in cfg and cfg[key] is not None and not isinstance(cfg[key], list):
            warn(key, "list", cfg[key])

    for key in SCHEMA_DICT_KEYS:
        if key in cfg and cfg[key] is not None and not isinstance(cfg[key], dict):
            warn(key, "dict", cfg[key])

    return warnings
