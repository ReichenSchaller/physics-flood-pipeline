# Manual Field-to-Guide Coverage Audit

Generated: 2026-06-02T15:03:33
Manual file: `/proj/zefflab/projects/Flooding/pipeline/web_launcher/manual.html`
Guide file: `/proj/zefflab/projects/Flooding/pipeline/web_launcher/guide.html`

## Quick coverage summary

| Manual tab | Guide panel | Controls | Mentioned | Missing |
|---|---:|---:|---:|---:|
| 0 Run identity | `run_identity` | 10 | 3 | 7 |
| 1 Pipeline | `pipeline` | 5 | 0 | 5 |
| 2 Slurm general | `slurm_general` | 7 | 1 | 6 |
| 3 Stage resources | `stage_resources` | 18 | 0 | 18 |
| 4 Data catalogs | `data_catalogs` | 1 | 1 | 0 |
| 5 Required inputs | `required_inputs` | 6 | 1 | 5 |
| 6 Optional inputs | `optional_inputs` | 27 | 0 | 27 |
| 7 Model settings | `model_settings` | 18 | 3 | 15 |
| 8 Elevation/mask | `elevation_mask` | 9 | 0 | 9 |
| 9 Roughness | `roughness` | 5 | 0 | 5 |
| 10 Subgrid | `subgrid` | 10 | 1 | 9 |
| 11 Forcing | `forcing` | 21 | 0 | 21 |
| 12 Infiltration | `infiltration` | 18 | 0 | 18 |
| 13 Output | `output` | 11 | 0 | 11 |
| 14 Advanced | `advanced` | 1 | 0 | 1 |
| 15 Postprocess | `postprocess` | 27 | 0 | 27 |
| 16 Safety/debug | `safety_debug` | 10 | 0 | 10 |
| 17 Backend paths | `backend_paths` | 10 | 3 | 7 |
| Check all | `check_all` | 1 | 0 | 1 |
| Submit | `submit` | 3 | 3 | 0 |

## Missing field mentions by guide panel

### 0 Run identity → `run_identity`

- L534: `event_name` (input)
  - nearby label/snippet: Setting Value Notes event_name
- L535: `run_series` (input)
  - nearby label/snippet: run_series
- L540: `overwrite_existing_run` (select)
  - nearby label/snippet: overwrite_existing_run
  - options: `false`, `true`
- L541: `allow_writes_inside_proj` (select)
  - nearby label/snippet: allow_writes_inside_proj
  - options: `true`, `false`
- L542: `allow_missing_model_inputs` (select)
  - nearby label/snippet: allow_missing_model_inputs
  - options: `false`, `true`
- L543: `run_description` (input)
  - nearby label/snippet: run_description
- L544: `run_tags` (textarea)
  - nearby label/snippet: run_tags

### 1 Pipeline → `pipeline`

- L557: `run_preprocessing_job` (select)
  - nearby label/snippet: Setting Value Notes run_preprocessing_job
  - options: `true`, `false`
- L558: `run_sfincs_job` (select)
  - nearby label/snippet: run_sfincs_job
  - options: `true`, `false`
- L559: `run_postprocessing_job` (select)
  - nearby label/snippet: run_postprocessing_job
  - options: `true`, `false`
- L560: `submit_with_dependencies` (select)
  - nearby label/snippet: submit_with_dependencies
  - options: `true`, `false`
- L561: `dependency_type` (select)
  - nearby label/snippet: dependency_type
  - options: `afterok`

### 2 Slurm general → `slurm_general`

- L575: `slurm_partition` (input)
  - nearby label/snippet: slurm_partition
- L576: `slurm_qos` (input)
  - nearby label/snippet: slurm_qos
- L577: `slurm_email` (input)
  - nearby label/snippet: slurm_email
- L578: `slurm_mail_type` (input)
  - nearby label/snippet: slurm_mail_type
- L579: `slurm_extra_directives` (textarea)
  - nearby label/snippet: slurm_extra_directives
- L580: `bash_strict_mode` (select)
  - nearby label/snippet: bash_strict_mode
  - options: `true`, `false`

### 3 Stage resources → `stage_resources`

- L593: `preprocess_time` (input)
  - nearby label/snippet: Setting Value Notes preprocess_time
- L594: `preprocess_nodes` (input)
  - nearby label/snippet: preprocess_nodes
- L595: `preprocess_ntasks` (input)
  - nearby label/snippet: preprocess_ntasks
- L596: `preprocess_cpus_per_task` (input)
  - nearby label/snippet: preprocess_cpus_per_task
- L597: `preprocess_mem` (input)
  - nearby label/snippet: preprocess_mem
- L598: `sfincs_time` (input)
  - nearby label/snippet: sfincs_time
- L599: `sfincs_nodes` (input)
  - nearby label/snippet: sfincs_nodes
- L600: `sfincs_ntasks` (input)
  - nearby label/snippet: sfincs_ntasks
- L601: `sfincs_cpus_per_task` (input)
  - nearby label/snippet: sfincs_cpus_per_task
- L602: `sfincs_mem` (input)
  - nearby label/snippet: sfincs_mem
- L603: `postprocess_time` (input)
  - nearby label/snippet: postprocess_time
- L604: `postprocess_nodes` (input)
  - nearby label/snippet: postprocess_nodes
- L605: `postprocess_ntasks` (input)
  - nearby label/snippet: postprocess_ntasks
- L606: `postprocess_cpus_per_task` (input)
  - nearby label/snippet: postprocess_cpus_per_task
