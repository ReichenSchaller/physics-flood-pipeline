# Manual Notes and Behavior Audit

Generated: 2026-06-02T15:05:44
Manual file: `/proj/zefflab/projects/Flooding/pipeline/web_launcher/manual.html`
Guide file: `/proj/zefflab/projects/Flooding/pipeline/web_launcher/guide.html`

## 1. External scripts used by manual.html

- `static/launcher_defaults.js`
- `static/config_path_browse_buttons.js`
- `static/path_browser.js`
- `static/pipeline_actions.js`
- `static/page_reset.js`

## 2. Browse settings

- Found `CONFIG_PATH_BROWSE_SETTINGS`: **True**
- Section numbers: `['0', '4', '5', '6', '10', '11', '12', '17']`
- Special path keys count: **43**

- `project_root`
- `output_root`
- `data_catalogs`
- `region_path`
- `dem_paths`
- `bathy_paths`
- `landcover_path`
- `landcover_reclass_table`
- `rainfall_path`
- `waterlevel_path`
- `streamflow_site_info_path`
- `streamflow_data_path`
- `hydrography_path`
- `obs_points_path`
- `obs_lines_path`
- `thin_dam_path`
- `weir_path`
- `drainage_structure_path`
- `culvert_path`
- `outflow_boundary_polygon_path`
- `subgrid_native_file_path`
- `subgrid_river_path`
- `discharge_points_csv_path`
- `discharge_timeseries_csv_path`
- `wind_path`
- `pressure_path`
- `infiltration_path`
- `curve_number_path`
- `hsg_path`
- `soil_storage_path`
- `qinf_path`
- `smax_path`
- `seff_path`
- `ks_path`
- `sigma_path`
- `psi_path`
- `f0_path`
- `fc_path`
- `kd_path`
- `vol_path`
- `conda_env_path`
- `conda_python`
- `sfincs_container_path`

## 3. JavaScript function names in manual.html

- `applyManualFixedConfig`
- `asList`
- `getConfig`
- `hasAnyValue`
- `isBlank`
- `loadConfigFromFile`
- `makeCheck`
- `manualReviewEsc`
- `outputRoot`
- `parseManualDate`
- `parseValue`
- `plannedRunRoot`
- `renderRuntimeWindowReview`
- `runChecks`
- `runRuntimeWindowReviewCheck`
- `saveConfig`
- `setFieldValue`
- `showTab`
- `stringifyForField`
- `updatePreview`

## 4. Field rows with existing Manual notes

### 0 Run identity → `run_identity`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 534 | event_name | `event_name` | harvey_2017 |  | Convenience label. Used by this page to help name runs, but it is also saved normally. |
| 535 | run_series | `run_series` | manual_001 |  | Convenience label for repeat experiments. |
| 536 | run_name | `run_name` | harris_harvey_2017_manual_001 |  | Only letters, numbers, underscores, dashes, and periods. This becomes the run folder name. |
| 537 | project_root | `project_root` | /proj/zefflab/projects/Flooding/pipeline |  | Backend pipeline bundle root. |
| 538 | output_root | `output_root` | /proj/zefflab/projects/Flooding/sfincs_runs |  | Run folders will be created under this path by the backend. |
| 539 | planned run root | `` |  |  | Preview only. This is computed as output_root / run_name. |
| 540 | overwrite_existing_run | `overwrite_existing_run` | false | false, true | Keep false unless you are deliberately replacing a run folder. |
| 541 | allow_writes_inside_proj | `allow_writes_inside_proj` | true | true, false | Shared project runs use /proj. Personal scratch runs may keep this false. |
| 542 | allow_missing_model_inputs | `allow_missing_model_inputs` | false | false, true | Real runs should normally keep this false. Skeleton tests may set it true. |
| 543 | run_description | `run_description` | Manual launcher SFINCS pipeline run. |  | Short human description. |
| 544 | run_tags | `run_tags` | ["manual", "sfincs", "harris_county"] |  | JSON list of tags. |

### 1 Pipeline → `pipeline`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 557 | run_preprocessing_job | `run_preprocessing_job` | true | true, false | Stage 1. |
| 558 | run_sfincs_job | `run_sfincs_job` | true | true, false | Stage 2. |
| 559 | run_postprocessing_job | `run_postprocessing_job` | true | true, false | Stage 3. |
| 560 | submit_with_dependencies | `submit_with_dependencies` | true | true, false | Normally true so later jobs wait for earlier jobs. |
| 561 | dependency_type | `dependency_type` | afterok | afterok | Currently the supported dependency style. |

### 2 Slurm general → `slurm_general`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 574 | slurm_account | `slurm_account` |  |  | Leave blank unless the lab/cluster requires an account. |
| 575 | slurm_partition | `slurm_partition` |  |  | Leave blank for default partition. |
| 576 | slurm_qos | `slurm_qos` |  |  | Leave blank unless needed. |
| 577 | slurm_email | `slurm_email` |  |  | Optional email for job notifications. |
| 578 | slurm_mail_type | `slurm_mail_type` | END,FAIL |  | Used only when slurm_email is set. |
| 579 | slurm_extra_directives | `slurm_extra_directives` | [] |  | JSON list of extra #SBATCH lines. Usually empty. |
| 580 | bash_strict_mode | `bash_strict_mode` | true | true, false | Keep true unless debugging unusual shell behavior. |

### 3 Stage resources → `stage_resources`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 593 | preprocess_time | `preprocess_time` | 01:00:00 |  | Wall time for preprocessing. |
| 594 | preprocess_nodes | `preprocess_nodes` | 1 |  | Usually 1. |
| 595 | preprocess_ntasks | `preprocess_ntasks` | 1 |  | Usually 1. |
| 596 | preprocess_cpus_per_task | `preprocess_cpus_per_task` | 4 |  | More helpful for heavier preprocessing. |
| 597 | preprocess_mem | `preprocess_mem` | 16G |  | Memory request. |
| 598 | sfincs_time | `sfincs_time` | 04:00:00 |  | Wall time for solver. |
| 599 | sfincs_nodes | `sfincs_nodes` | 1 |  | Usually 1. |
| 600 | sfincs_ntasks | `sfincs_ntasks` | 1 |  | Usually 1. |
| 601 | sfincs_cpus_per_task | `sfincs_cpus_per_task` | 8 |  | OpenMP threads for SFINCS. |
| 602 | sfincs_mem | `sfincs_mem` | 32G |  | Memory request. |
| 603 | postprocess_time | `postprocess_time` | 01:00:00 |  | Wall time for postprocessing. |
| 604 | postprocess_nodes | `postprocess_nodes` | 1 |  | Usually 1. |
| 605 | postprocess_ntasks | `postprocess_ntasks` | 1 |  | Usually 1. |
| 606 | postprocess_cpus_per_task | `postprocess_cpus_per_task` | 2 |  | Can increase for heavy plotting. |
| 607 | postprocess_mem | `postprocess_mem` | 24G |  | Memory request. |
| 608 | sfincs_use_openmp_threads | `sfincs_use_openmp_threads` | true | true, false | Usually true. |
| 609 | sfincs_omp_proc_bind | `sfincs_omp_proc_bind` | true |  | OpenMP binding setting. |
| 610 | sfincs_omp_places | `sfincs_omp_places` | cores |  | OpenMP placement setting. |

### 4 Data catalogs → `data_catalogs`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 623 | data_catalogs | `data_catalogs` | ["artifact_data"] |  | JSON list of catalog paths or HydroMT catalog names. Use full catalog paths when needed. |

### 5 Required inputs → `required_inputs`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 636 | region_mode | `region_mode` | geom | geom, bbox | Region geometry or bounding box. |
| 637 | region_path | `region_path` |  |  |  |
| 639 | dem_paths | `dem_paths` | [] |  | JSON list of DEM paths. |
| 640 | hydromt_dem_sources | `hydromt_dem_sources` | [ {"elevation": "merit_hydro", "zmin": 0.001} ] |  | HydroMT DEM source definitions. |
| 643 | require_at_least_one_forcing | `require_at_least_one_forcing` | true | true, false | Safety: at least one forcing should be enabled. |

### 6 Optional inputs → `optional_inputs`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 656 | bathy_paths | `bathy_paths` | [] |  | JSON list of bathymetry paths. |
| 657 | hydromt_bathy_sources | `hydromt_bathy_sources` | [ {"elevation": "gebco"} ] |  | HydroMT bathy source definitions. |
| 660 | landcover_path | `landcover_path` |  |  | Optional landcover file path. |
| 661 | landcover_source | `landcover_source` | vito_2015 |  | HydroMT source name. |
| 662 | landcover_reclass_table | `landcover_reclass_table` |  |  | [] rainfall_path |
| 665 | rainfall_source | `rainfall_source` | era5_hourly |  | HydroMT rainfall source. |
| 666 | rainfall_variable | `rainfall_variable` | precip |  | Rainfall variable name. |
| 667 | waterlevel_path | `waterlevel_path` |  |  | Optional direct water-level path. |
| 668 | waterlevel_source | `waterlevel_source` | gtsmv3_eu_era5 |  | HydroMT water-level source. |
| 669 | waterlevel_variable | `waterlevel_variable` | zeta |  | Water-level variable/column. |
| 670 | discharge_source | `discharge_source` | discharge_forcing |  | HydroMT discharge source name or configured catalog source. |
| 671 | streamflow_site_info_path | `streamflow_site_info_path` |  |  | Optional streamflow metadata path. |
| 672 | streamflow_data_path | `streamflow_data_path` |  |  | Optional streamflow data path. |
| 673 | hydrography_path | `hydrography_path` |  |  | Optional hydrography path. |
| 674 | hydrography_source | `hydrography_source` | nhdplus_or_enhdplus |  | Hydrography source name. |
| 675 | obs_points_path | `obs_points_path` |  |  | thin_dam_source_kind |
| 678 | thin_dam_path | `thin_dam_path` |  |  | Optional thin-dam path. |
| 679 | weir_source_kind | `weir_source_kind` | none | none, geodataframe, native_sfincs | Weir source style. |
| 680 | weir_path | `weir_path` |  |  | Optional weir path. |
| 681 | drainage_structure_source_kind | `drainage_structure_source_kind` | none | none, geodataframe, native_sfincs | Drainage structure source style. |
| 682 | drainage_structure_path | `drainage_structure_path` |  |  | Optional drainage structure path. |
| 683 | culvert_source_kind | `culvert_source_kind` | none | none, geodataframe, native_sfincs | Culvert source style. |
| 684 | culvert_path | `culvert_path` |  |  | Optional culvert path. |

