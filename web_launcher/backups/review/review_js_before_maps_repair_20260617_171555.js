// review.js — SFINCS Run Review V1 draft
// Read-only browser logic for the new Review tab.

(function () {
  "use strict";

const state = {
  runs: [],
  selectedRun: "",
  review: null,
  activeReviewTool: "maps",
  mapManifest: null,
  mapStatus: null,
  mapPollTimer: null,
};

  const $ = (id) => document.getElementById(id);

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function showMessage(kind, text) {
    const area = $("message-area");
    const cls = kind === "error" ? "warning warning-critical" : kind === "warn" ? "warning warning-major" : "warning warning-minor";
    area.innerHTML = `<div class="${cls}"><p>${escapeHtml(text)}</p></div>`;
  }

  function clearMessage() {
    $("message-area").innerHTML = "";
  }


  function clearInteractiveReviewOutput() {
    state.mapManifest = null;
    state.mapStatus = null;
    state.activeReviewTool = "maps";

    if (state.mapPollTimer) {
      window.clearTimeout(state.mapPollTimer);
      state.mapPollTimer = null;
    }

    const futureTab = $("tab-future");
    if (futureTab) {
      futureTab.innerHTML = `
        <div class="empty-note">
          Interactive Review output cleared. Load the selected run again to populate this area.
        </div>
      `;
    }
  }

  async function fetchJson(url) {
    const res = await fetch(url, { cache: "no-store" });
    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch (err) {
      throw new Error(`Expected JSON from ${url}, got: ${text.slice(0, 300)}`);
    }
    if (!res.ok || data.ok === false) {
      const msg = data.error || data.message || `Request failed: ${res.status}`;
      throw new Error(msg);
    }
    return data;
  }


  async function fetchText(url) {
    const res = await fetch(url, { cache: "no-store" });
    const text = await res.text();
    if (!res.ok) {
      throw new Error(`Request failed: ${res.status}: ${text.slice(0, 240)}`);
    }
    return text;
  }

  function statusClass(label) {
    const lower = String(label || "").toLowerCase();
    if (lower.includes("completed")) return "status-pill status-completed";
    if (lower.includes("failed")) return "status-pill status-failed";
    if (lower.includes("partial") || lower.includes("missing") || lower.includes("preprocess") || lower.includes("sfincs")) return "status-pill status-partial";
    return "status-pill";
  }

  function formatBytes(n) {
    if (n === null || n === undefined || isNaN(Number(n))) return "";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let v = Number(n);
    let i = 0;
    while (v >= 1024 && i < units.length - 1) {
      v /= 1024;
      i += 1;
    }
    return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
  }

  function renderMetricRows(obj) {
    if (!obj || typeof obj !== "object") return `<div class="empty-note">No data.</div>`;
    return Object.entries(obj).map(([key, value]) => {
      let pretty;
      if (value && typeof value === "object") {
        pretty = `<pre>${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
      } else {
        pretty = escapeHtml(value);
      }
      return `<div class="metric-row"><div class="metric-key">${escapeHtml(key)}</div><div class="metric-val">${pretty}</div></div>`;
    }).join("");
  }

  function pickConfigSource(review) {
    return review.run_config || review.full_config || review.config || review.config_summary || {};
  }

  function hasOwn(obj, key) {
    return Object.prototype.hasOwnProperty.call(obj || {}, key);
  }

  function hasDisplayValue(value) {
    if (value === null || value === undefined) return false;

    if (typeof value === "string") {
      return value.trim() !== "";
    }

    if (Array.isArray(value)) {
      return value.length > 0;
    }

    if (typeof value === "object") {
      return Object.keys(value).length > 0;
    }

    // Keep false and 0. They are meaningful config values.
    return true;
  }

  function startsAny(key, prefixes) {
    return prefixes.some((prefix) => key.startsWith(prefix));
  }

  function containsAny(key, parts) {
    return parts.some((part) => key.includes(part));
  }

  const MANUAL_CONFIG_GROUPS = [
    {
      title: "0. Run identity and launcher record",
      test: (key) => (
        [
          "run_name", "event_name", "run_series", "run_description", "run_tags",
          "pipeline_mode", "preprocess_mode", "created_at", "created_by_user",
          "source_config_path", "save_config_json", "save_data_inventory",
          "save_job_ids", "overwrite_existing_run"
        ].includes(key)
      ),
    },

    {
      title: "1. Project, output, backend, environment, and container paths",
      test: (key) => (
        [
          "project_root", "output_root", "data_root",
          "runner_file", "runner_python", "runner_python_version",
          "conda_python", "conda_env_path", "anaconda_module", "apptainer_module",
          "sfincs_container", "sfincs_container_path",
          "prefer_pipeline_bundle_runtime_paths", "allow_writes_inside_proj"
        ].includes(key)
      ),
    },

    {
      title: "2. Data catalogs, native overrides, and HydroMT source setup",
      test: (key) => (
        [
          "data_catalogs",
          "native_sfincs_input_dirs", "native_static_sfincs_input_dirs", "native_event_sfincs_input_dirs",
          "use_sfincs_file_overrides",
          "hydromt_dem_sources", "hydromt_bathy_sources", "hydromt_roughness_sources",
          "dem_paths", "bathy_paths",
          "hydrography_source", "hydrography_path"
        ].includes(key)
      ),
    },

    {
      title: "3. Region, grid, CRS, mask, DEM, bathy, and elevation controls",
      test: (key) => (
        startsAny(key, [
          "region_", "grid_", "mask_", "dem_", "bathy_", "elevation_"
        ]) ||
        [
          "active_zmin",
          "waterlevel_boundary_zmax",
          "reset_waterlevel_boundary",
          "reset_outflow_boundary",
          "outflow_boundary_polygon_path",
          "use_mask_template",
          "mask_template_path",
          "mask_template_mode"
        ].includes(key)
      ),
    },

    {
      title: "4. Runtime window, output intervals, and SFINCS input options",
      test: (key) => (
        [
          "tref", "tstart", "tstop",
          "dtout_s", "dthisout_s", "dtmaxout_s", "dtrstout_s",
          "meteo_update_interval_s", "output_format",
          "store_cumulative_precip", "store_hmax_subgrid",
          "store_max_flux", "store_max_velocity", "store_velocity", "store_wet_duration",
          "advanced_config"
        ].includes(key)
      ),
    },

    {
      title: "5. Rainfall, water level, discharge, wind, pressure, and forcing",
      test: (key) => (
        startsAny(key, [
          "rainfall_", "waterlevel_", "discharge_", "wind_", "pressure_",
          "streamflow_", "qinf_"
        ]) ||
        [
          "use_rainfall", "use_waterlevel_boundary", "use_discharge_boundary",
          "use_wind", "use_pressure",
          "require_at_least_one_forcing",
          "rainfall_path", "rainfall_source", "rainfall_variable",
          "waterlevel_path", "waterlevel_source", "waterlevel_variable",
          "discharge_source",
          "wind_path", "pressure_path", "wind_source", "pressure_source"
        ].includes(key)
      ),
    },

    {
      title: "6. Infiltration, soil storage, roughness, landcover, and subgrid",
      test: (key) => (
        startsAny(key, ["subgrid_"]) ||
        containsAny(key, [
          "infiltration", "curve_number", "soil_storage", "soil",
          "manning", "landcover"
        ]) ||
        [
          "landcover_source", "landcover_reclass_table",
          "roughness_land_level_m", "manning_land", "manning_sea", "manning_uniform",
          "use_spatially_variable_roughness", "use_landcover_roughness_if_available",
          "hsg_path", "f0_path", "fc_path", "kd_path", "ks_path",
          "psi_path", "sigma_path", "smax_path", "seff_path", "vol_path",
          "scs_initial_abstraction_factor"
        ].includes(key)
      ),
    },

    {
      title: "7. Structures, observation points, and cross sections",
      test: (key) => (
        startsAny(key, [
          "thin_dam_", "weir_", "drainage_structure_", "culvert_", "obs_"
        ]) ||
        [
          "use_obs_points", "use_obs_lines"
        ].includes(key)
      ),
    },

    {
      title: "8. Solver, Slurm, stage scripts, and job resources",
      test: (key) => (
        startsAny(key, ["slurm_"]) ||
        [
          "submit_with_dependencies", "dependency_type",
          "run_preprocessing_job", "run_sfincs_job", "run_postprocessing_job",
          "preprocess_stage_script", "postprocess_stage_script",
          "preprocess_time", "preprocess_ntasks", "preprocess_cpus_per_task",
          "preprocess_mem", "preprocess_nodes",
          "sfincs_time", "sfincs_ntasks", "sfincs_cpus_per_task",
          "sfincs_mem", "sfincs_nodes",
          "sfincs_use_openmp_threads", "sfincs_omp_places", "sfincs_omp_proc_bind",
          "postprocess_time", "postprocess_ntasks", "postprocess_cpus_per_task",
          "postprocess_mem", "postprocess_nodes"
        ].includes(key)
      ),
    },

    {
      title: "9. Postprocess plots, quicklooks, result maps, and basemap settings",
      test: (key) => (
        startsAny(key, ["postprocess_"]) &&
        ![
          "postprocess_time", "postprocess_ntasks", "postprocess_cpus_per_task",
          "postprocess_mem", "postprocess_nodes", "postprocess_stage_script"
        ].includes(key)
      ),
    },

    {
      title: "10. Validation, safety, schema, and advanced launcher behavior",
      test: (key) => (
        startsAny(key, ["warn_", "print_"]) ||
        [
          "strict_schema_validation",
          "validate_paths_before_submit",
          "stop_if_required_path_missing",
          "allow_missing_model_inputs",
          "bash_strict_mode",
          "preprocess_enable_hydromt_file_logging"
        ].includes(key)
      ),
    },
  ];

  function renderManualOrderedConfig(review) {
    const cfg = pickConfigSource(review);

    if (!cfg || typeof cfg !== "object" || !Object.keys(cfg).length) {
      return `<div class="empty-note">No run configuration was found in the review JSON.</div>`;
    }

    const used = new Set();
    const sectionHtml = [];

    MANUAL_CONFIG_GROUPS.forEach((section, index) => {
      const found = {};

      Object.keys(cfg).forEach((key) => {
        if (used.has(key)) return;
        if (!hasDisplayValue(cfg[key])) return;
        if (!section.test(key)) return;

        found[key] = cfg[key];
        used.add(key);
      });

      if (!Object.keys(found).length) return;

      sectionHtml.push(`
        <details ${index === 0 ? "open" : ""}>
          <summary>${escapeHtml(section.title)}</summary>
          <div class="details-body">${renderMetricRows(found)}</div>
        </details>
      `);
    });

    const leftovers = {};
    Object.keys(cfg).sort().forEach((key) => {
      if (used.has(key)) return;
      if (!hasDisplayValue(cfg[key])) return;
      leftovers[key] = cfg[key];
    });

    const leftoverHtml = Object.keys(leftovers).length ? `
      <details>
        <summary>Other non-empty config keys not assigned yet</summary>
        <div class="details-body">
          <p class="section-intro">
            These are real values in run_config.json that Review has not categorized yet. They are not hidden because they may matter for future diagnostics.
          </p>
          ${renderMetricRows(leftovers)}
        </div>
      </details>
    ` : "";

    return sectionHtml.join("") + leftoverHtml;
  }

  function loadFullSfincsInp() {
    const pre = $("full-sfincs-inp-pre");
    if (!pre || !state.selectedRun) return;

    pre.textContent = "Loading model/sfincs.inp…";

    fetchText(artifactUrl("model/sfincs.inp"))
      .then((text) => {
        pre.textContent = text || "(sfincs.inp was empty)";
      })
      .catch((err) => {
        pre.textContent = `Could not load full model/sfincs.inp:\n${err.message}`;
      });
  }


  function renderRunOptions(data) {
    const select = $("run-select");
    state.runs = data.runs || [];
    if (!state.runs.length) {
      select.innerHTML = `<option value="">No run folders found</option>`;
      return;
    }

    select.innerHTML = state.runs.map((run) => {
      const rawStatus = String(run.status || "").trim();
      const hideStatuses = new Set(["stat-error", "unknown", ""]);
      const cleanStatus = hideStatuses.has(rawStatus.toLowerCase()) ? "" : rawStatus;
      const label = cleanStatus ? `${run.name} — ${cleanStatus}` : run.name;
      return `<option value="${escapeHtml(run.name)}">${escapeHtml(label)}</option>`;
    }).join("");

    if (state.selectedRun) {
      select.value = state.selectedRun;
    }
  }

  async function loadRuns() {
    clearMessage();
    $("refresh-runs-btn").disabled = true;
    try {
      const data = await fetchJson("/api/review/runs");
      renderRunOptions(data);
      if (data.run_root) {
        showMessage("info", `Run root: ${data.run_root}`);
      }
    } catch (err) {
      showMessage("error", `Could not load runs: ${err.message}`);
    } finally {
      $("refresh-runs-btn").disabled = false;
    }
  }

  async function loadReview() {
    const run = $("run-select").value;
    if (!run) {
      showMessage("warn", "Pick a run first.");
      return;
    }
    state.selectedRun = run;
    state.review = null;
    clearInteractiveReviewOutput();

    $("load-review-btn").disabled = true;
    showMessage("info", `Loading review for ${run}…`);
    try {
      const data = await fetchJson(`/api/review/summary?run=${encodeURIComponent(run)}`);
      state.review = data.review || data;
      renderReview(state.review);
      clearMessage();
    } catch (err) {
      showMessage("error", `Could not load review: ${err.message}`);
    } finally {
      $("load-review-btn").disabled = false;
    }
  }

  function renderReview(review) {
    $("summary-grid").style.display = "block";

    renderStatus(review);
    renderStages(review);
    renderWarningCount(review);
    renderWarnings(review);
    renderConfig(review);
    renderArtifacts(review);
    renderNetcdf(review);
    renderChecks(review);
    renderLogs(review);
    renderFuture(review);

    $("tab-raw").innerHTML = `<pre>${escapeHtml(JSON.stringify(review, null, 2))}</pre>`;
  }
  
  
  function renderStatus(review) {
    const status = review.status || {};
    const label = status.label || "unknown";

    const titleEl = $("loaded-run-title");
    const pathEl = $("loaded-run-path");
    const statusLineEl = $("loaded-status-line");

    if (titleEl) titleEl.textContent = review.run_name || "Unnamed run";
    if (pathEl) pathEl.textContent = review.run_root || "";
    if (statusLineEl) {
      statusLineEl.innerHTML = `<span class="${statusClass(label)}">${escapeHtml(label)}</span>`;
    }

    $("status-card").innerHTML = `
      <p><span class="${statusClass(label)}">${escapeHtml(label)}</span></p>
      <div class="metric-row"><div class="metric-key">Run</div><div class="metric-val mono">${escapeHtml(review.run_name)}</div></div>
      <div class="metric-row"><div class="metric-key">Path</div><div class="metric-val mono">${escapeHtml(review.run_root)}</div></div>
      <div class="metric-row"><div class="metric-key">Review version</div><div class="metric-val mono">${escapeHtml(review.review_version)}</div></div>
    `;
  }

  function renderStages(review) {
    const stages = (review.status && review.status.stages) || {};
    const names = ["preprocess", "sfincs", "postprocess"];

    const rows = names.map((name) => {
      const s = stages[name] || {};
      const evidence = Array.isArray(s.complete_evidence) ? s.complete_evidence : [];
      const failed = Boolean(s.failed);

      let cls = "stage-light light-warn";
      let label = "no evidence yet";

      if (failed) {
        cls = "stage-light light-bad";
        label = "failed";
      } else if (evidence.length) {
        cls = "stage-light light-good";
        label = "cleared";
      }

      const note = evidence.length
        ? `${evidence.length} evidence file${evidence.length === 1 ? "" : "s"}`
        : "No completion evidence found yet.";

      return `
        <div class="${cls}">
          <div class="light-dot"></div>
          <div>
            <div class="stage-name">${escapeHtml(name)}</div>
            <div class="stage-note">${escapeHtml(label)}</div>
            <div class="stage-note mono">${escapeHtml(note)}</div>
          </div>
        </div>
      `;
    }).join("");

    $("stage-card").innerHTML = rows;
  }

  function renderWarningCount(review) {
    const warnings = review.warnings || [];
    const counts = {};
    warnings.forEach((w) => {
      const sev = w.severity || "unknown";
      counts[sev] = (counts[sev] || 0) + 1;
    });

    $("warning-count-card").innerHTML = `
      <div class="warning-mini-grid">
        <div class="warning-mini-item"><strong>${warnings.length}</strong><span>total</span></div>
        <div class="warning-mini-item"><strong>${counts.critical || 0}</strong><span>crit</span></div>
        <div class="warning-mini-item"><strong>${counts.major || 0}</strong><span>major</span></div>
        <div class="warning-mini-item"><strong>${counts.minor || 0}</strong><span>minor</span></div>
        <div class="warning-mini-item"><strong>${counts.info || 0}</strong><span>info</span></div>
      </div>
    `;
  }

  function renderWarnings(review) {
    const warnings = review.warnings || [];
    if (!warnings.length) {
      $("warnings-panel").innerHTML = `<div class="empty-note">No warnings reported by the V1 review checks.</div>`;
      return;
    }
    $("warnings-panel").innerHTML = warnings.map((w) => {
      const sev = String(w.severity || "info").toLowerCase();
      return `<div class="warning warning-${escapeHtml(sev)}">
        <h4>${escapeHtml((w.severity || "info").toUpperCase())}: ${escapeHtml(w.title)}</h4>
        <p>${escapeHtml(w.message)}</p>
        ${w.next_step ? `<p><strong>Next:</strong> ${escapeHtml(w.next_step)}</p>` : ""}
        ${w.details ? `<details><summary>Details</summary><pre>${escapeHtml(JSON.stringify(w.details, null, 2))}</pre></details>` : ""}
      </div>`;
    }).join("");
  }

  function renderConfig(review) {
    $("config-summary-panel").innerHTML = renderManualOrderedConfig(review);
  }

  function artifactUrl(relpath) {
    return `/api/review/file?run=${encodeURIComponent(state.selectedRun)}&rel=${encodeURIComponent(relpath)}`;
  }


  function artifactUrlFresh(relpath) {
    const base = artifactUrl(relpath);
    const token = state.mapStatus && state.mapStatus.updated_at
      ? encodeURIComponent(state.mapStatus.updated_at)
      : String(Date.now());

    return `${base}&v=${token}`;
  }


  function renderArtifacts(review) {
    const artifacts = review.artifacts || {};
    const images = artifacts.images || [];

    const imageHtml = images.length ? `
      <div class="artifact-grid">
        ${images.map((img) => {
          const rel = img.relpath || img.path;
          return `
            <div class="artifact-card">
              <a href="${artifactUrl(rel)}" target="_blank" rel="noopener">
                <img src="${artifactUrl(rel)}" alt="${escapeHtml(rel)}">
              </a>
              <div class="artifact-name mono">${escapeHtml(rel)}</div>
              <div class="artifact-name">${escapeHtml(formatBytes(img.size_bytes))}</div>
            </div>
          `;
        }).join("")}
      </div>
    ` : `<div class="empty-note">No image artifacts found yet. Completed postprocess quicklooks should appear here.</div>`;

    const other = {
      text: (artifacts.text || []).map((x) => x.relpath),
      netcdf: (artifacts.netcdf || []).map((x) => `${x.relpath} (${formatBytes(x.size_bytes)})`),
      geotiff: (artifacts.geotiff || []).map((x) => `${x.relpath} (${formatBytes(x.size_bytes)})`),
    };

    $("tab-artifacts").innerHTML = `
      ${imageHtml}

      <details style="margin-top: 16px;">
        <summary>Other discovered artifacts</summary>
        <div class="details-body">
          <pre>${escapeHtml(JSON.stringify(other, null, 2))}</pre>
        </div>
      </details>
    `;
  }

  function renderNetcdf(review) {
    const netcdf = review.netcdf || {};
    const blocks = Object.entries(netcdf).map(([name, info]) => {
      const available = info && info.available;
      const variables = info && info.variables ? Object.keys(info.variables) : [];
      return `<div class="artifact-card" style="margin-bottom:12px;">
        <h3>${escapeHtml(name)} ${available ? "✅" : "⚠️"}</h3>
        <div class="metric-row"><div class="metric-key">Available</div><div class="metric-val">${escapeHtml(available)}</div></div>
        <div class="metric-row"><div class="metric-key">Dims</div><div class="metric-val"><pre>${escapeHtml(JSON.stringify(info.dims || {}, null, 2))}</pre></div></div>
        <div class="metric-row"><div class="metric-key">Time</div><div class="metric-val"><pre>${escapeHtml(JSON.stringify(info.time || {}, null, 2))}</pre></div></div>
        <div class="metric-row"><div class="metric-key">Variables</div><div class="metric-val">${escapeHtml(variables.join(", "))}</div></div>
        ${info.error ? `<div class="warning warning-major"><p>${escapeHtml(info.error)}</p></div>` : ""}
      </div>`;
    }).join("");
    $("tab-netcdf").innerHTML = blocks || `<div class="empty-note">No NetCDF summary available.</div>`;
  }

  function renderChecks(review) {
    const inp = review.sfincs_inp || {};

    $("tab-checks").innerHTML = `
      <h3>Full model/sfincs.inp</h3>
      <p class="section-intro">
        This is the actual written SFINCS input file from the selected run. Use it as the source of truth for solver-facing runtime settings and file pointers.
      </p>
      <pre id="full-sfincs-inp-pre">Loading model/sfincs.inp…</pre>

      <details style="margin-top: 16px;">
        <summary>Parsed sfincs.inp highlights</summary>
        <div class="details-body">
          ${renderMetricRows(inp)}
        </div>
      </details>
    `;

    loadFullSfincsInp();
  }

  function renderLogs(review) {
    const logs = review.logs || {};
    if (!Object.keys(logs).length) {
      $("tab-logs").innerHTML = `<div class="empty-note">No log snippets found.</div>`;
      return;
    }
    $("tab-logs").innerHTML = Object.entries(logs).map(([name, row]) => `
      <details class="artifact-card" style="margin-bottom:10px;">
        <summary class="mono">${escapeHtml(name)}</summary>
        <pre>${escapeHtml(row.snippet || "")}</pre>
      </details>
    `).join("");
  }


  function renderSlurmStatus(status) {
    const stateLabel = String((status && status.state) || "missing").toLowerCase();

    let label = "Map products have not been generated yet.";
    let showSpinner = false;

    if (stateLabel === "submitted" || stateLabel === "queued") {
      label = "Slurm job sent. Waiting for the scheduler to start it.";
      showSpinner = true;
    } else if (stateLabel === "running") {
      label = "Slurm job running. Static map products are being built.";
      showSpinner = true;
    } else if (stateLabel === "ready") {
      label = "Slurm job done. Static map products are ready.";
      showSpinner = false;
    } else if (stateLabel === "failed" || stateLabel === "submit_failed") {
      label = "Map job failed. You can submit it again.";
      showSpinner = false;
    } else if (stateLabel === "sbatch_unavailable") {
      label = "Slurm submitter wrote the job file, but sbatch was not available from this process.";
      showSpinner = false;
    }

    return `
      <div class="review-spinner-row">
        ${showSpinner ? `<div class="review-spinner"></div>` : ""}
        <div>${escapeHtml(label)}</div>
      </div>
      ${status && status.job_id ? `<div class="map-status-line">Job ID: <span class="mono">${escapeHtml(status.job_id)}</span></div>` : ""}
    `;
  }

  async function postJson(url, payload) {
    const res = await fetch(url, {
      method: "POST",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload || {}),
    });

    const text = await res.text();
    let data;

    try {
      data = JSON.parse(text);
    } catch (err) {
      throw new Error(`Expected JSON from ${url}, got: ${text.slice(0, 300)}`);
    }

    if (!res.ok || data.ok === false) {
      const msg = data.error || data.stderr || data.message || `Request failed: ${res.status}`;
      throw new Error(msg);
    }

    return data;
  }

  function expectedMapLayerNote(layers) {
    const ids = new Set((layers || []).map((layer) => layer.layer_id));
    const missing = [];

    if (!ids.has("max_depth")) missing.push("max flood depth");
    if (!ids.has("max_water_level")) missing.push("max water level");

    if (!missing.length) return "";

    return `
      <div class="empty-note" style="margin-top: 12px;">
        Missing expected map layer(s): ${escapeHtml(missing.join(", "))}.
        The viewer is working, but this run currently only has the layer cards shown below.
      </div>
    `;
  }

  function renderMapLayerCard(layer) {
    const imageRel = layer.preview_relpath || layer.overlay_relpath;
    const legendRel = layer.legend_relpath;

    return `
      <div class="review-map-layer-card">
        <h3>${escapeHtml(layer.title || layer.layer_id)}</h3>
        <p class="section-intro">${escapeHtml(layer.description || "")}</p>

        <div class="review-map-layer-visual">
          <div class="review-map-main">
            ${imageRel ? `
              <a href="${artifactUrlFresh(imageRel)}" target="_blank" rel="noopener">
                <img src="${artifactUrlFresh(imageRel)}" alt="${escapeHtml(layer.title || layer.layer_id)}">
              </a>
            ` : `<div class="empty-note">No preview image was listed for this layer.</div>`}
          </div>

          <div class="review-map-legend">
            ${legendRel ? `
              <img src="${artifactUrlFresh(legendRel)}" alt="${escapeHtml(layer.title || layer.layer_id)} legend">
            ` : `<div class="empty-note">No legend</div>`}
          </div>
        </div>

        <div class="review-map-layer-meta">
          <div><strong>Variable:</strong> ${escapeHtml(layer.source_variable || "unknown")}</div>
          <div><strong>Units:</strong> ${escapeHtml(layer.units || "")}</div>
          <div><strong>Render range:</strong> ${escapeHtml(layer.render_vmin)} to ${escapeHtml(layer.render_vmax)}</div>
          <div><strong>Raw range:</strong> ${escapeHtml(layer.value_min)} to ${escapeHtml(layer.value_max)}</div>
          <div><strong>Shape:</strong> ${escapeHtml((layer.shape || []).join(" × "))}</div>
        </div>
      </div>
    `;
  }

  function renderReviewMapReady(status, manifest) {
    state.mapStatus = status || null;

    if (state.mapPollTimer) {
      window.clearTimeout(state.mapPollTimer);
      state.mapPollTimer = null;
    }
    
    const layers = (manifest && manifest.layers) || [];

    if (!layers.length) {
      $("review-tool-body").innerHTML = `
        <h3>Toggleable static maps</h3>
        ${renderSlurmStatus(status)}
        <div class="empty-note">
          The map job finished, but no layers were listed in the manifest.
        </div>
      `;
      return;
    }

    state.mapManifest = manifest;

    $("review-tool-body").innerHTML = `
      <h3>Toggleable static maps</h3>
      <p class="section-intro">
        Static map products built directly from sfincs_map.nc. Open any map image full-size by clicking it.
      </p>

      ${renderSlurmStatus(status)}
      ${expectedMapLayerNote(layers)}

      <div class="review-map-layer-grid">
        ${layers.map((layer) => renderMapLayerCard(layer)).join("")}
      </div>

      <div class="empty-note" style="margin-top: 12px;">
        Lat/lon point lookup will be wired after both static map layers are stable.
      </div>
    `;
  }

  function renderReviewMapMissing(status) {
    state.mapStatus = status || null;

    $("review-tool-body").innerHTML = `
      <h3>Toggleable static maps</h3>
      <p class="section-intro">
        Build static max-layer map products directly from sfincs_map.nc.
      </p>

      ${renderSlurmStatus(status)}

      <div class="review-map-controls">
        <button type="button" id="submit-review-map-cache-btn">Submit job</button>
      </div>
    `;

    $("submit-review-map-cache-btn").addEventListener("click", () => submitReviewMapCache(false));
  }

  function renderReviewMapProgress(status) {
    state.mapStatus = status || null;

    $("review-tool-body").innerHTML = ` `
      <h3>Toggleable static maps</h3>
      ${renderSlurmStatus(status)}
    `;

    if (state.mapPollTimer) {
      window.clearTimeout(state.mapPollTimer);
    }

    state.mapPollTimer = window.setTimeout(() => {
      if (state.activeReviewTool === "maps") {
        loadReviewMapStatus();
      }
    }, 10000);
  }

  function renderReviewMapFailed(status) {
    state.mapStatus = status || null;

    if (state.mapPollTimer) {
      window.clearTimeout(state.mapPollTimer);
      state.mapPollTimer = null;
    }

    $("review-tool-body").innerHTML = `
      <h3>Toggleable static maps</h3>
      ${renderSlurmStatus(status)}

      <div class="warning warning-major">
        <h4>Map job failed</h4>
        <p>${escapeHtml((status && status.error) || "Unknown map job error.")}</p>
        ${status && status.traceback ? `<details><summary>Traceback</summary><pre>${escapeHtml(status.traceback)}</pre></details>` : ""}
      </div>

      <div class="review-map-controls">
        <button type="button" id="submit-review-map-cache-btn">Submit job</button>
      </div>
    `;

    $("submit-review-map-cache-btn").addEventListener("click", () => submitReviewMapCache(false));
  }




  function renderReviewMapReadyButNoManifest(status, data) {
    state.mapStatus = status || null;

    if (state.mapPollTimer) {
      window.clearTimeout(state.mapPollTimer);
      state.mapPollTimer = null;
    }

    const panel = $("review-tool-body");
    if (!panel) return;

    panel.innerHTML = `
      <h3>Toggleable static maps</h3>
      ${renderSlurmStatus(status)}

      <div class="warning warning-major">
        <h4>Map job says done, but Review could not load the layer manifest</h4>
        <p>
          The job status is ready, but the browser did not receive usable layer metadata.
          This usually means layers_manifest.json is missing, empty, unreadable, or not where the Review API expects it.
        </p>
      </div>

      <details open>
        <summary>Status/API debug</summary>
        <div class="details-body">
          <pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>
        </div>
      </details>
    `;
  }


  async function loadReviewMapStatus() {
    if (!state.selectedRun) return;

    const panel = $("review-tool-body");
    if (!panel) return;

    panel.innerHTML = `
      <h3>Toggleable static maps</h3>
      <div class="review-spinner-row">
        <div class="review-spinner"></div>
        <div>Checking static map job status…</div>
      </div>
    `;

    try {
      const data = await fetchJson(`/api/review/maps/status?run=${encodeURIComponent(state.selectedRun)}`);
      const status = data.status || {};
      const manifest = data.manifest || null;
      const stateLabel = String(status.state || "missing").toLowerCase();

      if (stateLabel === "ready") {
        if (manifest && Array.isArray(manifest.layers) && manifest.layers.length) {
          renderReviewMapReady(status, manifest);
        } else {
          renderReviewMapReadyButNoManifest(status, data);
        }
      } else if (stateLabel === "failed" || stateLabel === "submit_failed") {
        renderReviewMapFailed(status);
      } else if (stateLabel === "submitted" || stateLabel === "queued" || stateLabel === "running") {
        renderReviewMapProgress(status);
      } else {
        renderReviewMapMissing(status);
      }
    } catch (err) {
      panel.innerHTML = `
        <h3>Toggleable static maps</h3>
        <div class="warning warning-major">
          <h4>Could not load map status</h4>
          <p>${escapeHtml(err.message)}</p>
        </div>
      `;
    }
  }

  async function submitReviewMapCache(force) {
    if (!state.selectedRun) return;

    const panel = $("review-tool-body");
    if (panel) {
      panel.innerHTML = `
        <h3>Toggleable static maps</h3>
        <div class="review-spinner-row">
          <div class="review-spinner"></div>
          <div>Sending static map job to Slurm…</div>
        </div>
      `;
    }

    try {
      const data = await postJson("/api/review/maps/submit", {
        run: state.selectedRun,
        force: Boolean(force),
      });

      const status = data.status || {};
      renderReviewMapProgress(status);
    } catch (err) {
      if (panel) {
        panel.innerHTML = `
          <h3>Toggleable static maps</h3>
          <div class="warning warning-major">
            <h4>Could not submit map job</h4>
            <p>${escapeHtml(err.message)}</p>
          </div>
          <div class="review-map-controls">
            <button type="button" id="submit-review-map-cache-btn">Submit job</button>
          </div>
        `;
        $("submit-review-map-cache-btn").addEventListener("click", () => submitReviewMapCache(false));
      }
    }
  }

  function setReviewTool(toolId) {
    state.activeReviewTool = toolId;

    document.querySelectorAll(".review-tool-choice").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tool === toolId);
    });

    const panel = $("review-tool-body");
    if (!panel) return;

    if (toolId === "maps") {
      loadReviewMapStatus();
      return;
    }

    if (toolId === "obs") {
      panel.innerHTML = `
        <h3>Obs points, lines, and gauge overlays</h3>
        <p class="section-intro">
          Planned next: observed-vs-modeled hydrographs, validation points, cross-section lines, and map-linked gauge selection.
        </p>
        <div class="empty-note">
          This will use the same Slurm/status/output pattern after static maps are complete.
        </div>
      `;
      return;
    }

    if (toolId === "animation") {
      panel.innerHTML = `
        <h3>Animation</h3>
        <p class="section-intro">
          Planned after graph overlays: Slurm-backed temporal renderer with cached video output and a Review-page player.
        </p>
        <div class="empty-note">
          This will use the same job/status/output pattern as static maps, but for time-varying frames and a final video.
        </div>
      `;
      return;
    }
  }

  function wireReviewToolButtons() {
    document.querySelectorAll(".review-tool-choice").forEach((btn) => {
      btn.addEventListener("click", () => {
        setReviewTool(btn.dataset.tool);
      });
    });
  }

  function renderFuture(review) {
    const mapInfo = review.netcdf && review.netcdf["sfincs_map.nc"];
    const hisInfo = review.netcdf && review.netcdf["sfincs_his.nc"];
    const mapVars = mapInfo && mapInfo.variables ? Object.keys(mapInfo.variables) : [];
    const hisVars = hisInfo && hisInfo.variables ? Object.keys(hisInfo.variables) : [];

    $("tab-future").innerHTML = `
      <div class="future-grid">
        <div class="review-tool-choice-row">
          <button type="button" class="review-tool-choice active" data-tool="maps">
            <strong>1. Toggleable static maps</strong>
            <span>max flood depth + max water level</span>
          </button>

          <button type="button" class="review-tool-choice" data-tool="obs">
            <strong>2. Obs / gauges</strong>
            <span>observed vs modeled graphs</span>
          </button>

          <button type="button" class="review-tool-choice" data-tool="animation">
            <strong>3. Animation</strong>
            <span>Slurm-backed temporal renderer</span>
          </button>
        </div>

        <div class="review-tool-open-panel" id="review-tool-body">
          <div class="empty-note">Choose an interactive review product.</div>
        </div>
      </div>

      <details style="margin-top: 16px;">
        <summary>Available map/history variables for future tools</summary>
        <div class="details-body">
          <h3>sfincs_map.nc variables</h3>
          <pre>${escapeHtml(JSON.stringify(mapVars, null, 2))}</pre>
          <h3>sfincs_his.nc variables</h3>
          <pre>${escapeHtml(JSON.stringify(hisVars, null, 2))}</pre>
        </div>
      </details>
    `;

    wireReviewToolButtons();
    setReviewTool("maps");
  }

  function wireTabs() {
    document.querySelectorAll(".tab-button").forEach((btn) => {
      btn.addEventListener("click", () => {
        const tab = btn.getAttribute("data-tab");
        document.querySelectorAll(".tab-button").forEach((b) => b.classList.remove("active"));
        document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
        btn.classList.add("active");
        const panel = $(`tab-${tab}`);
        if (panel) panel.classList.add("active");
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    wireTabs();
    $("refresh-runs-btn").addEventListener("click", loadRuns);
    $("load-review-btn").addEventListener("click", loadReview);
    loadRuns();
  });
})();