- L607: `postprocess_mem` (input)
  - nearby label/snippet: postprocess_mem
- L608: `sfincs_use_openmp_threads` (select)
  - nearby label/snippet: sfincs_use_openmp_threads
  - options: `true`, `false`
- L609: `sfincs_omp_proc_bind` (input)
  - nearby label/snippet: sfincs_omp_proc_bind
- L610: `sfincs_omp_places` (input)
  - nearby label/snippet: sfincs_omp_places

### 5 Required inputs → `required_inputs`

- L636: `region_mode` (select)
  - nearby label/snippet: Setting Value Notes region_mode
  - options: `geom`, `bbox`
- L638: `region_bbox` (textarea)
  - nearby label/snippet: region_path region_bbox
- L639: `dem_paths` (textarea)
  - nearby label/snippet: dem_paths
- L640: `hydromt_dem_sources` (textarea)
  - nearby label/snippet: hydromt_dem_sources
- L643: `require_at_least_one_forcing` (select)
  - nearby label/snippet: require_at_least_one_forcing
  - options: `true`, `false`

### 6 Optional inputs → `optional_inputs`

- L656: `bathy_paths` (textarea)
  - nearby label/snippet: Setting Value Notes bathy_paths
- L657: `hydromt_bathy_sources` (textarea)
  - nearby label/snippet: hydromt_bathy_sources
- L660: `landcover_path` (input)
  - nearby label/snippet: landcover_path
- L661: `landcover_source` (input)
  - nearby label/snippet: landcover_source
- L662: `landcover_reclass_table` (input)
  - nearby label/snippet: landcover_reclass_table
- L663: `hydromt_roughness_sources` (textarea)
  - nearby label/snippet: landcover_reclass_table hydromt_roughness_sources
- L664: `rainfall_path` (input)
  - nearby label/snippet: landcover_reclass_table hydromt_roughness_sources [] rainfall_path
- L665: `rainfall_source` (input)
  - nearby label/snippet: rainfall_source
- L666: `rainfall_variable` (input)
  - nearby label/snippet: rainfall_variable
- L667: `waterlevel_path` (input)
  - nearby label/snippet: waterlevel_path
- L668: `waterlevel_source` (input)
  - nearby label/snippet: waterlevel_source
- L669: `waterlevel_variable` (input)
  - nearby label/snippet: waterlevel_variable
- L670: `discharge_source` (input)
  - nearby label/snippet: discharge_source
- L671: `streamflow_site_info_path` (input)
  - nearby label/snippet: streamflow_site_info_path
- L672: `streamflow_data_path` (input)
  - nearby label/snippet: streamflow_data_path
- L673: `hydrography_path` (input)
  - nearby label/snippet: hydrography_path
- L674: `hydrography_source` (input)
  - nearby label/snippet: hydrography_source
- L675: `obs_points_path` (input)
  - nearby label/snippet: obs_points_path
- L676: `obs_lines_path` (input)
  - nearby label/snippet: obs_points_path obs_lines_path
- L677: `thin_dam_source_kind` (select)
  - nearby label/snippet: obs_points_path obs_lines_path thin_dam_source_kind
  - options: `none`, `geodataframe`, `native_sfincs`
- L678: `thin_dam_path` (input)
  - nearby label/snippet: thin_dam_path
- L679: `weir_source_kind` (select)
  - nearby label/snippet: weir_source_kind
  - options: `none`, `geodataframe`, `native_sfincs`
- L680: `weir_path` (input)
  - nearby label/snippet: weir_path
- L681: `drainage_structure_source_kind` (select)
  - nearby label/snippet: drainage_structure_source_kind
  - options: `none`, `geodataframe`, `native_sfincs`
- L682: `drainage_structure_path` (input)
  - nearby label/snippet: drainage_structure_path
- L683: `culvert_source_kind` (select)
  - nearby label/snippet: culvert_source_kind
  - options: `none`, `geodataframe`, `native_sfincs`
- L684: `culvert_path` (input)
  - nearby label/snippet: culvert_path

### 7 Model settings → `model_settings`

- L697: `grid_resolution_m` (input)
  - nearby label/snippet: Setting Value Notes grid_resolution_m
- L698: `grid_dx_m` (input)
  - nearby label/snippet: grid_dx_m
- L699: `grid_dy_m` (input)
  - nearby label/snippet: grid_dy_m
- L700: `grid_crs` (input)
  - nearby label/snippet: grid_crs
- L701: `grid_rotated` (select)
  - nearby label/snippet: grid_rotated
  - options: `true`, `false`
- L702: `grid_rotation_deg` (input)
  - nearby label/snippet: grid_rotation_deg
- L706: `use_rainfall` (select)
  - nearby label/snippet: use_rainfall
  - options: `true`, `false`
- L707: `use_waterlevel_boundary` (select)
  - nearby label/snippet: use_waterlevel_boundary
  - options: `true`, `false`
- L708: `use_discharge_boundary` (select)
  - nearby label/snippet: use_discharge_boundary
  - options: `true`, `false`
- L709: `use_infiltration` (select)
  - nearby label/snippet: use_infiltration
  - options: `true`, `false`
- L710: `use_wind` (select)
  - nearby label/snippet: use_wind
  - options: `false`, `true`
- L711: `use_pressure` (select)
  - nearby label/snippet: use_pressure
  - options: `false`, `true`
- L712: `use_structures` (select)
  - nearby label/snippet: use_structures
  - options: `true`, `false`
- L713: `use_obs_points` (select)
  - nearby label/snippet: use_obs_points
  - options: `true`, `false`