### 7 Model settings → `model_settings`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 697 | grid_resolution_m | `grid_resolution_m` | 50 |  | General target resolution. |
| 698 | grid_dx_m | `grid_dx_m` | 100 |  | Grid dx. |
| 699 | grid_dy_m | `grid_dy_m` | 100 |  | Grid dy. |
| 700 | grid_crs | `grid_crs` | utm |  | CRS label for HydroMT build workflows. |
| 701 | grid_rotated | `grid_rotated` | true | true, false | Whether grid is rotated. |
| 702 | grid_rotation_deg | `grid_rotation_deg` |  |  | Blank saves as null. |
| 703 | tref | `tref` | 2017-08-22 00:00:00 |  | Reference time. |
| 704 | tstart | `tstart` | 2017-08-22 00:00:00 |  | Model start. |
| 705 | tstop | `tstop` | 2017-09-17 01:00:00 |  | Model stop. |
| 706 | use_rainfall | `use_rainfall` | true | true, false | Rainfall forcing. |
| 707 | use_waterlevel_boundary | `use_waterlevel_boundary` | true | true, false | Boundary water-level forcing. |
| 708 | use_discharge_boundary | `use_discharge_boundary` | true | true, false | Discharge/source forcing. |
| 709 | use_infiltration | `use_infiltration` | true | true, false | Infiltration/SCS. |
| 710 | use_wind | `use_wind` | false | false, true | Wind forcing. |
| 711 | use_pressure | `use_pressure` | false | false, true | Pressure forcing. |
| 712 | use_structures | `use_structures` | true | true, false | Structures such as thin dams if configured. |
| 713 | use_obs_points | `use_obs_points` | true | true, false | Observation points. |
| 714 | use_obs_lines | `use_obs_lines` | true | true, false | Observation lines/cross sections. |

### 8 Elevation/mask → `elevation_mask`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 727 | dem_zmin | `dem_zmin` | 0.001 |  | Minimum DEM threshold. |
| 728 | elevation_buffer_cells | `elevation_buffer_cells` | 1 |  | Elevation buffer cells. |
| 729 | active_zmin | `active_zmin` | -5.0 |  | Active mask threshold. |
| 730 | mask_fill_area_km2 | `mask_fill_area_km2` | 10.0 |  | Fill small areas. |
| 731 | mask_drop_area_km2 | `mask_drop_area_km2` | 0.0 |  | Drop small areas. |
| 732 | waterlevel_boundary_zmax | `waterlevel_boundary_zmax` | -5.0 |  | Water-level boundary z threshold. |
| 733 | reset_waterlevel_boundary | `reset_waterlevel_boundary` | true | true, false | Reset/create water-level boundary. |
| 734 | outflow_boundary_polygon_path | `outflow_boundary_polygon_path` |  |  | Optional outflow boundary polygon. |
| 735 | reset_outflow_boundary | `reset_outflow_boundary` | true | true, false | Reset/create outflow boundary. |

### 9 Roughness → `roughness`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 748 | manning_uniform | `manning_uniform` | 0.04 |  | Uniform fallback Manning n. |
| 749 | manning_land | `manning_land` | 0.04 |  | Land Manning n. |
| 750 | manning_sea | `manning_sea` | 0.02 |  | Sea Manning n. |
| 751 | roughness_land_level_m | `roughness_land_level_m` | 0.0 |  | Land/sea threshold. |
| 752 | use_landcover_roughness_if_available | `use_landcover_roughness_if_available` | true | true, false | Use landcover mapping when available. |

### 10 Subgrid → `subgrid`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 770 | use_subgrid | `use_subgrid` | true | true, false | Master toggle for subgrid use. |
| 781 | subgrid_source_kind | `subgrid_source_kind` | hydromt_generate | hydromt_generate, premade_sbgfile, none | Choose whether preprocessing should generate subgrid data or use a pre-made SFINCS subgrid file. Backend support may need to be added for this new key. |
| 795 | subgrid_nr_pixels | `subgrid_nr_pixels` | 6 |  | Subgrid pixels per model cell. Higher values can improve detail but increase preprocessing cost and storage. |
| 801 | subgrid_write_dep_tif | `subgrid_write_dep_tif` | true | true, false | Write depth/elevation diagnostic GeoTIFF during subgrid creation. |
| 812 | subgrid_write_man_tif | `subgrid_write_man_tif` | true | true, false | Write Manning roughness diagnostic GeoTIFF during subgrid creation. |
| 823 | subgrid_use_rivers | `subgrid_use_rivers` | false | false, true | Use river network information in subgrid generation when supported by the preprocessing path. |
| 836 | subgrid_river_source | `subgrid_river_source` | river_network_for_subgrid |  | River source name in a HydroMT catalog. |
| 842 | use_spatially_variable_roughness | `use_spatially_variable_roughness` | true | true, false | Related roughness/subgrid behavior. Keep aligned with the roughness settings tab. |

### 11 Forcing → `forcing`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 865 | rainfall_kind | `rainfall_kind` | spatial | spatial, uniform, event_catalog_aorc | spatial = gridded/catalog rainfall; uniform = one constant rainfall rate; event_catalog_aorc = reduced-event AORC rainfall path used by hybrid workflows. |
| 877 | rainfall_uniform_mm_hr | `rainfall_uniform_mm_hr` |  |  | Used only for uniform rainfall. Blank saves as null. |
| 883 | rainfall_clip_to_model_time | `rainfall_clip_to_model_time` | true | true, false | Clip rainfall forcing to the model time window. |
| 894 | waterlevel_source_kind | `waterlevel_source_kind` | geodataset | geodataset, csv, cora, event_catalog_csv, native_sfincs | Water-level boundary source style. Native SFINCS is more naturally handled in Override Mode. |
| 908 | waterlevel_clip_to_model_time | `waterlevel_clip_to_model_time` | true | true, false | Clip water-level forcing to the model time window. |
| 919 | discharge_source_kind | `discharge_source_kind` | geodataset | geodataset, csv, event_catalog_csv, native_sfincs | Discharge/source forcing style. Native SFINCS is more naturally handled in Override Mode. |
| 932 | discharge_clip_to_model_time | `discharge_clip_to_model_time` | true | true, false | Clip discharge forcing to the model time window. |
| 943 | discharge_points_csv_path | `discharge_points_csv_path` |  |  | Optional direct discharge source-point CSV. |
| 949 | discharge_points_x_column | `discharge_points_x_column` | x |  | X-coordinate column for discharge points. |
| 955 | discharge_points_y_column | `discharge_points_y_column` | y |  | Y-coordinate column for discharge points. |
| 961 | discharge_points_name_column | `discharge_points_name_column` | name |  | Name/ID column for discharge points. |
| 967 | discharge_timeseries_csv_path | `discharge_timeseries_csv_path` |  |  | Optional direct discharge time-series CSV. |
| 973 | discharge_time_column | `discharge_time_column` | time |  | Time column in the discharge time-series CSV. |
| 979 | discharge_value_columns | `discharge_value_columns` | [] |  | JSON list. Empty means use all non-time columns. |
| 985 | discharge_time_format | `discharge_time_format` | auto |  | Usually auto. |
| 991 | discharge_units | `discharge_units` | m3/s |  | Discharge units. |
| 997 | meteo_update_interval_s | `meteo_update_interval_s` | 1800 |  | Meteorological forcing update interval. |
| 1003 | wind_path | `wind_path` |  |  | Optional wind path. |
| 1009 | pressure_path | `pressure_path` |  |  | Optional pressure path. |
| 1015 | wind_source | `wind_source` | wind_forcing |  | Wind source name. |
| 1021 | pressure_source | `pressure_source` | pressure_forcing |  | Pressure source name. |

### 12 Infiltration → `infiltration`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 1038 | infiltration_mode | `infiltration_mode` | none | none, constant, spatial_constant, curve_number, curve_number_with_ks, native_sfincs | Choose one of the supported/planned infiltration modes. Native SFINCS is usually for override/native-file workflows. |
| 1052 | qinf_mm_hr | `qinf_mm_hr` | 0.0 |  | Constant infiltration if used. |
| 1053 | qinf_zmin_m | `qinf_zmin_m` | 0.0 |  | Threshold if used. |
| 1054 | scs_initial_abstraction_factor | `scs_initial_abstraction_factor` | 0.2 |  | SCS parameter. |
| 1055 | infiltration_path | `infiltration_path` |  |  | Optional HydroMT infiltration source path. |
| 1056 | curve_number_path | `curve_number_path` |  |  | Optional HydroMT/Curve Number source path. |
| 1057 | hsg_path | `hsg_path` |  |  | Optional hydrologic soil group path. |
| 1058 | soil_storage_path | `soil_storage_path` |  |  | Optional soil storage path. |
| 1060 | qinf_path | `qinf_path` |  |  | Manual SFINCS qinf file. Copies to sfincs.qinf and writes qinffile. |
| 1061 | smax_path | `smax_path` |  |  | Manual maximum soil storage file. Copies to sfincs.smax and writes smaxfile. |
| 1062 | seff_path | `seff_path` |  |  | Manual initial/effective soil storage file. Copies to sfincs.seff and writes sefffile. |
| 1063 | ks_path | `ks_path` |  |  | Manual saturated hydraulic conductivity file. Copies to sfincs.ks and writes ksfile. |
| 1065 | sigma_path | `sigma_path` |  |  | Manual Green-Ampt sigma file. Copies to sfincs.sigma and writes sigmafile. |
| 1066 | psi_path | `psi_path` |  |  | Manual Green-Ampt psi file. Copies to sfincs.psi and writes psifile. |
| 1068 | f0_path | `f0_path` |  |  | Manual Horton f0 file. Copies to sfincs.f0 and writes f0file. |
| 1069 | fc_path | `fc_path` |  |  | Manual Horton fc file. Copies to sfincs.fc and writes fcfile. |
| 1070 | kd_path | `kd_path` |  |  | Manual Horton decay coefficient file. Copies to sfincs.kd and writes kdfile. |
| 1072 | vol_path | `vol_path` |  |  | Manual storage volume file. Copies to sfincs.vol and writes volfile. |

