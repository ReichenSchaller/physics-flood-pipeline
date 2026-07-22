# Manual Guide Content Audit

Generated: 2026-06-02T15:00:42
Manual file: `/proj/zefflab/projects/Flooding/pipeline/web_launcher/manual.html`
Guide file: `/proj/zefflab/projects/Flooding/pipeline/web_launcher/guide.html`

## 1. Manual guide panels found in guide.html

- `advanced`
- `backend_paths`
- `check_all`
- `data_catalogs`
- `elevation_mask`
- `forcing`
- `infiltration`
- `model_settings`
- `optional_inputs`
- `output`
- `pipeline`
- `postprocess`
- `required_inputs`
- `roughness`
- `run_identity`
- `safety_debug`
- `slurm_general`
- `stage_resources`
- `subgrid`
- `submit`

Total guide panels: **20**

## 2. Manual tab candidates found in manual.html

- L502: `div` `tab-strip-wrap`
- L504: `button` `0 Run identity`
- L505: `button` `1 Pipeline`
- L506: `button` `2 Slurm general`
- L507: `button` `3 Stage resources`
- L508: `button` `4 Data catalogs`
- L509: `button` `5 Required inputs`
- L510: `button` `6 Optional inputs`
- L511: `button` `7 Model settings`
- L512: `button` `8 Elevation/mask`
- L513: `button` `9 Roughness`
- L514: `button` `10 Subgrid`
- L515: `button` `11 Forcing`
- L516: `button` `12 Infiltration`
- L517: `button` `13 Output`
- L518: `button` `14 Advanced`
- L519: `button` `15 Postprocess`
- L520: `button` `16 Safety/debug`
- L521: `button` `17 Backend paths`
- L522: `button` `Check all`
- L523: `button` `Submit`
- L528: `div` `tab-0`
- L551: `div` `tab-1`
- L568: `div` `tab-2`
- L587: `div` `tab-3`
- L617: `div` `tab-4`
- L630: `div` `tab-5`
- L650: `div` `tab-6`
- L691: `div` `tab-7`
- L721: `div` `tab-8`
- L742: `div` `tab-9`
- L759: `div` `tab-10`
- L858: `div` `tab-11`
- L1032: `div` `tab-12`
- L1079: `div` `tab-13`
- L1102: `div` `tab-14`
- L1154: `div` `tab-15`
- L1193: `div` `tab-16`
- L1215: `div` `tab-17`
- L1305: `div` `tab-check`
- L1321: `div` `tab-submit`

## 3. Controls found in manual.html

Total controls: **246**

### Context: UNKNOWN

- L466: `pipeline_mode` (input, type=hidden, hidden)
- L467: `preprocess_mode` (input, type=hidden, hidden)
- L468: `data_root` (input, type=hidden, hidden)
- L469: `sfincs_container` (input, type=hidden, hidden)
- L488: `check-button` (button, type=button)
- L491: `New run / wipe page` (button, type=button)
- L494: `save-config-button` (button, type=button)
- L496: `load-config-input` (input, type=file)

### Context: 0 Run identity

- L504: `0 Run identity` (button, type=button)

### Context: 1 Pipeline

- L505: `1 Pipeline` (button, type=button)

### Context: 2 Slurm general

- L506: `2 Slurm general` (button, type=button)

### Context: 3 Stage resources

- L507: `3 Stage resources` (button, type=button)

### Context: 4 Data catalogs

- L508: `4 Data catalogs` (button, type=button)

### Context: 5 Required inputs

- L509: `5 Required inputs` (button, type=button)

### Context: 6 Optional inputs

- L510: `6 Optional inputs` (button, type=button)

### Context: 7 Model settings

- L511: `7 Model settings` (button, type=button)

### Context: 8 Elevation/mask

- L512: `8 Elevation/mask` (button, type=button)

### Context: 9 Roughness

- L513: `9 Roughness` (button, type=button)

### Context: 10 Subgrid

- L514: `10 Subgrid` (button, type=button)

### Context: 11 Forcing

- L515: `11 Forcing` (button, type=button)

### Context: 12 Infiltration

- L516: `12 Infiltration` (button, type=button)

### Context: 13 Output

- L517: `13 Output` (button, type=button)

### Context: 14 Advanced

- L518: `14 Advanced` (button, type=button)

### Context: 15 Postprocess

- L519: `15 Postprocess` (button, type=button)

### Context: 16 Safety/debug

- L520: `16 Safety/debug` (button, type=button)

### Context: 17 Backend paths

- L521: `17 Backend paths` (button, type=button)

### Context: Check all

- L522: `Check all` (button, type=button)