- L714: `use_obs_lines` (select)
  - nearby label/snippet: use_obs_lines
  - options: `true`, `false`

### 8 Elevation/mask → `elevation_mask`

- L727: `dem_zmin` (input)
  - nearby label/snippet: Setting Value Notes dem_zmin
- L728: `elevation_buffer_cells` (input)
  - nearby label/snippet: elevation_buffer_cells
- L729: `active_zmin` (input)
  - nearby label/snippet: active_zmin
- L730: `mask_fill_area_km2` (input)
  - nearby label/snippet: mask_fill_area_km2
- L731: `mask_drop_area_km2` (input)
  - nearby label/snippet: mask_drop_area_km2
- L732: `waterlevel_boundary_zmax` (input)
  - nearby label/snippet: waterlevel_boundary_zmax
- L733: `reset_waterlevel_boundary` (select)
  - nearby label/snippet: reset_waterlevel_boundary
  - options: `true`, `false`
- L734: `outflow_boundary_polygon_path` (input)
  - nearby label/snippet: outflow_boundary_polygon_path
- L735: `reset_outflow_boundary` (select)
  - nearby label/snippet: reset_outflow_boundary
  - options: `true`, `false`

### 9 Roughness → `roughness`

- L748: `manning_uniform` (input)
  - nearby label/snippet: Setting Value Notes manning_uniform
- L749: `manning_land` (input)
  - nearby label/snippet: manning_land
- L750: `manning_sea` (input)
  - nearby label/snippet: manning_sea
- L751: `roughness_land_level_m` (input)
  - nearby label/snippet: roughness_land_level_m
- L752: `use_landcover_roughness_if_available` (select)
  - nearby label/snippet: use_landcover_roughness_if_available
  - options: `true`, `false`

### 10 Subgrid → `subgrid`

- L784: `subgrid_source_kind` (select)
  - nearby label/snippet: subgrid_source_kind
  - options: `hydromt_generate`, `premade_sbgfile`, `none`
- L793: `subgrid_native_file_path` (input)
  - nearby label/snippet: Backend support may need to be added for this new key.
- L797: `subgrid_nr_pixels` (input)
  - nearby label/snippet: subgrid_nr_pixels
- L804: `subgrid_write_dep_tif` (select)
  - nearby label/snippet: subgrid_write_dep_tif
  - options: `true`, `false`
- L815: `subgrid_write_man_tif` (select)
  - nearby label/snippet: subgrid_write_man_tif
  - options: `true`, `false`
- L826: `subgrid_use_rivers` (select)
  - nearby label/snippet: subgrid_use_rivers
  - options: `false`, `true`
- L834: `subgrid_river_path` (input)
  - nearby label/snippet: subgrid_use_rivers false true Use river network information in subgrid generation when supported by the preprocessing path.
- L838: `subgrid_river_source` (input)
  - nearby label/snippet: subgrid_river_source
- L845: `use_spatially_variable_roughness` (select)
  - nearby label/snippet: use_spatially_variable_roughness
  - options: `true`, `false`

### 11 Forcing → `forcing`

- L868: `rainfall_kind` (select)
  - nearby label/snippet: Setting Value Notes rainfall_kind
  - options: `spatial`, `uniform`, `event_catalog_aorc`
- L879: `rainfall_uniform_mm_hr` (input)
  - nearby label/snippet: rainfall_uniform_mm_hr
- L886: `rainfall_clip_to_model_time` (select)
  - nearby label/snippet: rainfall_clip_to_model_time
  - options: `true`, `false`
- L897: `waterlevel_source_kind` (select)
  - nearby label/snippet: waterlevel_source_kind
  - options: `geodataset`, `csv`, `cora`, `event_catalog_csv`, `native_sfincs`
- L911: `waterlevel_clip_to_model_time` (select)
  - nearby label/snippet: waterlevel_clip_to_model_time
  - options: `true`, `false`
- L922: `discharge_source_kind` (select)
  - nearby label/snippet: discharge_source_kind
  - options: `geodataset`, `csv`, `event_catalog_csv`, `native_sfincs`
- L935: `discharge_clip_to_model_time` (select)
  - nearby label/snippet: discharge_clip_to_model_time
  - options: `true`, `false`
- L945: `discharge_points_csv_path` (input)
  - nearby label/snippet: discharge_points_csv_path
- L951: `discharge_points_x_column` (input)
  - nearby label/snippet: discharge_points_x_column
- L957: `discharge_points_y_column` (input)
  - nearby label/snippet: discharge_points_y_column
- L963: `discharge_points_name_column` (input)
  - nearby label/snippet: discharge_points_name_column
- L969: `discharge_timeseries_csv_path` (input)
  - nearby label/snippet: discharge_timeseries_csv_path
- L975: `discharge_time_column` (input)
  - nearby label/snippet: discharge_time_column
- L981: `discharge_value_columns` (textarea)
  - nearby label/snippet: discharge_value_columns
- L987: `discharge_time_format` (input)
  - nearby label/snippet: discharge_time_format
- L993: `discharge_units` (input)
  - nearby label/snippet: discharge_units
- L999: `meteo_update_interval_s` (input)
  - nearby label/snippet: meteo_update_interval_s
- L1005: `wind_path` (input)
  - nearby label/snippet: wind_path
- L1011: `pressure_path` (input)
  - nearby label/snippet: pressure_path
- L1017: `wind_source` (input)
  - nearby label/snippet: wind_source
- L1023: `pressure_source` (input)
  - nearby label/snippet: pressure_source

### 12 Infiltration → `infiltration`