### 13 Output → `output`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 1085 | output_format | `output_format` | net |  | Output format. |
| 1086 | dtout_s | `dtout_s` | 3600 |  | Map output interval. |
| 1087 | dthisout_s | `dthisout_s` | 900 |  | History output interval. |
| 1088 | dtmaxout_s | `dtmaxout_s` | 99999.0 |  | Maximum output interval. |
| 1089 | dtrstout_s | `dtrstout_s` | 259200 |  | Restart output interval. |
| 1090 | store_wet_duration | `store_wet_duration` | false | false, true | Save wet duration. |
| 1091 | store_velocity | `store_velocity` | false | false, true | Save velocity. |
| 1092 | store_max_velocity | `store_max_velocity` | true | true, false | Save max velocity. |
| 1093 | store_max_flux | `store_max_flux` | false | false, true | Save max flux. |
| 1094 | store_cumulative_precip | `store_cumulative_precip` | true | true, false | Save cumulative precipitation. |
| 1095 | store_hmax_subgrid | `store_hmax_subgrid` | true | true, false | Save hmax subgrid. |

### 14 Advanced → `advanced`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 1108 | advanced_config | `advanced_config` | { "mmax": 997, "nmax": 1012, "dx": 100, "dy": 100, "x0": 211971.0, "y0": 3261293.0, "rotation": 0... |  | Must be valid JSON. These keys are written as advanced SFINCS controls. |

### 15 Postprocess → `postprocess`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 1160 | postprocess_create_summary_txt | `postprocess_create_summary_txt` | true | true, false | Create summary text. |
| 1161 | postprocess_create_summary_json | `postprocess_create_summary_json` | true | true, false | Create summary JSON. |
| 1162 | postprocess_list_output_variables | `postprocess_list_output_variables` | true | true, false | List output variables. |
| 1163 | postprocess_make_quicklook_plots | `postprocess_make_quicklook_plots` | true | true, false | Make quicklook plots. |
| 1164 | postprocess_plot_max_water_level | `postprocess_plot_max_water_level` | true | true, false | Plot max water level. |
| 1165 | postprocess_plot_max_flood_depth | `postprocess_plot_max_flood_depth` | true | true, false | Plot max flood depth. |
| 1166 | postprocess_plot_final_water_level | `postprocess_plot_final_water_level` | true | true, false | Plot final water level. |
| 1167 | postprocess_plot_obs_hydrographs | `postprocess_plot_obs_hydrographs` | true | true, false | Plot observation hydrographs. |
| 1168 | postprocess_use_basemap | `postprocess_use_basemap` | true | true, false | Use basemap for maps. |
| 1169 | postprocess_basemap_source | `postprocess_basemap_source` | sat |  | Basemap source. |
| 1170 | postprocess_basemap_zoomlevel | `postprocess_basemap_zoomlevel` | 14 |  | Can be a number or a string such as auto. |
| 1171 | postprocess_use_rotated_map_plots | `postprocess_use_rotated_map_plots` | true | true, false | Use rotated map plots. |
| 1172 | postprocess_use_basemap_on_result_maps | `postprocess_use_basemap_on_result_maps` | true | true, false | Overlay result maps on basemap. |
| 1173 | postprocess_result_map_alpha | `postprocess_result_map_alpha` | 1.0 |  | Result layer opacity. |
| 1174 | postprocess_result_map_background_fade_alpha | `postprocess_result_map_background_fade_alpha` | 0.35 |  | Basemap fade amount. |
| 1175 | postprocess_result_map_show_model_features | `postprocess_result_map_show_model_features` | false | false, true | Show model features. |
| 1176 | postprocess_result_map_show_obs | `postprocess_result_map_show_obs` | false | false, true | Show observation points. |
| 1177 | postprocess_result_map_show_boundaries | `postprocess_result_map_show_boundaries` | false | false, true | Show boundaries. |
| 1178 | postprocess_result_map_show_dep_layer | `postprocess_result_map_show_dep_layer` | false | false, true | Show bed/elevation layer. |
| 1179 | postprocess_result_map_show_layout_legend | `postprocess_result_map_show_layout_legend` | false | false, true | Show layout legend. |
| 1180 | postprocess_waterlevel_var_candidates | `postprocess_waterlevel_var_candidates` | ["zs", "waterlevel", "water_level"] |  | Candidate variable names. |
| 1181 | postprocess_bedlevel_var_candidates | `postprocess_bedlevel_var_candidates` | ["zb", "bedlevel", "bed_level", "dep"] |  | Candidate variable names. |
| 1182 | postprocess_depth_var_candidates | `postprocess_depth_var_candidates` | ["h", "depth", "flood_depth"] |  | Candidate variable names. |
| 1183 | postprocess_max_waterlevel_var_candidates | `postprocess_max_waterlevel_var_candidates` | ["zsmax", "max_zs", "waterlevel_max"] |  | Candidate variable names. |
| 1184 | postprocess_max_depth_var_candidates | `postprocess_max_depth_var_candidates` | ["hmax", "max_h", "flood_depth_max"] |  | Candidate variable names. |
| 1185 | postprocess_matplotlib_backend | `postprocess_matplotlib_backend` | Agg |  | Non-interactive plotting backend. |
| 1186 | postprocess_max_plot_cells | `postprocess_max_plot_cells` | 2000000 |  | Plot downsampling guard. |

### 16 Safety/debug → `safety_debug`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 1199 | print_config_summary | `print_config_summary` | true | true, false | Print summary in backend logs. |
| 1200 | validate_paths_before_submit | `validate_paths_before_submit` | true | true, false | Safety path validation. |
| 1201 | stop_if_required_path_missing | `stop_if_required_path_missing` | true | true, false | Set false only if you truly want warnings instead of stops. |
| 1202 | save_data_inventory | `save_data_inventory` | true | true, false | Save data inventory. |
| 1203 | save_config_json | `save_config_json` | true | true, false | Backend should write frozen run_config.json. |
| 1204 | save_job_ids | `save_job_ids` | true | true, false | Save Slurm job IDs. |
| 1205 | print_optional_path_warnings | `print_optional_path_warnings` | true | true, false | Print optional path warnings. |
| 1206 | warn_unknown_config_keys | `warn_unknown_config_keys` | true | true, false | Schema hardening warning. |
| 1207 | strict_schema_validation | `strict_schema_validation` | false | false, true | Use true for final strict checking. |
| 1208 | warn_schema_type_mismatches | `warn_schema_type_mismatches` | true | true, false | Schema hardening type warning. |

### 17 Backend paths → `backend_paths`

| Line | Setting | Control key | Default | Options | Existing Manual notes |
|---:|---|---|---|---|---|
| 1226 | prefer_pipeline_bundle_runtime_paths | `prefer_pipeline_bundle_runtime_paths` | true | true, false | Prefer runtime paths inside the shared pipeline bundle when available. |
| 1237 | anaconda_module | `anaconda_module` | anaconda |  | Longleaf module name. |
| 1243 | apptainer_module | `apptainer_module` | apptainer |  | Longleaf module name. |
| 1249 | preprocess_stage_script | `preprocess_stage_script` | /proj/zefflab/projects/Flooding/pipeline/code/preprocess_stage.py |  | Shared pipeline backend script. |
| 1255 | postprocess_stage_script | `postprocess_stage_script` | /proj/zefflab/projects/Flooding/pipeline/code/postprocess_stage.py |  | Shared pipeline backend script. |
| 1261 | conda_env_path | `conda_env_path` | /proj/zefflab/projects/Flooding/pipeline/envs/sfincs |  | Desired shared environment path. Use only after the shared env exists and passes smoke tests. |
| 1267 | conda_python | `conda_python` | /proj/zefflab/projects/Flooding/pipeline/envs/sfincs/bin/python |  | Desired shared Python executable. Current known-good fallback is still under /users/e/p/epsilon/... . |
| 1273 | sfincs_container_path | `sfincs_container_path` | /proj/zefflab/projects/Flooding/pipeline/containers/sfincs-v2.3.0-mt-Faber-Release.sif |  | SFINCS Apptainer image inside the shared pipeline bundle. |
| 1279 | preprocess_enable_hydromt_file_logging | `preprocess_enable_hydromt_file_logging` | false | false, true | Keep false by default; HydroMT file logging is slow. Slurm stdout/stderr logs still capture preprocessing messages. |
| 1290 | preprocess timing report | `` |  | backend hook needed | Timing blocks already exist in preprocessing, but making this configurable from the web page requires a small backend/config hook. Not worth adding as a fake HTML-only setting. |

### Check all → `check_all`

_No table rows extracted._

### Submit → `submit`

_No table rows extracted._

## 5. Buttons by tab

### Check all → `check_all`

| Line | Button text | ID | Pipeline action | Requires preflight | Disabled? | Onclick |
|---:|---|---|---|---|---|---|
| 1313 | Run page checks | `check-button-2` | `` | `` | False | `` |

### Submit → `submit`

| Line | Button text | ID | Pipeline action | Requires preflight | Disabled? | Onclick |
|---:|---|---|---|---|---|---|
| 1350 | Run backend preflight | `` | `preflight` | `` | False | `` |
| 1356 | Build Slurm scripts | `` | `build_scripts` | `true` | True | `` |
| 1364 | Submit Slurm chain | `` | `submit` | `true` | True | `` |

## 6. Behavior / warning / config logic hits

```text
   L0017:       --accent-2: #173f73;
   L0018:       --good: #18794e;
>> L0019:       --warn: #b25e09;
   L0020:       --bad: #b42318;
   L0021:       --radius: 18px;
```

```text
   L0230:     }
   L0231: 
>> L0232:     .tab.check-tab.active { background: var(--warn); border-color: var(--warn); }
   L0233:     .tab.submit-tab.active { background: var(--bad); border-color: var(--bad); }
   L0234: 
```

```text
   L0335: 
   L0336:     .pill.good { color: var(--good); background: #eaf6ef; border-color: #badfca; }
>> L0337:     .pill.warn { color: var(--warn); background: #fff4e5; border-color: #ffd6a7; }
   L0338:     .pill.bad { color: var(--bad); background: #ffeceb; border-color: #ffbdb8; }
   L0339: 
```