### Context: Submit

- L523: `Submit` (button, type=button)

### Context: TAB 0: RUN IDENTITY START

- L534: `event_name` (input)
- L535: `run_series` (input)
- L536: `run_name` (input)
- L537: `project_root` (input)
- L538: `output_root` (input)
- L540: `overwrite_existing_run` (select)
- L541: `allow_writes_inside_proj` (select)
- L542: `allow_missing_model_inputs` (select)
- L543: `run_description` (input)
- L544: `run_tags` (textarea)

### Context: TAB 1: PIPELINE CONTROL START

- L557: `run_preprocessing_job` (select)
- L558: `run_sfincs_job` (select)
- L559: `run_postprocessing_job` (select)
- L560: `submit_with_dependencies` (select)
- L561: `dependency_type` (select)

### Context: TAB 2: SLURM GENERAL START

- L574: `slurm_account` (input)
- L575: `slurm_partition` (input)
- L576: `slurm_qos` (input)
- L577: `slurm_email` (input)
- L578: `slurm_mail_type` (input)
- L579: `slurm_extra_directives` (textarea)
- L580: `bash_strict_mode` (select)

### Context: TAB 3: STAGE RESOURCES START

- L593: `preprocess_time` (input)
- L594: `preprocess_nodes` (input)
- L595: `preprocess_ntasks` (input)
- L596: `preprocess_cpus_per_task` (input)
- L597: `preprocess_mem` (input)
- L598: `sfincs_time` (input)
- L599: `sfincs_nodes` (input)
- L600: `sfincs_ntasks` (input)
- L601: `sfincs_cpus_per_task` (input)
- L602: `sfincs_mem` (input)
- L603: `postprocess_time` (input)
- L604: `postprocess_nodes` (input)
- L605: `postprocess_ntasks` (input)
- L606: `postprocess_cpus_per_task` (input)
- L607: `postprocess_mem` (input)
- L608: `sfincs_use_openmp_threads` (select)
- L609: `sfincs_omp_proc_bind` (input)
- L610: `sfincs_omp_places` (input)

### Context: TAB 4: DATA CATALOGS START

- L623: `data_catalogs` (textarea)

### Context: TAB 5: REQUIRED INPUTS START

- L636: `region_mode` (select)
- L637: `region_path` (input)
- L638: `region_bbox` (textarea)
- L639: `dem_paths` (textarea)
- L640: `hydromt_dem_sources` (textarea)
- L643: `require_at_least_one_forcing` (select)

### Context: TAB 6: OPTIONAL INPUTS START

- L656: `bathy_paths` (textarea)
- L657: `hydromt_bathy_sources` (textarea)
- L660: `landcover_path` (input)
- L661: `landcover_source` (input)
- L662: `landcover_reclass_table` (input)
- L663: `hydromt_roughness_sources` (textarea)
- L664: `rainfall_path` (input)
- L665: `rainfall_source` (input)
- L666: `rainfall_variable` (input)
- L667: `waterlevel_path` (input)
- L668: `waterlevel_source` (input)
- L669: `waterlevel_variable` (input)
- L670: `discharge_source` (input)
- L671: `streamflow_site_info_path` (input)
- L672: `streamflow_data_path` (input)
- L673: `hydrography_path` (input)
- L674: `hydrography_source` (input)
- L675: `obs_points_path` (input)
- L676: `obs_lines_path` (input)
- L677: `thin_dam_source_kind` (select)
- L678: `thin_dam_path` (input)
- L679: `weir_source_kind` (select)
- L680: `weir_path` (input)
- L681: `drainage_structure_source_kind` (select)
- L682: `drainage_structure_path` (input)
- L683: `culvert_source_kind` (select)
- L684: `culvert_path` (input)

### Context: TAB 7: MODEL SETTINGS START

- L697: `grid_resolution_m` (input)
- L698: `grid_dx_m` (input)
- L699: `grid_dy_m` (input)
- L700: `grid_crs` (input)
- L701: `grid_rotated` (select)
- L702: `grid_rotation_deg` (input)
- L703: `tref` (input)
- L704: `tstart` (input)
- L705: `tstop` (input)
- L706: `use_rainfall` (select)
- L707: `use_waterlevel_boundary` (select)
- L708: `use_discharge_boundary` (select)
- L709: `use_infiltration` (select)
- L710: `use_wind` (select)
- L711: `use_pressure` (select)
- L712: `use_structures` (select)
- L713: `use_obs_points` (select)
- L714: `use_obs_lines` (select)

### Context: TAB 8: ELEVATION MASK START