- L1041: `infiltration_mode` (select)
  - nearby label/snippet: Setting Value Notes infiltration_mode
  - options: `none`, `constant`, `spatial_constant`, `curve_number`, `curve_number_with_ks`, `native_sfincs`
- L1052: `qinf_mm_hr` (input)
  - nearby label/snippet: qinf_mm_hr
- L1053: `qinf_zmin_m` (input)
  - nearby label/snippet: qinf_zmin_m
- L1054: `scs_initial_abstraction_factor` (input)
  - nearby label/snippet: scs_initial_abstraction_factor
- L1055: `infiltration_path` (input)
  - nearby label/snippet: infiltration_path
- L1056: `curve_number_path` (input)
  - nearby label/snippet: curve_number_path
- L1057: `hsg_path` (input)
  - nearby label/snippet: hsg_path
- L1058: `soil_storage_path` (input)
  - nearby label/snippet: soil_storage_path
- L1060: `qinf_path` (input)
  - nearby label/snippet: qinf_path
- L1061: `smax_path` (input)
  - nearby label/snippet: smax_path
- L1062: `seff_path` (input)
  - nearby label/snippet: seff_path
- L1063: `ks_path` (input)
  - nearby label/snippet: ks_path
- L1065: `sigma_path` (input)
  - nearby label/snippet: sigma_path
- L1066: `psi_path` (input)
  - nearby label/snippet: psi_path
- L1068: `f0_path` (input)
  - nearby label/snippet: f0_path
- L1069: `fc_path` (input)
  - nearby label/snippet: fc_path
- L1070: `kd_path` (input)
  - nearby label/snippet: kd_path
- L1072: `vol_path` (input)
  - nearby label/snippet: vol_path

### 13 Output → `output`

- L1085: `output_format` (input)
  - nearby label/snippet: Setting Value Notes output_format
- L1086: `dtout_s` (input)
  - nearby label/snippet: dtout_s
- L1087: `dthisout_s` (input)
  - nearby label/snippet: dthisout_s
- L1088: `dtmaxout_s` (input)
  - nearby label/snippet: dtmaxout_s
- L1089: `dtrstout_s` (input)
  - nearby label/snippet: dtrstout_s
- L1090: `store_wet_duration` (select)
  - nearby label/snippet: store_wet_duration
  - options: `false`, `true`
- L1091: `store_velocity` (select)
  - nearby label/snippet: store_velocity
  - options: `false`, `true`
- L1092: `store_max_velocity` (select)
  - nearby label/snippet: store_max_velocity
  - options: `true`, `false`
- L1093: `store_max_flux` (select)
  - nearby label/snippet: store_max_flux
  - options: `false`, `true`
- L1094: `store_cumulative_precip` (select)
  - nearby label/snippet: store_cumulative_precip
  - options: `true`, `false`
- L1095: `store_hmax_subgrid` (select)
  - nearby label/snippet: store_hmax_subgrid
  - options: `true`, `false`

### 14 Advanced → `advanced`

- L1110: `advanced_config` (textarea)
  - nearby label/snippet: Setting Value Notes advanced_config

### 15 Postprocess → `postprocess`

- L1160: `postprocess_create_summary_txt` (select)
  - nearby label/snippet: Setting Value Notes postprocess_create_summary_txt
  - options: `true`, `false`
- L1161: `postprocess_create_summary_json` (select)
  - nearby label/snippet: postprocess_create_summary_json
  - options: `true`, `false`
- L1162: `postprocess_list_output_variables` (select)
  - nearby label/snippet: postprocess_list_output_variables
  - options: `true`, `false`
- L1163: `postprocess_make_quicklook_plots` (select)
  - nearby label/snippet: postprocess_make_quicklook_plots
  - options: `true`, `false`
- L1164: `postprocess_plot_max_water_level` (select)
  - nearby label/snippet: postprocess_plot_max_water_level
  - options: `true`, `false`
- L1165: `postprocess_plot_max_flood_depth` (select)
  - nearby label/snippet: postprocess_plot_max_flood_depth
  - options: `true`, `false`
- L1166: `postprocess_plot_final_water_level` (select)
  - nearby label/snippet: postprocess_plot_final_water_level
  - options: `true`, `false`
- L1167: `postprocess_plot_obs_hydrographs` (select)
  - nearby label/snippet: postprocess_plot_obs_hydrographs
  - options: `true`, `false`
- L1168: `postprocess_use_basemap` (select)
  - nearby label/snippet: postprocess_use_basemap
  - options: `true`, `false`
- L1169: `postprocess_basemap_source` (input)
  - nearby label/snippet: postprocess_basemap_source
- L1170: `postprocess_basemap_zoomlevel` (input)
  - nearby label/snippet: postprocess_basemap_zoomlevel
- L1171: `postprocess_use_rotated_map_plots` (select)
  - nearby label/snippet: postprocess_use_rotated_map_plots
  - options: `true`, `false`
- L1172: `postprocess_use_basemap_on_result_maps` (select)
  - nearby label/snippet: postprocess_use_basemap_on_result_maps
  - options: `true`, `false`
- L1173: `postprocess_result_map_alpha` (input)
  - nearby label/snippet: postprocess_result_map_alpha
- L1174: `postprocess_result_map_background_fade_alpha` (input)
  - nearby label/snippet: postprocess_result_map_background_fade_alpha
- L1175: `postprocess_result_map_show_model_features` (select)
  - nearby label/snippet: postprocess_result_map_show_model_features
  - options: `false`, `true`