```text
   L0374:     }
   L0375: 
>> L0376:     .callout.warn {
   L0377:       border-left-color: var(--warn);
   L0378:       background: #fff7ed;
```

```text
   L0375: 
   L0376:     .callout.warn {
>> L0377:       border-left-color: var(--warn);
   L0378:       background: #fff7ed;
   L0379:       color: #7a3e00;
```

```text
   L0403: 
   L0404:     .check-item.good { border-color: #badfca; background: #f0fbf4; }
>> L0405:     .check-item.warn { border-color: #ffd6a7; background: #fff8ec; }
   L0406:     .check-item.bad { border-color: #ffbdb8; background: #fff0ef; }
   L0407:     .check-status { font-weight: 900; }
```

```text
   L0407:     .check-status { font-weight: 900; }
   L0408:     .check-item.good .check-status { color: var(--good); }
>> L0409:     .check-item.warn .check-status { color: var(--warn); }
   L0410:     .check-item.bad .check-status { color: var(--bad); }
   L0411: 
```

```text
   L0464: </head>
   L0465: <body>
>> L0466:   <input type="hidden" data-key="pipeline_mode" data-type="string" value="preflight_only">
   L0467:   <input type="hidden" data-key="preprocess_mode" data-type="string" value="hydromt_build">
   L0468:   <input type="hidden" data-key="data_root" data-type="string" value="/proj/zefflab/projects/Flooding/Data/harris_county">
```

```text
   L0465: <body>
   L0466:   <input type="hidden" data-key="pipeline_mode" data-type="string" value="preflight_only">
>> L0467:   <input type="hidden" data-key="preprocess_mode" data-type="string" value="hydromt_build">
   L0468:   <input type="hidden" data-key="data_root" data-type="string" value="/proj/zefflab/projects/Flooding/Data/harris_county">
   L0469:   <input type="hidden" data-key="sfincs_container" data-type="string" value="/proj/zefflab/projects/Flooding/pipeline/containers/sfincs-v2.3.0-mt-Faber-Release.sif">
```

```text
   L0492:           New run / wipe page
   L0493:         </button>
>> L0494:         <button class="primary" type="button" id="save-config-button">Save progress</button>
   L0495:         <label class="file-label" for="load-config-input">Load config</label>
   L0496:         <input id="load-config-input" type="file" accept=".json,application/json" />
```

```text
   L0493:         </button>
   L0494:         <button class="primary" type="button" id="save-config-button">Save progress</button>
>> L0495:         <label class="file-label" for="load-config-input">Load config</label>
   L0496:         <input id="load-config-input" type="file" accept=".json,application/json" />
   L0497:       </div>
```

```text
   L0494:         <button class="primary" type="button" id="save-config-button">Save progress</button>
   L0495:         <label class="file-label" for="load-config-input">Load config</label>
>> L0496:         <input id="load-config-input" type="file" accept=".json,application/json" />
   L0497:       </div>
   L0498:     </div>
```

```text
   L0538:               <tr><td>output_root</td><td><input data-key="output_root" data-type="string" value="/proj/zefflab/projects/Flooding/sfincs_runs"></td><td>Run folders will be created under this path by the backend.</td></tr>
   L0539:               <tr><td>planned run root</td><td><div id="run-root-preview" class="path-preview"></div></td><td>Preview only. This is computed as output_root / run_name.</td></tr>
>> L0540:               <tr><td>overwrite_existing_run</td><td><select data-key="overwrite_existing_run" data-type="bool"><option value="false" selected>false</option><option value="true">true</option></select></td><td>Keep false unless you are deliberately replacing a run folder.</td></tr>
   L0541:               <tr><td>allow_writes_inside_proj</td><td><select data-key="allow_writes_inside_proj" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Shared project runs use /proj. Personal scratch runs may keep this false.</td></tr>
   L0542:               <tr><td>allow_missing_model_inputs</td><td><select data-key="allow_missing_model_inputs" data-type="bool"><option value="false" selected>false</option><option value="true">true</option></select></td><td>Real runs should normally keep this false. Skeleton tests may set it true.</td></tr>
```

```text
   L0539:               <tr><td>planned run root</td><td><div id="run-root-preview" class="path-preview"></div></td><td>Preview only. This is computed as output_root / run_name.</td></tr>
   L0540:               <tr><td>overwrite_existing_run</td><td><select data-key="overwrite_existing_run" data-type="bool"><option value="false" selected>false</option><option value="true">true</option></select></td><td>Keep false unless you are deliberately replacing a run folder.</td></tr>
>> L0541:               <tr><td>allow_writes_inside_proj</td><td><select data-key="allow_writes_inside_proj" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Shared project runs use /proj. Personal scratch runs may keep this false.</td></tr>
   L0542:               <tr><td>allow_missing_model_inputs</td><td><select data-key="allow_missing_model_inputs" data-type="bool"><option value="false" selected>false</option><option value="true">true</option></select></td><td>Real runs should normally keep this false. Skeleton tests may set it true.</td></tr>
   L0543:               <tr><td>run_description</td><td><input data-key="run_description" data-type="string" value="Manual launcher SFINCS pipeline run."></td><td>Short human description.</td></tr>
```

```text
   L0540:               <tr><td>overwrite_existing_run</td><td><select data-key="overwrite_existing_run" data-type="bool"><option value="false" selected>false</option><option value="true">true</option></select></td><td>Keep false unless you are deliberately replacing a run folder.</td></tr>
   L0541:               <tr><td>allow_writes_inside_proj</td><td><select data-key="allow_writes_inside_proj" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Shared project runs use /proj. Personal scratch runs may keep this false.</td></tr>
>> L0542:               <tr><td>allow_missing_model_inputs</td><td><select data-key="allow_missing_model_inputs" data-type="bool"><option value="false" selected>false</option><option value="true">true</option></select></td><td>Real runs should normally keep this false. Skeleton tests may set it true.</td></tr>
   L0543:               <tr><td>run_description</td><td><input data-key="run_description" data-type="string" value="Manual launcher SFINCS pipeline run."></td><td>Short human description.</td></tr>
   L0544:               <tr><td>run_tags</td><td><textarea class="short-textarea" data-key="run_tags" data-type="json">["manual", "sfincs", "harris_county"]</textarea></td><td>JSON list of tags.</td></tr>
```

```text
   L0576:               <tr><td>slurm_qos</td><td><input data-key="slurm_qos" data-type="nullable" value=""></td><td>Leave blank unless needed.</td></tr>
   L0577:               <tr><td>slurm_email</td><td><input data-key="slurm_email" data-type="nullable" value=""></td><td>Optional email for job notifications.</td></tr>
>> L0578:               <tr><td>slurm_mail_type</td><td><input data-key="slurm_mail_type" data-type="string" value="END,FAIL"></td><td>Used only when slurm_email is set.</td></tr>
   L0579:               <tr><td>slurm_extra_directives</td><td><textarea class="short-textarea" data-key="slurm_extra_directives" data-type="json">[]</textarea></td><td>JSON list of extra #SBATCH lines. Usually empty.</td></tr>
   L0580:               <tr><td>bash_strict_mode</td><td><select data-key="bash_strict_mode" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Keep true unless debugging unusual shell behavior.</td></tr>
```

```text
   L0621:             <thead><tr><th>Setting</th><th>Value</th><th>Notes</th></tr></thead>
   L0622:             <tbody>
>> L0623:               <tr><td>data_catalogs</td><td><textarea data-key="data_catalogs" data-type="json">["artifact_data"]</textarea></td><td>JSON list of catalog paths or HydroMT catalog names. Use full catalog paths when needed.</td></tr>
   L0624:             </tbody>
   L0625:           </table>
```

```text
   L0675:               <tr><td>obs_points_path</td><td><input data-key="obs_points_path" data-type="nullable" value="">
   L0676:               <tr><td>obs_lines_path</td><td><input data-key="obs_lines_path" data-type="nullable" value="">
>> L0677:               <tr><td>thin_dam_source_kind</td><td><select data-key="thin_dam_source_kind" data-type="string"><option selected>none</option><option>geodataframe</option><option>native_sfincs</option></select></td><td>Thin-dam source style.</td></tr>
   L0678:               <tr><td>thin_dam_path</td><td><input data-key="thin_dam_path" data-type="nullable" value=""></td><td>Optional thin-dam path.</td></tr>
   L0679:               <tr><td>weir_source_kind</td><td><select data-key="weir_source_kind" data-type="string"><option selected>none</option><option>geodataframe</option><option>native_sfincs</option></select></td><td>Weir source style.</td></tr>
```

```text
   L0677:               <tr><td>thin_dam_source_kind</td><td><select data-key="thin_dam_source_kind" data-type="string"><option selected>none</option><option>geodataframe</option><option>native_sfincs</option></select></td><td>Thin-dam source style.</td></tr>
   L0678:               <tr><td>thin_dam_path</td><td><input data-key="thin_dam_path" data-type="nullable" value=""></td><td>Optional thin-dam path.</td></tr>
>> L0679:               <tr><td>weir_source_kind</td><td><select data-key="weir_source_kind" data-type="string"><option selected>none</option><option>geodataframe</option><option>native_sfincs</option></select></td><td>Weir source style.</td></tr>
   L0680:               <tr><td>weir_path</td><td><input data-key="weir_path" data-type="nullable" value=""></td><td>Optional weir path.</td></tr>
   L0681:               <tr><td>drainage_structure_source_kind</td><td><select data-key="drainage_structure_source_kind" data-type="string"><option selected>none</option><option>geodataframe</option><option>native_sfincs</option></select></td><td>Drainage structure source style.</td></tr>
```

```text
   L0679:               <tr><td>weir_source_kind</td><td><select data-key="weir_source_kind" data-type="string"><option selected>none</option><option>geodataframe</option><option>native_sfincs</option></select></td><td>Weir source style.</td></tr>
   L0680:               <tr><td>weir_path</td><td><input data-key="weir_path" data-type="nullable" value=""></td><td>Optional weir path.</td></tr>
>> L0681:               <tr><td>drainage_structure_source_kind</td><td><select data-key="drainage_structure_source_kind" data-type="string"><option selected>none</option><option>geodataframe</option><option>native_sfincs</option></select></td><td>Drainage structure source style.</td></tr>
   L0682:               <tr><td>drainage_structure_path</td><td><input data-key="drainage_structure_path" data-type="nullable" value=""></td><td>Optional drainage structure path.</td></tr>
   L0683:               <tr><td>culvert_source_kind</td><td><select data-key="culvert_source_kind" data-type="string"><option selected>none</option><option>geodataframe</option><option>native_sfincs</option></select></td><td>Culvert source style.</td></tr>
```