- L727: `dem_zmin` (input)
- L728: `elevation_buffer_cells` (input)
- L729: `active_zmin` (input)
- L730: `mask_fill_area_km2` (input)
- L731: `mask_drop_area_km2` (input)
- L732: `waterlevel_boundary_zmax` (input)
- L733: `reset_waterlevel_boundary` (select)
- L734: `outflow_boundary_polygon_path` (input)
- L735: `reset_outflow_boundary` (select)

### Context: TAB 9: ROUGHNESS START

- L748: `manning_uniform` (input)
- L749: `manning_land` (input)
- L750: `manning_sea` (input)
- L751: `roughness_land_level_m` (input)
- L752: `use_landcover_roughness_if_available` (select)

### Context: TAB 10: SUBGRID START

- L773: `use_subgrid` (select)
- L784: `subgrid_source_kind` (select)
- L793: `subgrid_native_file_path` (input)
- L797: `subgrid_nr_pixels` (input)
- L804: `subgrid_write_dep_tif` (select)
- L815: `subgrid_write_man_tif` (select)
- L826: `subgrid_use_rivers` (select)
- L834: `subgrid_river_path` (input)
- L838: `subgrid_river_source` (input)
- L845: `use_spatially_variable_roughness` (select)

### Context: TAB 11: FORCING START

- L868: `rainfall_kind` (select)
- L879: `rainfall_uniform_mm_hr` (input)
- L886: `rainfall_clip_to_model_time` (select)
- L897: `waterlevel_source_kind` (select)
- L911: `waterlevel_clip_to_model_time` (select)
- L922: `discharge_source_kind` (select)
- L935: `discharge_clip_to_model_time` (select)
- L945: `discharge_points_csv_path` (input)
- L951: `discharge_points_x_column` (input)
- L957: `discharge_points_y_column` (input)
- L963: `discharge_points_name_column` (input)
- L969: `discharge_timeseries_csv_path` (input)
- L975: `discharge_time_column` (input)
- L981: `discharge_value_columns` (textarea)
- L987: `discharge_time_format` (input)
- L993: `discharge_units` (input)
- L999: `meteo_update_interval_s` (input)
- L1005: `wind_path` (input)
- L1011: `pressure_path` (input)
- L1017: `wind_source` (input)
- L1023: `pressure_source` (input)

### Context: TAB 12: INFILTRATION START

- L1041: `infiltration_mode` (select)
- L1052: `qinf_mm_hr` (input)
- L1053: `qinf_zmin_m` (input)
- L1054: `scs_initial_abstraction_factor` (input)
- L1055: `infiltration_path` (input)
- L1056: `curve_number_path` (input)
- L1057: `hsg_path` (input)
- L1058: `soil_storage_path` (input)
- L1060: `qinf_path` (input)
- L1061: `smax_path` (input)
- L1062: `seff_path` (input)
- L1063: `ks_path` (input)
- L1065: `sigma_path` (input)
- L1066: `psi_path` (input)
- L1068: `f0_path` (input)
- L1069: `fc_path` (input)
- L1070: `kd_path` (input)
- L1072: `vol_path` (input)

### Context: TAB 13: OUTPUT START

- L1085: `output_format` (input)
- L1086: `dtout_s` (input)
- L1087: `dthisout_s` (input)
- L1088: `dtmaxout_s` (input)
- L1089: `dtrstout_s` (input)
- L1090: `store_wet_duration` (select)
- L1091: `store_velocity` (select)
- L1092: `store_max_velocity` (select)
- L1093: `store_max_flux` (select)
- L1094: `store_cumulative_precip` (select)
- L1095: `store_hmax_subgrid` (select)

### Context: TAB 14: ADVANCED START

- L1110: `advanced_config` (textarea)

### Context: TAB 15: POSTPROCESS START