- L1176: `postprocess_result_map_show_obs` (select)
  - nearby label/snippet: postprocess_result_map_show_obs
  - options: `false`, `true`
- L1177: `postprocess_result_map_show_boundaries` (select)
  - nearby label/snippet: postprocess_result_map_show_boundaries
  - options: `false`, `true`
- L1178: `postprocess_result_map_show_dep_layer` (select)
  - nearby label/snippet: postprocess_result_map_show_dep_layer
  - options: `false`, `true`
- L1179: `postprocess_result_map_show_layout_legend` (select)
  - nearby label/snippet: postprocess_result_map_show_layout_legend
  - options: `false`, `true`
- L1180: `postprocess_waterlevel_var_candidates` (textarea)
  - nearby label/snippet: postprocess_waterlevel_var_candidates
- L1181: `postprocess_bedlevel_var_candidates` (textarea)
  - nearby label/snippet: postprocess_bedlevel_var_candidates
- L1182: `postprocess_depth_var_candidates` (textarea)
  - nearby label/snippet: postprocess_depth_var_candidates
- L1183: `postprocess_max_waterlevel_var_candidates` (textarea)
  - nearby label/snippet: postprocess_max_waterlevel_var_candidates
- L1184: `postprocess_max_depth_var_candidates` (textarea)
  - nearby label/snippet: postprocess_max_depth_var_candidates
- L1185: `postprocess_matplotlib_backend` (input)
  - nearby label/snippet: postprocess_matplotlib_backend
- L1186: `postprocess_max_plot_cells` (input)
  - nearby label/snippet: postprocess_max_plot_cells

### 16 Safety/debug → `safety_debug`

- L1199: `print_config_summary` (select)
  - nearby label/snippet: Setting Value Notes print_config_summary
  - options: `true`, `false`
- L1200: `validate_paths_before_submit` (select)
  - nearby label/snippet: validate_paths_before_submit
  - options: `true`, `false`
- L1201: `stop_if_required_path_missing` (select)
  - nearby label/snippet: stop_if_required_path_missing
  - options: `true`, `false`
- L1202: `save_data_inventory` (select)
  - nearby label/snippet: save_data_inventory
  - options: `true`, `false`
- L1203: `save_config_json` (select)
  - nearby label/snippet: save_config_json
  - options: `true`, `false`
- L1204: `save_job_ids` (select)
  - nearby label/snippet: save_job_ids
  - options: `true`, `false`
- L1205: `print_optional_path_warnings` (select)
  - nearby label/snippet: print_optional_path_warnings
  - options: `true`, `false`
- L1206: `warn_unknown_config_keys` (select)
  - nearby label/snippet: warn_unknown_config_keys
  - options: `true`, `false`
- L1207: `strict_schema_validation` (select)
  - nearby label/snippet: strict_schema_validation
  - options: `false`, `true`
- L1208: `warn_schema_type_mismatches` (select)
  - nearby label/snippet: warn_schema_type_mismatches
  - options: `true`, `false`

### 17 Backend paths → `backend_paths`

- L1229: `prefer_pipeline_bundle_runtime_paths` (select)
  - nearby label/snippet: Setting Value Notes prefer_pipeline_bundle_runtime_paths
  - options: `true`, `false`
- L1239: `anaconda_module` (input)
  - nearby label/snippet: anaconda_module
- L1245: `apptainer_module` (input)
  - nearby label/snippet: apptainer_module
- L1251: `preprocess_stage_script` (input)
  - nearby label/snippet: preprocess_stage_script
- L1257: `postprocess_stage_script` (input)
  - nearby label/snippet: postprocess_stage_script
- L1282: `preprocess_enable_hydromt_file_logging` (select)
  - nearby label/snippet: preprocess_enable_hydromt_file_logging
  - options: `false`, `true`
- L1293: `(unnamed select)` (select, disabled)
  - nearby label/snippet: preprocess timing report
  - options: `backend hook needed`

### Check all → `check_all`

- L1313: `check-button-2` (button, type=button)
  - nearby label/snippet: Run page checks

## Full controls by Manual tab

### 0 Run identity → `run_identity`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 534 | `event_name` | input | harvey_2017 |  | NO |
| 535 | `run_series` | input | manual_001 |  | NO |
| 536 | `run_name` | input | harris_harvey_2017_manual_001 |  | YES |
| 537 | `project_root` | input | /proj/zefflab/projects/Flooding/pipeline |  | YES |
| 538 | `output_root` | input | /proj/zefflab/projects/Flooding/sfincs_runs |  | YES |
| 540 | `overwrite_existing_run` | select | false | false, true | NO |
| 541 | `allow_writes_inside_proj` | select | true | true, false | NO |
| 542 | `allow_missing_model_inputs` | select | false | false, true | NO |
| 543 | `run_description` | input | Manual launcher SFINCS pipeline run. |  | NO |
| 544 | `run_tags` | textarea | ["manual", "sfincs", "harris_county"] |  | NO |

### 1 Pipeline → `pipeline`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 557 | `run_preprocessing_job` | select | true | true, false | NO |
| 558 | `run_sfincs_job` | select | true | true, false | NO |
| 559 | `run_postprocessing_job` | select | true | true, false | NO |
| 560 | `submit_with_dependencies` | select | true | true, false | NO |
| 561 | `dependency_type` | select |  | afterok | NO |

### 2 Slurm general → `slurm_general`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 574 | `slurm_account` | input |  |  | YES |
| 575 | `slurm_partition` | input |  |  | NO |
| 576 | `slurm_qos` | input |  |  | NO |
| 577 | `slurm_email` | input |  |  | NO |
| 578 | `slurm_mail_type` | input | END,FAIL |  | NO |
| 579 | `slurm_extra_directives` | textarea | [] |  | NO |
| 580 | `bash_strict_mode` | select | true | true, false | NO |