```text
   L0681:               <tr><td>drainage_structure_source_kind</td><td><select data-key="drainage_structure_source_kind" data-type="string"><option selected>none</option><option>geodataframe</option><option>native_sfincs</option></select></td><td>Drainage structure source style.</td></tr>
   L0682:               <tr><td>drainage_structure_path</td><td><input data-key="drainage_structure_path" data-type="nullable" value=""></td><td>Optional drainage structure path.</td></tr>
>> L0683:               <tr><td>culvert_source_kind</td><td><select data-key="culvert_source_kind" data-type="string"><option selected>none</option><option>geodataframe</option><option>native_sfincs</option></select></td><td>Culvert source style.</td></tr>
   L0684:               <tr><td>culvert_path</td><td><input data-key="culvert_path" data-type="nullable" value=""></td><td>Optional culvert path.</td></tr>
   L0685:             </tbody>
```

```text
   L0761:           <p class="section-intro">Subgrid controls are important because they affect how fine-scale elevation and roughness are represented inside coarser SFINCS cells. This page supports either generating subgrid data from source inputs or pointing to a pre-made subgrid file.</p>
   L0762: 
>> L0763:           <div class="callout warn">
   L0764:             The pre-made subgrid file option is intentionally separate from full Override Mode. Full Override Mode is for many already-processed SFINCS files; this option is only for using a pre-made subgrid while keeping the rest of the setup manual.
   L0765:           </div>
```

```text
   L0780: 
   L0781:               <tr>
>> L0782:                 <td>subgrid_source_kind</td>
   L0783:                 <td>
   L0784:                   <select data-key="subgrid_source_kind" data-type="string">
```

```text
   L0782:                 <td>subgrid_source_kind</td>
   L0783:                 <td>
>> L0784:                   <select data-key="subgrid_source_kind" data-type="string">
   L0785:                     <option selected>hydromt_generate</option>
   L0786:                     <option>premade_sbgfile</option>
```

```text
   L0784:                   <select data-key="subgrid_source_kind" data-type="string">
   L0785:                     <option selected>hydromt_generate</option>
>> L0786:                     <option>premade_sbgfile</option>
   L0787:                     <option>none</option>
   L0788:                   </select>
```

```text
   L0900:                     <option>cora</option>
   L0901:                     <option>event_catalog_csv</option>
>> L0902:                     <option>native_sfincs</option>
   L0903:                   </select>
   L0904:                 </td>
```

```text
   L0924:                     <option>csv</option>
   L0925:                     <option>event_catalog_csv</option>
>> L0926:                     <option>native_sfincs</option>
   L0927:                   </select>
   L0928:                 </td>
```

```text
   L1045:                     <option>curve_number</option>
   L1046:                     <option>curve_number_with_ks</option>
>> L1047:                     <option>native_sfincs</option>
   L1048:                   </select>
   L1049:                 </td>
```

```text
   L1193:         <div class="panel tab-panel" id="tab-16">
   L1194:           <h2>16. Safety / debug settings</h2>
>> L1195:           <p class="section-intro">This is where failed checks can be understood. Some safety checks can be relaxed deliberately, but the page should make that choice visible.</p>
   L1196:           <table class="config-table">
   L1197:             <thead><tr><th>Setting</th><th>Value</th><th>Notes</th></tr></thead>
```

```text
   L1199:               <tr><td>print_config_summary</td><td><select data-key="print_config_summary" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Print summary in backend logs.</td></tr>
   L1200:               <tr><td>validate_paths_before_submit</td><td><select data-key="validate_paths_before_submit" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Safety path validation.</td></tr>
>> L1201:               <tr><td>stop_if_required_path_missing</td><td><select data-key="stop_if_required_path_missing" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Set false only if you truly want warnings instead of stops.</td></tr>
   L1202:               <tr><td>save_data_inventory</td><td><select data-key="save_data_inventory" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Save data inventory.</td></tr>
   L1203:               <tr><td>save_config_json</td><td><select data-key="save_config_json" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Backend should write frozen run_config.json.</td></tr>
```

```text
   L1203:               <tr><td>save_config_json</td><td><select data-key="save_config_json" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Backend should write frozen run_config.json.</td></tr>
   L1204:               <tr><td>save_job_ids</td><td><select data-key="save_job_ids" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Save Slurm job IDs.</td></tr>
>> L1205:               <tr><td>print_optional_path_warnings</td><td><select data-key="print_optional_path_warnings" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Print optional path warnings.</td></tr>
   L1206:               <tr><td>warn_unknown_config_keys</td><td><select data-key="warn_unknown_config_keys" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Schema hardening warning.</td></tr>
   L1207:               <tr><td>strict_schema_validation</td><td><select data-key="strict_schema_validation" data-type="bool"><option value="false" selected>false</option><option value="true">true</option></select></td><td>Use true for final strict checking.</td></tr>
```

```text
   L1204:               <tr><td>save_job_ids</td><td><select data-key="save_job_ids" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Save Slurm job IDs.</td></tr>
   L1205:               <tr><td>print_optional_path_warnings</td><td><select data-key="print_optional_path_warnings" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Print optional path warnings.</td></tr>
>> L1206:               <tr><td>warn_unknown_config_keys</td><td><select data-key="warn_unknown_config_keys" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Schema hardening warning.</td></tr>
   L1207:               <tr><td>strict_schema_validation</td><td><select data-key="strict_schema_validation" data-type="bool"><option value="false" selected>false</option><option value="true">true</option></select></td><td>Use true for final strict checking.</td></tr>
   L1208:               <tr><td>warn_schema_type_mismatches</td><td><select data-key="warn_schema_type_mismatches" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Schema hardening type warning.</td></tr>
```

```text
   L1206:               <tr><td>warn_unknown_config_keys</td><td><select data-key="warn_unknown_config_keys" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Schema hardening warning.</td></tr>
   L1207:               <tr><td>strict_schema_validation</td><td><select data-key="strict_schema_validation" data-type="bool"><option value="false" selected>false</option><option value="true">true</option></select></td><td>Use true for final strict checking.</td></tr>
>> L1208:               <tr><td>warn_schema_type_mismatches</td><td><select data-key="warn_schema_type_mismatches" data-type="bool"><option value="true" selected>true</option><option value="false">false</option></select></td><td>Schema hardening type warning.</td></tr>
   L1209:             </tbody>
   L1210:           </table>
```

```text
   L1217:           <p class="section-intro">Usually these should remain stable. They define the Python environment, stage scripts, and SFINCS container used by generated Slurm scripts.</p>
   L1218: 
>> L1219:           <div class="callout warn">
   L1220:             The shared-project Python environment path below is the desired multi-user direction. If <span class="mono">/proj/zefflab/projects/Flooding/pipeline/envs/sfincs/bin/python</span> has not been created and tested yet, keep using the known-good personal environment for actual runs.
   L1221:           </div>
```

```text
   L1278: 
   L1279:               <tr>
>> L1280:                 <td>preprocess_enable_hydromt_file_logging</td>
   L1281:                 <td>
   L1282:                   <select data-key="preprocess_enable_hydromt_file_logging" data-type="bool">
```

```text
   L1280:                 <td>preprocess_enable_hydromt_file_logging</td>
   L1281:                 <td>
>> L1282:                   <select data-key="preprocess_enable_hydromt_file_logging" data-type="bool">
   L1283:                     <option value="false" selected>false</option>
   L1284:                     <option value="true">true</option>
```

```text
   L1314:           </div>
   L1315:         
>> L1316:           <div id="runtime-window-review-output"></div>
   L1317:           <div id="checks-output" class="checks-list"></div>
   L1318:         <!-- CHECK ALL END -->
```

```text
   L1327:           </p>
   L1328: 
>> L1329:           <div class="callout warn">
   L1330:             Keep <span class="mono">preprocess_mode = hydromt_build</span> for clean Manual Mode testing.
   L1331:             Use Override Mode for already-native or hybrid reduced-event catalog workflows unless you are intentionally debugging those backend paths from Manual.
```

```text
   L1328: 
   L1329:           <div class="callout warn">
>> L1330:             Keep <span class="mono">preprocess_mode = hydromt_build</span> for clean Manual Mode testing.
   L1331:             Use Override Mode for already-native or hybrid reduced-event catalog workflows unless you are intentionally debugging those backend paths from Manual.
   L1332:           </div>
```

```text
   L1410:     const checksOutput = document.getElementById('checks-output');
   L1411:     
>> L1412:     let extraLoadedConfig = {};
   L1413:     let lastLoadedUnmatchedKeys = [];
   L1414: 
```

```text
   L1413:     let lastLoadedUnmatchedKeys = [];
   L1414: 
>> L1415:     const MANUAL_FIXED_CONFIG = {
   L1416:       pipeline_mode: 'preflight_only',
   L1417:       preprocess_mode: 'hydromt_build',
```

```text
   L1414: 
   L1415:     const MANUAL_FIXED_CONFIG = {
>> L1416:       pipeline_mode: 'preflight_only',
   L1417:       preprocess_mode: 'hydromt_build',
   L1418:       use_sfincs_file_overrides: false
```

```text
   L1415:     const MANUAL_FIXED_CONFIG = {
   L1416:       pipeline_mode: 'preflight_only',
>> L1417:       preprocess_mode: 'hydromt_build',
   L1418:       use_sfincs_file_overrides: false
   L1419:     };
```

```text
   L1416:       pipeline_mode: 'preflight_only',
   L1417:       preprocess_mode: 'hydromt_build',
>> L1418:       use_sfincs_file_overrides: false
   L1419:     };
   L1420:     
```

```text
   L1419:     };
   L1420:     
>> L1421:     const MANUAL_STRIP_LOADED_KEYS = new Set([
   L1422:       // Override/native workflow metadata should not survive into Manual Mode.
   L1423:       'native_static_sfincs_input_dirs',
```