- L1160: `postprocess_create_summary_txt` (select)
- L1161: `postprocess_create_summary_json` (select)
- L1162: `postprocess_list_output_variables` (select)
- L1163: `postprocess_make_quicklook_plots` (select)
- L1164: `postprocess_plot_max_water_level` (select)
- L1165: `postprocess_plot_max_flood_depth` (select)
- L1166: `postprocess_plot_final_water_level` (select)
- L1167: `postprocess_plot_obs_hydrographs` (select)
- L1168: `postprocess_use_basemap` (select)
- L1169: `postprocess_basemap_source` (input)
- L1170: `postprocess_basemap_zoomlevel` (input)
- L1171: `postprocess_use_rotated_map_plots` (select)
- L1172: `postprocess_use_basemap_on_result_maps` (select)
- L1173: `postprocess_result_map_alpha` (input)
- L1174: `postprocess_result_map_background_fade_alpha` (input)
- L1175: `postprocess_result_map_show_model_features` (select)
- L1176: `postprocess_result_map_show_obs` (select)
- L1177: `postprocess_result_map_show_boundaries` (select)
- L1178: `postprocess_result_map_show_dep_layer` (select)
- L1179: `postprocess_result_map_show_layout_legend` (select)
- L1180: `postprocess_waterlevel_var_candidates` (textarea)
- L1181: `postprocess_bedlevel_var_candidates` (textarea)
- L1182: `postprocess_depth_var_candidates` (textarea)
- L1183: `postprocess_max_waterlevel_var_candidates` (textarea)
- L1184: `postprocess_max_depth_var_candidates` (textarea)
- L1185: `postprocess_matplotlib_backend` (input)
- L1186: `postprocess_max_plot_cells` (input)

### Context: TAB 16: SAFETY DEBUG START

- L1199: `print_config_summary` (select)
- L1200: `validate_paths_before_submit` (select)
- L1201: `stop_if_required_path_missing` (select)
- L1202: `save_data_inventory` (select)
- L1203: `save_config_json` (select)
- L1204: `save_job_ids` (select)
- L1205: `print_optional_path_warnings` (select)
- L1206: `warn_unknown_config_keys` (select)
- L1207: `strict_schema_validation` (select)
- L1208: `warn_schema_type_mismatches` (select)

### Context: TAB 17: BACKEND PATHS START

- L1229: `prefer_pipeline_bundle_runtime_paths` (select)
- L1239: `anaconda_module` (input)
- L1245: `apptainer_module` (input)
- L1251: `preprocess_stage_script` (input)
- L1257: `postprocess_stage_script` (input)
- L1263: `conda_env_path` (input)
- L1269: `conda_python` (input)
- L1275: `sfincs_container_path` (input)
- L1282: `preprocess_enable_hydromt_file_logging` (select)
- L1293: `(unnamed)` (select, disabled)

### Context: CHECK ALL START

- L1313: `check-button-2` (button, type=button)

### Context: SUBMIT START

- L1350: `Run backend preflight` (button, type=button, pipeline_action=preflight)
- L1356: `Build Slurm scripts` (button, type=button, pipeline_action=build_scripts, disabled)
- L1364: `Submit Slurm chain` (button, type=button, pipeline_action=submit, disabled)

## 4. Select dropdown options

### `overwrite_existing_run`
- `false` — false
- `true` — true

### `allow_writes_inside_proj`
- `true` — true
- `false` — false

### `allow_missing_model_inputs`
- `false` — false
- `true` — true

### `run_preprocessing_job`
- `true` — true
- `false` — false

### `run_sfincs_job`
- `true` — true
- `false` — false

### `run_postprocessing_job`
- `true` — true
- `false` — false

### `submit_with_dependencies`
- `true` — true
- `false` — false

### `dependency_type`
- `` — afterok

### `bash_strict_mode`
- `true` — true
- `false` — false

### `sfincs_use_openmp_threads`
- `true` — true
- `false` — false

### `region_mode`
- `` — geom
- `` — bbox

### `require_at_least_one_forcing`
- `true` — true
- `false` — false

### `thin_dam_source_kind`
- `` — none
- `` — geodataframe
- `` — native_sfincs

### `weir_source_kind`
- `` — none
- `` — geodataframe
- `` — native_sfincs

### `drainage_structure_source_kind`
- `` — none
- `` — geodataframe
- `` — native_sfincs

### `culvert_source_kind`
- `` — none
- `` — geodataframe
- `` — native_sfincs

### `grid_rotated`
- `true` — true
- `false` — false

### `use_rainfall`
- `true` — true
- `false` — false

### `use_waterlevel_boundary`
- `true` — true
- `false` — false

### `use_discharge_boundary`
- `true` — true
- `false` — false

### `use_infiltration`
- `true` — true
- `false` — false

### `use_wind`
- `false` — false
- `true` — true

### `use_pressure`
- `false` — false
- `true` — true

### `use_structures`
- `true` — true
- `false` — false

### `use_obs_points`
- `true` — true
- `false` — false

### `use_obs_lines`
- `true` — true
- `false` — false

### `reset_waterlevel_boundary`
- `true` — true
- `false` — false

### `reset_outflow_boundary`
- `true` — true
- `false` — false

### `use_landcover_roughness_if_available`
- `true` — true
- `false` — false

### `use_subgrid`
- `true` — true
- `false` — false

### `subgrid_source_kind`
- `` — hydromt_generate
- `` — premade_sbgfile
- `` — none