### 3 Stage resources → `stage_resources`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 593 | `preprocess_time` | input | 01:00:00 |  | NO |
| 594 | `preprocess_nodes` | input | 1 |  | NO |
| 595 | `preprocess_ntasks` | input | 1 |  | NO |
| 596 | `preprocess_cpus_per_task` | input | 4 |  | NO |
| 597 | `preprocess_mem` | input | 16G |  | NO |
| 598 | `sfincs_time` | input | 04:00:00 |  | NO |
| 599 | `sfincs_nodes` | input | 1 |  | NO |
| 600 | `sfincs_ntasks` | input | 1 |  | NO |
| 601 | `sfincs_cpus_per_task` | input | 8 |  | NO |
| 602 | `sfincs_mem` | input | 32G |  | NO |
| 603 | `postprocess_time` | input | 01:00:00 |  | NO |
| 604 | `postprocess_nodes` | input | 1 |  | NO |
| 605 | `postprocess_ntasks` | input | 1 |  | NO |
| 606 | `postprocess_cpus_per_task` | input | 2 |  | NO |
| 607 | `postprocess_mem` | input | 24G |  | NO |
| 608 | `sfincs_use_openmp_threads` | select | true | true, false | NO |
| 609 | `sfincs_omp_proc_bind` | input | true |  | NO |
| 610 | `sfincs_omp_places` | input | cores |  | NO |

### 4 Data catalogs → `data_catalogs`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 623 | `data_catalogs` | textarea | ["artifact_data"] |  | YES |

### 5 Required inputs → `required_inputs`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 636 | `region_mode` | select |  | geom, bbox | NO |
| 637 | `region_path` | input |  |  | YES |
| 638 | `region_bbox` | textarea |  |  | NO |
| 639 | `dem_paths` | textarea | [] |  | NO |
| 640 | `hydromt_dem_sources` | textarea | [ {"elevation": "merit_hydro", "zmin": 0.001} ] |  | NO |
| 643 | `require_at_least_one_forcing` | select | true | true, false | NO |

### 6 Optional inputs → `optional_inputs`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 656 | `bathy_paths` | textarea | [] |  | NO |
| 657 | `hydromt_bathy_sources` | textarea | [ {"elevation": "gebco"} ] |  | NO |
| 660 | `landcover_path` | input |  |  | NO |
| 661 | `landcover_source` | input | vito_2015 |  | NO |
| 662 | `landcover_reclass_table` | input |  |  | NO |
| 663 | `hydromt_roughness_sources` | textarea | [] |  | NO |
| 664 | `rainfall_path` | input |  |  | NO |
| 665 | `rainfall_source` | input | era5_hourly |  | NO |
| 666 | `rainfall_variable` | input | precip |  | NO |
| 667 | `waterlevel_path` | input |  |  | NO |
| 668 | `waterlevel_source` | input | gtsmv3_eu_era5 |  | NO |
| 669 | `waterlevel_variable` | input | zeta |  | NO |
| 670 | `discharge_source` | input | discharge_forcing |  | NO |
| 671 | `streamflow_site_info_path` | input |  |  | NO |
| 672 | `streamflow_data_path` | input |  |  | NO |
| 673 | `hydrography_path` | input |  |  | NO |
| 674 | `hydrography_source` | input | nhdplus_or_enhdplus |  | NO |
| 675 | `obs_points_path` | input |  |  | NO |
| 676 | `obs_lines_path` | input |  |  | NO |
| 677 | `thin_dam_source_kind` | select |  | none, geodataframe, native_sfincs | NO |
| 678 | `thin_dam_path` | input |  |  | NO |
| 679 | `weir_source_kind` | select |  | none, geodataframe, native_sfincs | NO |
| 680 | `weir_path` | input |  |  | NO |
| 681 | `drainage_structure_source_kind` | select |  | none, geodataframe, native_sfincs | NO |
| 682 | `drainage_structure_path` | input |  |  | NO |
| 683 | `culvert_source_kind` | select |  | none, geodataframe, native_sfincs | NO |
| 684 | `culvert_path` | input |  |  | NO |

### 7 Model settings → `model_settings`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 697 | `grid_resolution_m` | input | 50 |  | NO |
| 698 | `grid_dx_m` | input | 100 |  | NO |
| 699 | `grid_dy_m` | input | 100 |  | NO |
| 700 | `grid_crs` | input | utm |  | NO |
| 701 | `grid_rotated` | select | true | true, false | NO |
| 702 | `grid_rotation_deg` | input |  |  | NO |
| 703 | `tref` | input | 2017-08-22 00:00:00 |  | YES |
| 704 | `tstart` | input | 2017-08-22 00:00:00 |  | YES |
| 705 | `tstop` | input | 2017-09-17 01:00:00 |  | YES |
| 706 | `use_rainfall` | select | true | true, false | NO |
| 707 | `use_waterlevel_boundary` | select | true | true, false | NO |
| 708 | `use_discharge_boundary` | select | true | true, false | NO |
| 709 | `use_infiltration` | select | true | true, false | NO |
| 710 | `use_wind` | select | false | false, true | NO |
| 711 | `use_pressure` | select | false | false, true | NO |
| 712 | `use_structures` | select | true | true, false | NO |
| 713 | `use_obs_points` | select | true | true, false | NO |
| 714 | `use_obs_lines` | select | true | true, false | NO |