```text
   L1423:       'native_static_sfincs_input_dirs',
   L1424:       'native_event_sfincs_input_dirs',
>> L1425:       'native_sfincs_input_dirs',
   L1426:       'sfincs_file_overrides',
   L1427:       'override_source_path',
```

```text
   L1439:     
   L1440:     function applyManualFixedConfig(cfg) {
>> L1441:       Object.entries(MANUAL_FIXED_CONFIG).forEach(([key, value]) => {
   L1442:         cfg[key] = value;
   L1443:       });
```

```text
   L1443:       });
   L1444:     
>> L1445:       MANUAL_STRIP_LOADED_KEYS.forEach(key => {
   L1446:         delete cfg[key];
   L1447:       });
```

```text
   L1483:     }
   L1484: 
>> L1485:     function getConfig() {
   L1486:       // Start from keys loaded from an existing backend JSON but not rendered by this page.
   L1487:       // Rendered Manual fields then overwrite matching keys, so visible edits always win.
```

```text
   L1486:       // Start from keys loaded from an existing backend JSON but not rendered by this page.
   L1487:       // Rendered Manual fields then overwrite matching keys, so visible edits always win.
>> L1488:       const cfg = { ...extraLoadedConfig };
   L1489:     
   L1490:       document.querySelectorAll('[data-key]').forEach(el => {
```

```text
   L1494:           el.style.borderColor = '';
   L1495:         } catch (err) {
>> L1496:           cfg[key] = `JSON_PARSE_ERROR: ${err.message}`;
   L1497:           el.style.borderColor = 'var(--bad)';
   L1498:         }
```

```text
   L1502:     }
   L1503: 
>> L1504:     function setFieldValue(key, value) {
   L1505:       const el = document.querySelector(`[data-key="${CSS.escape(key)}"]`);
   L1506:       if (!el) return false;
```

```text
   L1516:     }
   L1517: 
>> L1518:     function updatePreview() {
   L1519:       const cfg = getConfig();
   L1520:       const root = plannedRunRoot(cfg);
```

```text
   L1517: 
   L1518:     function updatePreview() {
>> L1519:       const cfg = getConfig();
   L1520:       const root = plannedRunRoot(cfg);
   L1521:       if (runRootPreview) runRootPreview.textContent = root;
```

```text
   L1527:       const div = document.createElement('div');
   L1528:       div.className = `check-item ${status}`;
>> L1529:       const label = status === 'good' ? 'OK' : status === 'warn' ? 'WARN' : 'FAIL';
   L1530:       div.innerHTML = `<div class="check-status">${label}</div><div><b>${message}</b><br><span class="muted">${detail || ''}</span></div>`;
   L1531:       return div;
```

```text
   L1542:     
   L1543:     function renderRuntimeWindowReview(audit) {
>> L1544:       const target = document.getElementById('runtime-window-review-output');
   L1545:       if (!target) return;
   L1546:     
```

```text
   L1561:       target.innerHTML = `
   L1562:         <div style="margin-top: 1rem; margin-bottom: 1rem; padding: 1rem; border-radius: 14px; border: 2px solid ${border}; background: ${background}; color: ${text};">
>> L1563:           <div><strong>${manualReviewEsc(audit.message || 'Runtime-window review complete.')}</strong></div>
   L1564:           <div style="margin-top: 0.45rem;">Category: <code>${manualReviewEsc(audit.category || '')}</code></div>
   L1565:           <div style="margin-top: 0.45rem;">Reason: ${manualReviewEsc(audit.reason || '')}</div>
```

```text
   L1571:     }
   L1572:     