### `subgrid_write_dep_tif`
- `true` — true
- `false` — false

### `subgrid_write_man_tif`
- `true` — true
- `false` — false

### `subgrid_use_rivers`
- `false` — false
- `true` — true

### `use_spatially_variable_roughness`
- `true` — true
- `false` — false

### `rainfall_kind`
- `` — spatial
- `` — uniform
- `` — event_catalog_aorc

### `rainfall_clip_to_model_time`
- `true` — true
- `false` — false

### `waterlevel_source_kind`
- `` — geodataset
- `` — csv
- `` — cora
- `` — event_catalog_csv
- `` — native_sfincs

### `waterlevel_clip_to_model_time`
- `true` — true
- `false` — false

### `discharge_source_kind`
- `` — geodataset
- `` — csv
- `` — event_catalog_csv
- `` — native_sfincs

### `discharge_clip_to_model_time`
- `true` — true
- `false` — false

### `infiltration_mode`
- `` — none
- `` — constant
- `` — spatial_constant
- `` — curve_number
- `` — curve_number_with_ks
- `` — native_sfincs

### `store_wet_duration`
- `false` — false
- `true` — true

### `store_velocity`
- `false` — false
- `true` — true

### `store_max_velocity`
- `true` — true
- `false` — false

### `store_max_flux`
- `false` — false
- `true` — true

### `store_cumulative_precip`
- `true` — true
- `false` — false

### `store_hmax_subgrid`
- `true` — true
- `false` — false

### `postprocess_create_summary_txt`
- `true` — true
- `false` — false

### `postprocess_create_summary_json`
- `true` — true
- `false` — false

### `postprocess_list_output_variables`
- `true` — true
- `false` — false

### `postprocess_make_quicklook_plots`
- `true` — true
- `false` — false

### `postprocess_plot_max_water_level`
- `true` — true
- `false` — false

### `postprocess_plot_max_flood_depth`
- `true` — true
- `false` — false

### `postprocess_plot_final_water_level`
- `true` — true
- `false` — false

### `postprocess_plot_obs_hydrographs`
- `true` — true
- `false` — false

### `postprocess_use_basemap`
- `true` — true
- `false` — false

### `postprocess_use_rotated_map_plots`
- `true` — true
- `false` — false

### `postprocess_use_basemap_on_result_maps`
- `true` — true
- `false` — false

### `postprocess_result_map_show_model_features`
- `false` — false
- `true` — true

### `postprocess_result_map_show_obs`
- `false` — false
- `true` — true

### `postprocess_result_map_show_boundaries`
- `false` — false
- `true` — true

### `postprocess_result_map_show_dep_layer`
- `false` — false
- `true` — true

### `postprocess_result_map_show_layout_legend`
- `false` — false
- `true` — true

### `print_config_summary`
- `true` — true
- `false` — false

### `validate_paths_before_submit`
- `true` — true
- `false` — false

### `stop_if_required_path_missing`
- `true` — true
- `false` — false

### `save_data_inventory`
- `true` — true
- `false` — false

### `save_config_json`
- `true` — true
- `false` — false

### `save_job_ids`
- `true` — true
- `false` — false

### `print_optional_path_warnings`
- `true` — true
- `false` — false

### `warn_unknown_config_keys`
- `true` — true
- `false` — false

### `strict_schema_validation`
- `false` — false
- `true` — true

### `warn_schema_type_mismatches`
- `true` — true
- `false` — false

### `prefer_pipeline_bundle_runtime_paths`
- `true` — true
- `false` — false

### `preprocess_enable_hydromt_file_logging`
- `false` — false
- `true` — true

### `select_at_char_74560`
- `` — backend hook needed

## 5. Important guide term coverage

- YES: `Save Progress`
- YES: `Load Config`
- NO: `Run page checks`
- YES: `Run backend preflight`
- YES: `Build Slurm scripts`
- YES: `Submit Slurm chain`
- YES: `Browse`
- YES: `New run`
- YES: `wipe page`
- YES: `runtime-window review`
- YES: `preprocess_mode`
- YES: `pipeline_mode`
- YES: `use_sfincs_file_overrides`
- YES: `data_catalogs`
- YES: `run_name`
- YES: `output_root`
- YES: `project_root`
- YES: `conda_python`
- YES: `sfincs_container_path`
- YES: `overwrite_existing_run`
- YES: `allow_writes_inside_proj`
- NO: `preprocess_enable_hydromt_file_logging`

## 6. Suggested next use

Use this audit to fill Manual guide panels one at a time.
Start with panels whose real controls are most numerous or safety-critical.