### 8 Elevation/mask → `elevation_mask`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 727 | `dem_zmin` | input | 0.001 |  | NO |
| 728 | `elevation_buffer_cells` | input | 1 |  | NO |
| 729 | `active_zmin` | input | -5.0 |  | NO |
| 730 | `mask_fill_area_km2` | input | 10.0 |  | NO |
| 731 | `mask_drop_area_km2` | input | 0.0 |  | NO |
| 732 | `waterlevel_boundary_zmax` | input | -5.0 |  | NO |
| 733 | `reset_waterlevel_boundary` | select | true | true, false | NO |
| 734 | `outflow_boundary_polygon_path` | input |  |  | NO |
| 735 | `reset_outflow_boundary` | select | true | true, false | NO |

### 9 Roughness → `roughness`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 748 | `manning_uniform` | input | 0.04 |  | NO |
| 749 | `manning_land` | input | 0.04 |  | NO |
| 750 | `manning_sea` | input | 0.02 |  | NO |
| 751 | `roughness_land_level_m` | input | 0.0 |  | NO |
| 752 | `use_landcover_roughness_if_available` | select | true | true, false | NO |

### 10 Subgrid → `subgrid`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 773 | `use_subgrid` | select | true | true, false | YES |
| 784 | `subgrid_source_kind` | select |  | hydromt_generate, premade_sbgfile, none | NO |
| 793 | `subgrid_native_file_path` | input |  |  | NO |
| 797 | `subgrid_nr_pixels` | input | 6 |  | NO |
| 804 | `subgrid_write_dep_tif` | select | true | true, false | NO |
| 815 | `subgrid_write_man_tif` | select | true | true, false | NO |
| 826 | `subgrid_use_rivers` | select | false | false, true | NO |
| 834 | `subgrid_river_path` | input |  |  | NO |
| 838 | `subgrid_river_source` | input | river_network_for_subgrid |  | NO |
| 845 | `use_spatially_variable_roughness` | select | true | true, false | NO |

### 11 Forcing → `forcing`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 868 | `rainfall_kind` | select |  | spatial, uniform, event_catalog_aorc | NO |
| 879 | `rainfall_uniform_mm_hr` | input |  |  | NO |
| 886 | `rainfall_clip_to_model_time` | select | true | true, false | NO |
| 897 | `waterlevel_source_kind` | select |  | geodataset, csv, cora, event_catalog_csv, native_sfincs | NO |
| 911 | `waterlevel_clip_to_model_time` | select | true | true, false | NO |
| 922 | `discharge_source_kind` | select |  | geodataset, csv, event_catalog_csv, native_sfincs | NO |
| 935 | `discharge_clip_to_model_time` | select | true | true, false | NO |
| 945 | `discharge_points_csv_path` | input |  |  | NO |
| 951 | `discharge_points_x_column` | input | x |  | NO |
| 957 | `discharge_points_y_column` | input | y |  | NO |
| 963 | `discharge_points_name_column` | input | name |  | NO |
| 969 | `discharge_timeseries_csv_path` | input |  |  | NO |
| 975 | `discharge_time_column` | input | time |  | NO |
| 981 | `discharge_value_columns` | textarea | [] |  | NO |
| 987 | `discharge_time_format` | input | auto |  | NO |
| 993 | `discharge_units` | input | m3/s |  | NO |
| 999 | `meteo_update_interval_s` | input | 1800 |  | NO |
| 1005 | `wind_path` | input |  |  | NO |
| 1011 | `pressure_path` | input |  |  | NO |
| 1017 | `wind_source` | input | wind_forcing |  | NO |
| 1023 | `pressure_source` | input | pressure_forcing |  | NO |

### 12 Infiltration → `infiltration`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 1041 | `infiltration_mode` | select |  | none, constant, spatial_constant, curve_number, curve_number_with_ks, native_sfincs | NO |
| 1052 | `qinf_mm_hr` | input | 0.0 |  | NO |
| 1053 | `qinf_zmin_m` | input | 0.0 |  | NO |
| 1054 | `scs_initial_abstraction_factor` | input | 0.2 |  | NO |
| 1055 | `infiltration_path` | input |  |  | NO |
| 1056 | `curve_number_path` | input |  |  | NO |
| 1057 | `hsg_path` | input |  |  | NO |
| 1058 | `soil_storage_path` | input |  |  | NO |
| 1060 | `qinf_path` | input |  |  | NO |
| 1061 | `smax_path` | input |  |  | NO |
| 1062 | `seff_path` | input |  |  | NO |
| 1063 | `ks_path` | input |  |  | NO |
| 1065 | `sigma_path` | input |  |  | NO |
| 1066 | `psi_path` | input |  |  | NO |
| 1068 | `f0_path` | input |  |  | NO |
| 1069 | `fc_path` | input |  |  | NO |
| 1070 | `kd_path` | input |  |  | NO |
| 1072 | `vol_path` | input |  |  | NO |

### 13 Output → `output`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 1085 | `output_format` | input | net |  | NO |
| 1086 | `dtout_s` | input | 3600 |  | NO |
| 1087 | `dthisout_s` | input | 900 |  | NO |
| 1088 | `dtmaxout_s` | input | 99999.0 |  | NO |
| 1089 | `dtrstout_s` | input | 259200 |  | NO |
| 1090 | `store_wet_duration` | select | false | false, true | NO |
| 1091 | `store_velocity` | select | false | false, true | NO |
| 1092 | `store_max_velocity` | select | true | true, false | NO |
| 1093 | `store_max_flux` | select | false | false, true | NO |
| 1094 | `store_cumulative_precip` | select | true | true, false | NO |
| 1095 | `store_hmax_subgrid` | select | true | true, false | NO |