>> L1573:     async function runRuntimeWindowReviewCheck() {
   L1574:       const target = document.getElementById('runtime-window-review-output');
   L1575:       if (target) {
```

```text
   L1572:     
   L1573:     async function runRuntimeWindowReviewCheck() {
>> L1574:       const target = document.getElementById('runtime-window-review-output');
   L1575:       if (target) {
   L1576:         target.innerHTML = `
```

```text
   L1583:       let cfg;
   L1584:       try {
>> L1585:         cfg = getConfig();
   L1586:       } catch (err) {
   L1587:         renderRuntimeWindowReview({
```

```text
   L1588:           severity: 'major',
   L1589:           ui_color: 'red',
>> L1590:           category: 'runtime_window_review_failed',
   L1591:           message: 'Runtime window review failed before request.',
   L1592:           reason: err.message,
```

```text
   L1589:           ui_color: 'red',
   L1590:           category: 'runtime_window_review_failed',
>> L1591:           message: 'Runtime window review failed before request.',
   L1592:           reason: err.message,
   L1593:           mismatches: {}
```

```text
   L1597:     
   L1598:       try {
>> L1599:         const response = await fetch('/api/review-runtime-window', {
   L1600:           method: 'POST',
   L1601:           headers: { 'Content-Type': 'application/json' },
```

```text
   L1606:     
   L1607:         if (!response.ok || !result.ok) {
>> L1608:           throw new Error(result.error || 'Runtime review request failed.');
   L1609:         }
   L1610:     
```

```text
   L1614:           severity: 'major',
   L1615:           ui_color: 'red',
>> L1616:           category: 'runtime_window_review_failed',
   L1617:           message: 'Runtime window review request failed.',
   L1618:           reason: err.message,
```

```text
   L1615:           ui_color: 'red',
   L1616:           category: 'runtime_window_review_failed',
>> L1617:           message: 'Runtime window review request failed.',
   L1618:           reason: err.message,
   L1619:           mismatches: {}
```

```text
   L1622:     }
   L1623:     
>> L1624:     window.runRuntimeWindowReviewCheck = runRuntimeWindowReviewCheck;
   L1625: 
   L1626:     function runChecks(navigate = true) {
```

```text
   L1624:     window.runRuntimeWindowReviewCheck = runRuntimeWindowReviewCheck;
   L1625: 
>> L1626:     function runChecks(navigate = true) {
   L1627:       const cfg = getConfig();
   L1628:       checksOutput.innerHTML = '';
```

```text
   L1625: 
   L1626:     function runChecks(navigate = true) {
>> L1627:       const cfg = getConfig();
   L1628:       checksOutput.innerHTML = '';
   L1629:       const checks = [];
```

```text
   L1629:       const checks = [];
   L1630:     
>> L1631:       runRuntimeWindowReviewCheck();
   L1632: 
   L1633:       if (/^[A-Za-z0-9_.-]+$/.test(cfg.run_name || '')) {
```

```text
   L1695:         } else {
   L1696:           checks.push(makeCheck(
>> L1697:             'warn',
   L1698:             'tref is after tstart.',
   L1699:             'This is unusual; confirm it is intentional.'
```

```text
   L1785: 
   L1786:       // Manual-mode identity checks.
>> L1787:       if (cfg.preprocess_mode === 'hydromt_build') {
   L1788:         checks.push(makeCheck(
   L1789:           'good',
```

```text
   L1795:           'bad',
   L1796:           'Manual preprocess mode is not hydromt_build.',
>> L1797:           `Current preprocess_mode = ${cfg.preprocess_mode}. Manual v1.1 should stay hydromt_build.`
   L1798:         ));
   L1799:       }
```

```text
   L1799:       }
   L1800: 
>> L1801:       if (cfg.pipeline_mode === 'preflight_only') {
   L1802:         checks.push(makeCheck(
   L1803:           'good',
```

```text
   L1802:         checks.push(makeCheck(
   L1803:           'good',
>> L1804:           'Manual hidden pipeline_mode default is safe.',
   L1805:           'Submit/build actions are chosen by the final Submit tab buttons.'
   L1806:         ));
```

```text
   L1807:       } else {
   L1808:         checks.push(makeCheck(
>> L1809:           'warn',
   L1810:           'Hidden pipeline_mode is not the safe default.',
   L1811:           `Current pipeline_mode = ${cfg.pipeline_mode}. The Submit tab will still override it when staging.`
```

```text
   L1808:         checks.push(makeCheck(
   L1809:           'warn',
>> L1810:           'Hidden pipeline_mode is not the safe default.',
   L1811:           `Current pipeline_mode = ${cfg.pipeline_mode}. The Submit tab will still override it when staging.`
   L1812:         ));
```

```text
   L1809:           'warn',
   L1810:           'Hidden pipeline_mode is not the safe default.',
>> L1811:           `Current pipeline_mode = ${cfg.pipeline_mode}. The Submit tab will still override it when staging.`
   L1812:         ));
   L1813:       }
```

```text
   L1830:       }
   L1831: 
>> L1832:       if (catalogList.length === 1 && String(catalogList[0]).trim() === 'artifact_data') {
   L1833:         checks.push(makeCheck(
   L1834:           'warn',
```

```text
   L1832:       if (catalogList.length === 1 && String(catalogList[0]).trim() === 'artifact_data') {
   L1833:         checks.push(makeCheck(
>> L1834:           'warn',
   L1835:           'data_catalogs still uses artifact_data.',
   L1836:           'This is okay for a tiny artifact test, but probably wrong for a real Harris County run.'
```

```text
   L1833:         checks.push(makeCheck(
   L1834:           'warn',
>> L1835:           'data_catalogs still uses artifact_data.',
   L1836:           'This is okay for a tiny artifact test, but probably wrong for a real Harris County run.'
   L1837:         ));
```

```text
   L1886:         } else {
   L1887:           checks.push(makeCheck(
>> L1888:             'warn',
   L1889:             'Landcover roughness is enabled but no reclass/source config is set.',
   L1890:             'Either browse/select a reclass table/source, or disable use_landcover_roughness_if_available.'
```

```text
   L1936:         } else if (cfg.rainfall_kind === 'event_catalog_aorc') {
   L1937:           checks.push(makeCheck(
>> L1938:             'warn',
   L1939:             'Rainfall kind is event_catalog_aorc in Manual Mode.',
   L1940:             'That reduced-event workflow is usually cleaner in Override/hybrid mode.'
```

```text
   L1949:       } else {
   L1950:         checks.push(makeCheck(
>> L1951:           'warn',
   L1952:           'Rainfall is disabled.',
   L1953:           'Confirm this is intentional for the event.'
```

```text
   L1957:       // Water-level consistency.
   L1958:       if (cfg.use_waterlevel_boundary) {
>> L1959:         if (cfg.waterlevel_source_kind === 'native_sfincs') {
   L1960:           checks.push(makeCheck(
   L1961:             'warn',
```

```text
   L1959:         if (cfg.waterlevel_source_kind === 'native_sfincs') {
   L1960:           checks.push(makeCheck(
>> L1961:             'warn',
   L1962:             'Water-level source kind is native_sfincs in Manual Mode.',
   L1963:             'Native SFINCS files are usually better handled in Override Mode.'
```

```text
   L1960:           checks.push(makeCheck(
   L1961:             'warn',
>> L1962:             'Water-level source kind is native_sfincs in Manual Mode.',
   L1963:             'Native SFINCS files are usually better handled in Override Mode.'
   L1964:           ));
```

```text
   L1980:       // Discharge consistency.
   L1981:       if (cfg.use_discharge_boundary) {
>> L1982:         if (cfg.discharge_source_kind === 'native_sfincs') {
   L1983:           checks.push(makeCheck(
   L1984:             'warn',
```

```text
   L1982:         if (cfg.discharge_source_kind === 'native_sfincs') {
   L1983:           checks.push(makeCheck(
>> L1984:             'warn',
   L1985:             'Discharge source kind is native_sfincs in Manual Mode.',
   L1986:             'Native SFINCS files are usually better handled in Override Mode.'
```

```text
   L1983:           checks.push(makeCheck(
   L1984:             'warn',
>> L1985:             'Discharge source kind is native_sfincs in Manual Mode.',
   L1986:             'Native SFINCS files are usually better handled in Override Mode.'
   L1987:           ));
```

```text
   L2043:       // Subgrid consistency.
   L2044:       if (cfg.use_subgrid) {
>> L2045:         if (cfg.subgrid_source_kind === 'premade_sbgfile') {
   L2046:           if (!isBlank(cfg.subgrid_native_file_path)) {
   L2047:             checks.push(makeCheck(
```

```text
   L2057:             ));
   L2058:           }
>> L2059:         } else if (cfg.subgrid_source_kind === 'none') {
   L2060:           checks.push(makeCheck(
   L2061:             'warn',
```

```text
   L2059:         } else if (cfg.subgrid_source_kind === 'none') {
   L2060:           checks.push(makeCheck(
>> L2061:             'warn',
   L2062:             'use_subgrid is true but subgrid_source_kind is none.',
   L2063:             'Choose hydromt_generate or disable use_subgrid.'
```

```text
   L2060:           checks.push(makeCheck(
   L2061:             'warn',
>> L2062:             'use_subgrid is true but subgrid_source_kind is none.',
   L2063:             'Choose hydromt_generate or disable use_subgrid.'
   L2064:           ));
```

```text
   L2067:             'good',
   L2068:             'Subgrid settings are structurally plausible.',
>> L2069:             `subgrid_source_kind = ${cfg.subgrid_source_kind}`
   L2070:           ));
   L2071:         }
```

```text
   L2072:       } else {
   L2073:         checks.push(makeCheck(
>> L2074:           'warn',
   L2075:           'Subgrid is disabled.',
   L2076:           'This may be intentional, but most Harris County runs should use subgrid.'
```

```text
   L2089:       if (cfg.use_infiltration && cfg.infiltration_mode === 'none') {
   L2090:         checks.push(makeCheck(
>> L2091:           'warn',
   L2092:           'Infiltration is enabled but infiltration_mode is none.',
   L2093:           'Choose a real infiltration mode or disable use_infiltration.'
```

```text
   L2095:       } else if (!cfg.use_infiltration && cfg.infiltration_mode !== 'none') {
   L2096:         checks.push(makeCheck(
>> L2097:           'warn',
   L2098:           'Infiltration mode is set but use_infiltration is false.',
   L2099:           `infiltration_mode = ${cfg.infiltration_mode}`
```

```text
   L2153:         } else {
   L2154:           checks.push(makeCheck(
>> L2155:             'warn',
   L2156:             'Structures are enabled but no structure source/path is selected.',
   L2157:             'Disable use_structures or configure thin dams, weirs, drainage structures, or culverts.'
```

```text
   L2162:       if (cfg.use_obs_points && isBlank(cfg.obs_points_path)) {
   L2163:         checks.push(makeCheck(
>> L2164:           'warn',
   L2165:           'Observation points are enabled but obs_points_path is blank.',
   L2166:           'Set obs_points_path or disable use_obs_points.'
```

```text
   L2170:       if (cfg.use_obs_lines && isBlank(cfg.obs_lines_path)) {
   L2171:         checks.push(makeCheck(
>> L2172:           'warn',
   L2173:           'Observation lines are enabled but obs_lines_path is blank.',
   L2174:           'Set obs_lines_path or disable use_obs_lines.'
```

```text
   L2202:         } else {
   L2203:           checks.push(makeCheck(
>> L2204:             'warn',
   L2205:             'SFINCS container path does not end in .sif.',
   L2206:             containerPath
```

```text
   L2215:       }
   L2216: 
>> L2217:       if (String(cfg.output_root || '').startsWith('/proj/') && !cfg.allow_writes_inside_proj) {
   L2218:         checks.push(makeCheck(
   L2219:           'bad',
```

```text
   L2218:         checks.push(makeCheck(
   L2219:           'bad',
>> L2220:           'output_root is inside /proj but allow_writes_inside_proj is false.',
   L2221:           'Either enable allow_writes_inside_proj or choose a /work run root.'
   L2222:         ));
```

```text
   L2219:           'bad',
   L2220:           'output_root is inside /proj but allow_writes_inside_proj is false.',
>> L2221:           'Either enable allow_writes_inside_proj or choose a /work run root.'
   L2222:         ));
   L2223:       }
```

```text
   L2223:       }
   L2224: 
>> L2225:       if (cfg.overwrite_existing_run) {
   L2226:         checks.push(makeCheck(
   L2227:           'warn',
```

```text
   L2225:       if (cfg.overwrite_existing_run) {
   L2226:         checks.push(makeCheck(
>> L2227:           'warn',
   L2228:           'overwrite_existing_run is true.',
   L2229:           'Only use this when intentionally replacing a prior run folder.'
```

```text
   L2226:         checks.push(makeCheck(
   L2227:           'warn',
>> L2228:           'overwrite_existing_run is true.',
   L2229:           'Only use this when intentionally replacing a prior run folder.'
   L2230:         ));
```

```text
   L2233: 
   L2234:       const forcingOn = Boolean(cfg.use_rainfall || cfg.use_waterlevel_boundary || cfg.use_discharge_boundary || cfg.use_wind || cfg.use_pressure);
>> L2235:       if (!cfg.require_at_least_one_forcing || forcingOn || cfg.allow_missing_model_inputs) {
   L2236:         checks.push(makeCheck('good', 'Forcing safety check passed.', `forcing enabled = ${forcingOn}`));
   L2237:       } else {
```

```text
   L2236:         checks.push(makeCheck('good', 'Forcing safety check passed.', `forcing enabled = ${forcingOn}`));
   L2237:       } else {
>> L2238:         checks.push(makeCheck('bad', 'No forcing is enabled.', 'Turn on at least one forcing or intentionally relax require_at_least_one_forcing / allow_missing_model_inputs.'));
   L2239:       }
   L2240: 
```

```text
   L2239:       }
   L2240: 
>> L2241:       if (cfg.preprocess_mode === 'hybrid' || cfg.preprocess_mode === 'native_sfincs_assembly') {
   L2242:         checks.push(makeCheck('warn', 'This preprocess mode usually belongs in Override Mode.', `preprocess_mode = ${cfg.preprocess_mode}; manual mode no longer exposes full native-file routing controls.`));
   L2243:       } else {
```

```text
   L2240: 
   L2241:       if (cfg.preprocess_mode === 'hybrid' || cfg.preprocess_mode === 'native_sfincs_assembly') {
>> L2242:         checks.push(makeCheck('warn', 'This preprocess mode usually belongs in Override Mode.', `preprocess_mode = ${cfg.preprocess_mode}; manual mode no longer exposes full native-file routing controls.`));
   L2243:       } else {
   L2244:         checks.push(makeCheck('good', 'Manual preprocess mode is clean.', `preprocess_mode = ${cfg.preprocess_mode}`));
```

```text
   L2242:         checks.push(makeCheck('warn', 'This preprocess mode usually belongs in Override Mode.', `preprocess_mode = ${cfg.preprocess_mode}; manual mode no longer exposes full native-file routing controls.`));
   L2243:       } else {
>> L2244:         checks.push(makeCheck('good', 'Manual preprocess mode is clean.', `preprocess_mode = ${cfg.preprocess_mode}`));
   L2245:       }
   L2246: 
```

```text
   L2245:       }
   L2246: 
>> L2247:       if (cfg.subgrid_source_kind === 'premade_sbgfile' && !cfg.subgrid_native_file_path) {
   L2248:         checks.push(makeCheck('bad', 'Pre-made subgrid selected but no subgrid file path is set.', 'Set subgrid_native_file_path or switch subgrid_source_kind back to hydromt_generate.'));
   L2249:       } else if (cfg.subgrid_source_kind === 'premade_sbgfile') {
```

```text
   L2246: 
   L2247:       if (cfg.subgrid_source_kind === 'premade_sbgfile' && !cfg.subgrid_native_file_path) {
>> L2248:         checks.push(makeCheck('bad', 'Pre-made subgrid selected but no subgrid file path is set.', 'Set subgrid_native_file_path or switch subgrid_source_kind back to hydromt_generate.'));
   L2249:       } else if (cfg.subgrid_source_kind === 'premade_sbgfile') {
   L2250:         checks.push(makeCheck('warn', 'Pre-made subgrid path is set.', 'This UI field may need a backend/schema hook before the runner uses it.'));
```

```text
   L2247:       if (cfg.subgrid_source_kind === 'premade_sbgfile' && !cfg.subgrid_native_file_path) {
   L2248:         checks.push(makeCheck('bad', 'Pre-made subgrid selected but no subgrid file path is set.', 'Set subgrid_native_file_path or switch subgrid_source_kind back to hydromt_generate.'));
>> L2249:       } else if (cfg.subgrid_source_kind === 'premade_sbgfile') {
   L2250:         checks.push(makeCheck('warn', 'Pre-made subgrid path is set.', 'This UI field may need a backend/schema hook before the runner uses it.'));
   L2251:       }
```

```text
   L2248:         checks.push(makeCheck('bad', 'Pre-made subgrid selected but no subgrid file path is set.', 'Set subgrid_native_file_path or switch subgrid_source_kind back to hydromt_generate.'));
   L2249:       } else if (cfg.subgrid_source_kind === 'premade_sbgfile') {
>> L2250:         checks.push(makeCheck('warn', 'Pre-made subgrid path is set.', 'This UI field may need a backend/schema hook before the runner uses it.'));
   L2251:       }
   L2252: 
```

```text
   L2251:       }
   L2252: 
>> L2253:       if (cfg.pipeline_mode === 'submit_slurm_chain') {
   L2254:         checks.push(makeCheck(
   L2255:           'warn',
```

```text
   L2253:       if (cfg.pipeline_mode === 'submit_slurm_chain') {
   L2254:         checks.push(makeCheck(
>> L2255:           'warn',
   L2256:           'Submit mode is selected in the config.',
   L2257:           'Use the Final submit tab buttons so the Flask backend runs preflight/build/submit in order.'
```

```text
   L2261:           'good',
   L2262:           'Submit is not selected in the config.',
>> L2263:           `pipeline_mode = ${cfg.pipeline_mode}. Use the Final submit tab buttons when ready.`
   L2264:         ));
   L2265:       }
```

```text
   L2268:         checks.push(makeCheck('good', 'Strict schema validation is on.', 'Useful for final configs.'));
   L2269:       } else {
>> L2270:         checks.push(makeCheck('warn', 'Strict schema validation is off.', 'Good during editing; turn on later if you want typo/type issues to fail.'));
   L2271:       }
   L2272: 
```

```text
   L2285:       if (lastLoadedUnmatchedKeys.length > 0) {
   L2286:         checks.push(makeCheck(
>> L2287:           'warn',
   L2288:           'Loaded config has extra backend keys preserved.',
   L2289:           `${lastLoadedUnmatchedKeys.length} key(s): ${lastLoadedUnmatchedKeys.slice(0, 12).join(', ')}${lastLoadedUnmatchedKeys.length > 12 ? ', ...' : ''}`
```

```text
   L2299: 
   L2300:       const badCount = checks.filter(c => c.classList.contains('bad')).length;
>> L2301:       const warnCount = checks.filter(c => c.classList.contains('warn')).length;
   L2302:     
   L2303:       const summary = makeCheck(
```

```text
   L2302:     
   L2303:       const summary = makeCheck(
>> L2304:         badCount > 0 ? 'bad' : warnCount > 0 ? 'warn' : 'good',
   L2305:         'Manual page checks complete.',
   L2306:         `${badCount} fail(s), ${warnCount} warning(s), ${checks.length} total check(s).`
```

```text
   L2304:         badCount > 0 ? 'bad' : warnCount > 0 ? 'warn' : 'good',
   L2305:         'Manual page checks complete.',
>> L2306:         `${badCount} fail(s), ${warnCount} warning(s), ${checks.length} total check(s).`
   L2307:       );
   L2308:     
```

```text
   L2315:     }
   L2316: 
>> L2317:     async function saveConfig(confirmUpdate = false) {
   L2318:       const cfg = getConfig();
   L2319:     
```

```text
   L2316: 
   L2317:     async function saveConfig(confirmUpdate = false) {
>> L2318:       const cfg = getConfig();
   L2319:     
   L2320:       const response = await fetch('/api/save-config', {
```

```text
   L2318:       const cfg = getConfig();
   L2319:     
>> L2320:       const response = await fetch('/api/save-config', {
   L2321:         method: 'POST',
   L2322:         headers: {
```

```text
   L2335:     
   L2336:         if (data.run_state && data.run_state.has_real_run) {
>> L2337:           message += '\n\nWarning: this run folder also appears to contain real run artifacts. Updating run_config.json could make the saved config differ from what was actually run.';
   L2338:         }
   L2339:     
```

```text
   L2339:     
   L2340:         if (confirm(message)) {
>> L2341:           return saveConfig(true);
   L2342:         }
   L2343:     
```

```text
   L2346:     
   L2347:       if (!response.ok || !data.ok) {
>> L2348:         const message = data.message || data.error || `Save failed with HTTP ${response.status}`;
   L2349:         alert(message);
   L2350:         throw new Error(message);
```

```text
   L2348:         const message = data.message || data.error || `Save failed with HTTP ${response.status}`;
   L2349:         alert(message);
>> L2350:         throw new Error(message);
   L2351:       }
   L2352:     
```

```text
   L2360: }
   L2361: 
>> L2362:     async function loadConfigFromFile(file) {
   L2363:       if (!file) return;
   L2364:       const text = await file.text();
```

```text
   L2374:     
   L2375:       // Reset preserved extras each time a new file is loaded.
>> L2376:       extraLoadedConfig = {};
   L2377:       lastLoadedUnmatchedKeys = [];
   L2378:     
```

```text
   L2378:     
   L2379:       Object.entries(cfg).forEach(([key, value]) => {
>> L2380:         if (setFieldValue(key, value)) {
   L2381:           matched += 1;
   L2382:         } else if (!MANUAL_STRIP_LOADED_KEYS.has(key) && !(key in MANUAL_FIXED_CONFIG)) {
```

```text
   L2380:         if (setFieldValue(key, value)) {
   L2381:           matched += 1;
>> L2382:         } else if (!MANUAL_STRIP_LOADED_KEYS.has(key) && !(key in MANUAL_FIXED_CONFIG)) {
   L2383:           unmatched.push(key);
   L2384:           extraLoadedConfig[key] = value;
```

```text
   L2382:         } else if (!MANUAL_STRIP_LOADED_KEYS.has(key) && !(key in MANUAL_FIXED_CONFIG)) {
   L2383:           unmatched.push(key);
>> L2384:           extraLoadedConfig[key] = value;
   L2385:         }
   L2386:       });
```

```text
   L2388:       lastLoadedUnmatchedKeys = unmatched;
   L2389:     
>> L2390:       updatePreview();
   L2391:     
   L2392:       alert(
```

```text
   L2399:     tabs.forEach(tab => tab.addEventListener('click', () => showTab(tab.dataset.tab)));
   L2400:     document.querySelectorAll('[data-key]').forEach(el => {
>> L2401:       el.addEventListener('input', updatePreview);
   L2402:       el.addEventListener('change', updatePreview);
   L2403:     });
```

```text
   L2400:     document.querySelectorAll('[data-key]').forEach(el => {
   L2401:       el.addEventListener('input', updatePreview);
>> L2402:       el.addEventListener('change', updatePreview);
   L2403:     });
   L2404:     document.getElementById('save-config-button').addEventListener('click', saveConfig);
```

```text
   L2402:       el.addEventListener('change', updatePreview);
   L2403:     });
>> L2404:     document.getElementById('save-config-button').addEventListener('click', saveConfig);
   L2405:     document.getElementById('load-config-input').addEventListener('change', event => loadConfigFromFile(event.target.files[0]));
   L2406:     document.getElementById('check-button').addEventListener('click', () => runChecks(true));
```

```text
   L2403:     });
   L2404:     document.getElementById('save-config-button').addEventListener('click', saveConfig);
>> L2405:     document.getElementById('load-config-input').addEventListener('change', event => loadConfigFromFile(event.target.files[0]));
   L2406:     document.getElementById('check-button').addEventListener('click', () => runChecks(true));
   L2407:     document.getElementById('check-button-2').addEventListener('click', () => runChecks(false));
```

```text
   L2404:     document.getElementById('save-config-button').addEventListener('click', saveConfig);
   L2405:     document.getElementById('load-config-input').addEventListener('change', event => loadConfigFromFile(event.target.files[0]));
>> L2406:     document.getElementById('check-button').addEventListener('click', () => runChecks(true));
   L2407:     document.getElementById('check-button-2').addEventListener('click', () => runChecks(false));
   L2408: 
```

```text
   L2405:     document.getElementById('load-config-input').addEventListener('change', event => loadConfigFromFile(event.target.files[0]));
   L2406:     document.getElementById('check-button').addEventListener('click', () => runChecks(true));
>> L2407:     document.getElementById('check-button-2').addEventListener('click', () => runChecks(false));
   L2408: 
   L2409:     // Expose Manual Mode hooks for reusable static helpers such as pipeline_actions.js.
```

```text
   L2408: 
   L2409:     // Expose Manual Mode hooks for reusable static helpers such as pipeline_actions.js.
>> L2410:     window.getConfig = getConfig;
   L2411:     window.setFieldValue = setFieldValue;
   L2412:     window.updatePreview = updatePreview;
```

```text
   L2409:     // Expose Manual Mode hooks for reusable static helpers such as pipeline_actions.js.
   L2410:     window.getConfig = getConfig;
>> L2411:     window.setFieldValue = setFieldValue;
   L2412:     window.updatePreview = updatePreview;
   L2413:     window.runChecks = runChecks;
```

```text
   L2410:     window.getConfig = getConfig;
   L2411:     window.setFieldValue = setFieldValue;
>> L2412:     window.updatePreview = updatePreview;
   L2413:     window.runChecks = runChecks;
   L2414:     window.showTab = showTab;
```

```text
   L2411:     window.setFieldValue = setFieldValue;
   L2412:     window.updatePreview = updatePreview;
>> L2413:     window.runChecks = runChecks;
   L2414:     window.showTab = showTab;
   L2415:     window.getExtraLoadedConfig = () => ({ ...extraLoadedConfig });
```

```text
   L2413:     window.runChecks = runChecks;
   L2414:     window.showTab = showTab;
>> L2415:     window.getExtraLoadedConfig = () => ({ ...extraLoadedConfig });
   L2416:     window.applyManualFixedConfig = applyManualFixedConfig;
   L2417:     window.MANUAL_FIXED_CONFIG = MANUAL_FIXED_CONFIG;
```

```text
   L2415:     window.getExtraLoadedConfig = () => ({ ...extraLoadedConfig });
   L2416:     window.applyManualFixedConfig = applyManualFixedConfig;
>> L2417:     window.MANUAL_FIXED_CONFIG = MANUAL_FIXED_CONFIG;
   L2418: 
   L2419: 
```

```text
   L2418: 
   L2419: 
>> L2420:     updatePreview();
   L2421:   </script>
   L2422: <script src="static/launcher_defaults.js"></script>
```