### 14 Advanced → `advanced`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 1110 | `advanced_config` | textarea | { "mmax": 997, "nmax": 1012, "dx": 100, "dy": 100, "x0": 211971.0, "y0": 3261... |  | NO |

### 15 Postprocess → `postprocess`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 1160 | `postprocess_create_summary_txt` | select | true | true, false | NO |
| 1161 | `postprocess_create_summary_json` | select | true | true, false | NO |
| 1162 | `postprocess_list_output_variables` | select | true | true, false | NO |
| 1163 | `postprocess_make_quicklook_plots` | select | true | true, false | NO |
| 1164 | `postprocess_plot_max_water_level` | select | true | true, false | NO |
| 1165 | `postprocess_plot_max_flood_depth` | select | true | true, false | NO |
| 1166 | `postprocess_plot_final_water_level` | select | true | true, false | NO |
| 1167 | `postprocess_plot_obs_hydrographs` | select | true | true, false | NO |
| 1168 | `postprocess_use_basemap` | select | true | true, false | NO |
| 1169 | `postprocess_basemap_source` | input | sat |  | NO |
| 1170 | `postprocess_basemap_zoomlevel` | input | 14 |  | NO |
| 1171 | `postprocess_use_rotated_map_plots` | select | true | true, false | NO |
| 1172 | `postprocess_use_basemap_on_result_maps` | select | true | true, false | NO |
| 1173 | `postprocess_result_map_alpha` | input | 1.0 |  | NO |
| 1174 | `postprocess_result_map_background_fade_alpha` | input | 0.35 |  | NO |
| 1175 | `postprocess_result_map_show_model_features` | select | false | false, true | NO |
| 1176 | `postprocess_result_map_show_obs` | select | false | false, true | NO |
| 1177 | `postprocess_result_map_show_boundaries` | select | false | false, true | NO |
| 1178 | `postprocess_result_map_show_dep_layer` | select | false | false, true | NO |
| 1179 | `postprocess_result_map_show_layout_legend` | select | false | false, true | NO |
| 1180 | `postprocess_waterlevel_var_candidates` | textarea | ["zs", "waterlevel", "water_level"] |  | NO |
| 1181 | `postprocess_bedlevel_var_candidates` | textarea | ["zb", "bedlevel", "bed_level", "dep"] |  | NO |
| 1182 | `postprocess_depth_var_candidates` | textarea | ["h", "depth", "flood_depth"] |  | NO |
| 1183 | `postprocess_max_waterlevel_var_candidates` | textarea | ["zsmax", "max_zs", "waterlevel_max"] |  | NO |
| 1184 | `postprocess_max_depth_var_candidates` | textarea | ["hmax", "max_h", "flood_depth_max"] |  | NO |
| 1185 | `postprocess_matplotlib_backend` | input | Agg |  | NO |
| 1186 | `postprocess_max_plot_cells` | input | 2000000 |  | NO |

### 16 Safety/debug → `safety_debug`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 1199 | `print_config_summary` | select | true | true, false | NO |
| 1200 | `validate_paths_before_submit` | select | true | true, false | NO |
| 1201 | `stop_if_required_path_missing` | select | true | true, false | NO |
| 1202 | `save_data_inventory` | select | true | true, false | NO |
| 1203 | `save_config_json` | select | true | true, false | NO |
| 1204 | `save_job_ids` | select | true | true, false | NO |
| 1205 | `print_optional_path_warnings` | select | true | true, false | NO |
| 1206 | `warn_unknown_config_keys` | select | true | true, false | NO |
| 1207 | `strict_schema_validation` | select | false | false, true | NO |
| 1208 | `warn_schema_type_mismatches` | select | true | true, false | NO |

### 17 Backend paths → `backend_paths`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 1229 | `prefer_pipeline_bundle_runtime_paths` | select | true | true, false | NO |
| 1239 | `anaconda_module` | input | anaconda |  | NO |
| 1245 | `apptainer_module` | input | apptainer |  | NO |
| 1251 | `preprocess_stage_script` | input | /proj/zefflab/projects/Flooding/pipeline/code/preprocess_stage.py |  | NO |
| 1257 | `postprocess_stage_script` | input | /proj/zefflab/projects/Flooding/pipeline/code/postprocess_stage.py |  | NO |
| 1263 | `conda_env_path` | input | /proj/zefflab/projects/Flooding/pipeline/envs/sfincs |  | YES |
| 1269 | `conda_python` | input | /proj/zefflab/projects/Flooding/pipeline/envs/sfincs/bin/python |  | YES |
| 1275 | `sfincs_container_path` | input | /proj/zefflab/projects/Flooding/pipeline/containers/sfincs-v2.3.0-mt-Faber-Re... |  | YES |
| 1282 | `preprocess_enable_hydromt_file_logging` | select | false | false, true | NO |
| 1293 | `(unnamed select)` | select |  | backend hook needed | NO |

### Check all → `check_all`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 1313 | `check-button-2` | button |  |  | NO |

### Submit → `submit`

| Line | Key | Tag | Default/value | Options | Mentioned in guide panel? |
|---:|---|---|---|---|---|
| 1350 | `Run backend preflight` | button |  |  | YES |
| 1356 | `Build Slurm scripts` | button |  |  | YES |
| 1364 | `Submit Slurm chain` | button |  |  | YES |
