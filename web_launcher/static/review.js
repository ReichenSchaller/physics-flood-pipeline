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
  animationPollTimer: null,
  mapJobStartedThisView: false,
  obsStatus: null,
  obsManifest: null,
  obsMapManifest: null,
  obsMetrics: null,
  obsPollTimer: null,
  obsJobStartedThisView: false,
  obsValidationCsvPath: "",

  obsTimeseries: null,
  obsTimeseriesByKey: new Map(),
  obsTimeseriesLoading: false,
  obsTimeseriesError: "",
  selectedObsTimeseriesKey: "",
  selectedObsTimeseriesFamilyKey: "",
  selectedObsTimeseriesMetric: "auto",
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

  function clearReviewTimer(timerName) {
    if (state[timerName]) {
      window.clearTimeout(state[timerName]);
      state[timerName] = null;
    }
  }

  function clearInactiveReviewToolTimers(activeTool) {
    if (activeTool !== "maps") clearReviewTimer("mapPollTimer");
    if (activeTool !== "obs") clearReviewTimer("obsPollTimer");
    if (activeTool !== "animation") clearReviewTimer("animationPollTimer");
  }

  function isCurrentReviewTool(toolId, runName) {
    return state.activeReviewTool === toolId && state.selectedRun === runName;
  }


  function clearInteractiveReviewOutput() {
    state.mapManifest = null;
    state.mapStatus = null;
    state.activeReviewTool = "maps";
    state.mapJobStartedThisView = false;
    state.obsStatus = null;
    state.obsMapManifest = null;
    state.obsManifest = null;
    state.obsMetrics = null;
    state.obsTimeseries = null;
    state.obsTimeseriesByKey = new Map();
    state.obsTimeseriesLoading = false;
    state.obsTimeseriesError = "";
    state.obsValidationCsvPath = "";
    state.selectedObsTimeseriesKey = "";
    state.selectedObsTimeseriesFamilyKey = "";
    state.selectedObsTimeseriesMetric = "auto";

    clearReviewTimer("mapPollTimer");
    clearReviewTimer("obsPollTimer");
    clearReviewTimer("animationPollTimer");

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



  function appUrl(path) {
    const clean = String(path || "").replace(/^\/+/, "");

    // If the app is served through Open OnDemand like:
    // /node/<host>/<port>/review
    // we need /node/<host>/<port>/api/... not /api/...
    const currentPath = window.location.pathname || "/";
    const reviewIdx = currentPath.lastIndexOf("/review");

    let root = "/";
    if (reviewIdx >= 0) {
      root = currentPath.slice(0, reviewIdx + 1);
    } else {
      root = currentPath.replace(/\/[^/]*$/, "/");
    }

    return `${root}${clean}`;
  }


  function normalizeAppFetchUrl(url) {
    const raw = String(url || "");

    if (/^https?:\/\//i.test(raw)) {
      return raw;
    }

    if (raw.startsWith("/api/")) {
      return appUrl(raw.slice(1));
    }

    if (raw.startsWith("api/")) {
      return appUrl(raw);
    }

    return raw;
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

  function escapeAttr(value) {
    return escapeHtml(String(value || "")).replace(/"/g, "&quot;");
  }


  function formatBytes(n) {
    const value = Number(n || 0);
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }


  function revokeReviewAnimationBlobUrls() {
    if (!window.__reviewAnimationBlobUrls) {
      window.__reviewAnimationBlobUrls = [];
      return;
    }

    for (const url of window.__reviewAnimationBlobUrls) {
      try {
        URL.revokeObjectURL(url);
      } catch (err) {
        // ignore cleanup failures
      }
    }

    window.__reviewAnimationBlobUrls = [];
  }


  async function hydrateReviewAnimationVideos() {
    const videos = document.querySelectorAll("video[data-review-animation-src]");
    if (!videos.length) return;

    revokeReviewAnimationBlobUrls();

    for (const video of videos) {
      const src = video.getAttribute("data-review-animation-src");
      const noteId = video.getAttribute("data-review-animation-note-id");
      const note = noteId ? document.getElementById(noteId) : null;

      if (!src) continue;

      video.addEventListener("error", () => {
        const err = video.error;
        const code = err ? err.code : "unknown";
        const msg = err && err.message ? err.message : "Browser could not decode video source.";
        if (note) {
          note.textContent = `Video element error ${code}: ${msg}`;
        }
      }, { once: true });

      try {
        if (note) {
          note.textContent = "Downloading full MP4 for embedded playback...";
        }

        const res = await fetch(src, {
          method: "GET",
          cache: "no-store",
          headers: {
            "Accept": "video/mp4,*/*",
          },
        });

        const contentType = res.headers.get("content-type") || "unknown";

        if (!res.ok) {
          const text = await res.text();
          throw new Error(`HTTP ${res.status}: ${text.slice(0, 300)}`);
        }

        const buffer = await res.arrayBuffer();

        if (!buffer || buffer.byteLength === 0) {
          throw new Error("Downloaded video is empty.");
        }

        const firstBytes = Array.from(new Uint8Array(buffer.slice(0, 16)));
        const firstText = firstBytes
          .map((b) => (b >= 32 && b <= 126 ? String.fromCharCode(b) : "."))
          .join("");

        const looksLikeMp4 = firstText.includes("ftyp");
        const looksLikeWebm =
          firstBytes.length >= 4 &&
          firstBytes[0] === 0x1a &&
          firstBytes[1] === 0x45 &&
          firstBytes[2] === 0xdf &&
          firstBytes[3] === 0xa3;

        if (!looksLikeMp4 && !looksLikeWebm) {
          throw new Error(
            `Downloaded response does not look like MP4/WebM. content-type=${contentType}, first bytes=${firstText}`
          );
        }

        const mimeType = looksLikeWebm ? "video/webm" : "video/mp4";
        const blob = new Blob([buffer], { type: mimeType });

        const dataUrl = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result);
          reader.onerror = () => reject(reader.error || new Error("FileReader failed."));
          reader.readAsDataURL(blob);
        });

        video.removeAttribute("data-review-animation-src");
        video.src = dataUrl;
        video.load();

        if (note) {
          note.textContent = `Loaded ${formatBytes(buffer.byteLength)} ${looksLikeWebm ? "WebM" : "MP4"} into page memory. content-type=${contentType}, first bytes=${firstText}`;
        }
      } catch (err) {
        if (note) {
          note.textContent = `Could not prepare embedded video: ${err.message || err}`;
        }
      }
    }
  }

  function animationVideoUrl(relpath) {
    const params = new URLSearchParams({
      run: state.selectedRun || "",
      path: relpath || "",
      t: String(Date.now()),
    });

    return appUrl(`api/review/animation/video?${params.toString()}`);
  }


  function artifactUrlFresh(relpath) {
    const base = artifactUrl(relpath);
    const token = state.mapStatus && state.mapStatus.updated_at
      ? encodeURIComponent(state.mapStatus.updated_at)
      : String(Date.now());

    return `${base}&v=${token}`;
  }


  async function getJson(url) {
    const freshUrl = `${normalizeAppFetchUrl(url)}${String(url).includes("?") ? "&" : "?"}_=${Date.now()}`;

    const res = await fetch(freshUrl, {
      method: "GET",
      cache: "no-store",
      headers: {
        "Accept": "application/json",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
      },
    });

    const text = await res.text();
    let data = null;

    try {
      data = text ? JSON.parse(text) : {};
    } catch (err) {
      throw new Error(`Expected JSON from ${url}, got: ${text.slice(0, 300)}`);
    }

    if (!res.ok || data.ok === false) {
      throw new Error(data.error || data.message || `Request failed: ${res.status}`);
    }

    return data;
  }


  async function postJson(url, payload) {
    const res = await fetch(normalizeAppFetchUrl(url), {
      method: "POST",
      headers: {
        "Accept": "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload || {}),
    });

    const text = await res.text();
    let data = null;

    try {
      data = text ? JSON.parse(text) : {};
    } catch (err) {
      throw new Error(`Expected JSON from ${url}, got: ${text.slice(0, 300)}`);
    }

    if (!res.ok || data.ok === false) {
      throw new Error(data.error || data.message || `Request failed: ${res.status}`);
    }

    return data;
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


  function renderSlurmStatus(status, productLabel = "review products") {
    const stateLabel = String((status && status.state) || "missing").toLowerCase();

    let label = `${productLabel} have not been generated yet.`;
    let showSpinner = false;

    if (["submitted", "queued", "pending", "submitting"].includes(stateLabel)) {
      label = `Slurm job sent. Waiting for the scheduler to start ${productLabel}.`;
      showSpinner = true;
    } else if (stateLabel === "running") {
      label = `Slurm job running. ${productLabel} are being built.`;
      showSpinner = true;
    } else if (stateLabel === "ready") {
      label = `Slurm job done. ${productLabel} are ready.`;
      showSpinner = false;
    } else if (["failed", "submit_failed", "error"].includes(stateLabel)) {
      label = `${productLabel} job failed. You can submit it again.`;
      showSpinner = false;
    } else if (stateLabel === "sbatch_unavailable") {
      label = "Slurm submitter wrote the job file, but sbatch was not available from this process.";
      showSpinner = false;
    }

    const message = status && status.message ? String(status.message) : "";

    return `
      <div class="review-spinner-row">
        ${showSpinner ? `<div class="review-spinner"></div>` : ""}
        <div>${escapeHtml(label)}</div>
      </div>
      ${message ? `<div class="map-status-line">${escapeHtml(message)}</div>` : ""}
      ${status && status.job_id ? `<div class="map-status-line">Job ID: <span class="mono">${escapeHtml(status.job_id)}</span></div>` : ""}
    `;
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

  function overlayMeta(key) {
    const overlays = (state.mapManifest && state.mapManifest.optional_overlays) || {};
    const item = overlays[key] || null;
    if (!item || !item.relpath) return null;
    return item;
  }

  function renderOverlayToggle(key, label, item, checked) {
    const disabled = item ? "" : "disabled";
    const rowClass = item ? "review-toggle-row" : "review-toggle-row disabled";
    const isChecked = item && checked ? "checked" : "";

    return `
      <label class="${rowClass}">
        <span>${escapeHtml(label)}</span>
        <input type="checkbox" data-toggle="${escapeHtml(key)}" ${isChecked} ${disabled}>
      </label>
    `;
  }

  function renderMapLayerCard(layer) {
    const modelRel = layer.overlay_relpath || layer.preview_relpath;
    const haloRel = layer.halo_relpath || null;
    const legendRel = layer.legend_relpath;

    const satellite = overlayMeta("satellite_background");
    const activeArea = overlayMeta("model_active_area");
    const obsPoints = overlayMeta("obs_points");
    const obsLines = overlayMeta("obs_lines");

    const safeId = String(layer.layer_id || "layer")
      .replace(/[^A-Za-z0-9_-]/g, "_");

    return `
      <div class="review-map-layer-card" data-layer-card="${escapeHtml(safeId)}">
        <h3>${escapeHtml(layer.title || layer.layer_id)}</h3>
        <p class="section-intro">${escapeHtml(layer.description || "")}</p>

        <div class="review-map-layer-visual">
          <div class="review-toggle-bank">
            <h4>Layer toggles</h4>

            ${renderOverlayToggle("satellite", "Satellite background", satellite, false)}

            <label class="review-toggle-row slider-row ${satellite ? "" : "disabled"}">
              <span>Satellite opacity</span>
              <input type="range" data-toggle="satelliteOpacity" min="0" max="100" value="100" ${satellite ? "" : "disabled"}>
            </label>


            ${renderOverlayToggle("activeArea", "Model active area", activeArea, false)}

            <label class="review-toggle-row">
              <span>Flood layer</span>
              <input type="checkbox" data-toggle="model" checked>
            </label>
            
            <label class="review-toggle-row">
              <span>Flood halo</span>
              <input type="checkbox" data-toggle="halo" ${haloRel ? "checked" : "disabled"}>
            </label>
            
            <label class="review-toggle-row slider-row">
              <span>Flood opacity</span>
              <input type="range" data-toggle="opacity" min="0" max="100" value="100">
            </label>

            ${renderOverlayToggle("obsPoints", "Obs points", obsPoints, true)}
            ${renderOverlayToggle("obsLines", "Obs lines / gauges", obsLines, true)}
          </div>

          <div class="review-layer-stage">
            ${satellite ? `
              <img
                class="review-layer-base"
                data-layer-img="satellite"
                src="${artifactUrlFresh(satellite.relpath)}"
                alt="Satellite background"
                style="display:none;"
              >
            ` : ""}

            ${activeArea ? `
              <img
                class="review-layer-overlay"
                data-layer-img="activeArea"
                src="${artifactUrlFresh(activeArea.relpath)}"
                alt="Model active area"
                style="display:none;"
              >
            ` : ""}

            ${modelRel ? `
              <a href="${artifactUrlFresh(modelRel)}" target="_blank" rel="noopener" style="position:absolute; inset:0; z-index:20;">
                <span aria-hidden="true"></span>
              </a>
              <img
                class="review-layer-model"
                data-layer-img="model"
                src="${artifactUrlFresh(modelRel)}"
                alt="${escapeHtml(layer.title || layer.layer_id)}"
              >
              ${haloRel ? `
                <img
                  class="review-layer-overlay review-layer-halo"
                  data-layer-img="halo"
                  src="${artifactUrlFresh(haloRel)}"
                  alt="${escapeHtml(layer.title || layer.layer_id)} halo"
                >
              ` : ""}
            ` : `<div class="empty-note">No model image was listed for this layer.</div>`}

            ${obsPoints ? `
              <img
                class="review-layer-overlay review-layer-points"
                data-layer-img="obsPoints"
                src="${artifactUrlFresh(obsPoints.relpath)}"
                alt="Observation points"
              >
            ` : ""}

            ${obsLines ? `
              <img
                class="review-layer-overlay review-layer-lines"
                data-layer-img="obsLines"
                src="${artifactUrlFresh(obsLines.relpath)}"
                alt="Observation lines and gauges"
              >
            ` : ""}
          </div>

          <div class="review-map-constant-panel">
            <h4>Legend and info</h4>

            <div class="review-map-legend">
              ${legendRel ? `
                <img src="${artifactUrlFresh(legendRel)}" alt="${escapeHtml(layer.title || layer.layer_id)} legend">
              ` : `<div class="empty-note">No legend</div>`}
            </div>

            <div class="review-map-layer-meta">
              <div><strong>Variable:</strong> ${escapeHtml(layer.source_variable || "unknown")}</div>
              <div><strong>Units:</strong> ${escapeHtml(layer.units || "")}</div>
              <div><strong>Render range:</strong> ${escapeHtml(layer.render_vmin)} to ${escapeHtml(layer.render_vmax)}</div>
              <div><strong>Raw range:</strong> ${escapeHtml(layer.value_min)} to ${escapeHtml(layer.value_max)}</div>
              <div><strong>Shape:</strong> ${escapeHtml((layer.shape || []).join(" × "))}</div>
              ${layer.derived_from ? `
                <div><strong>Derived:</strong> ${escapeHtml(JSON.stringify(layer.derived_from))}</div>
              ` : ""}
            </div>
          </div>
        </div>
      </div>
    `;
  }



  function wireMapLayerToggles() {
    document.querySelectorAll(".review-map-layer-card").forEach((card) => {
      const satelliteImg = card.querySelector('[data-layer-img="satellite"]');
      const activeAreaImg = card.querySelector('[data-layer-img="activeArea"]');
      const modelImg = card.querySelector('[data-layer-img="model"]');
      const haloImg = card.querySelector('[data-layer-img="halo"]');
      const obsPointsImg = card.querySelector('[data-layer-img="obsPoints"]');
      const obsLinesImg = card.querySelector('[data-layer-img="obsLines"]');

      const satelliteToggle = card.querySelector('[data-toggle="satellite"]');
      const satelliteOpacitySlider = card.querySelector('[data-toggle="satelliteOpacity"]');
      const activeAreaToggle = card.querySelector('[data-toggle="activeArea"]');
      const modelToggle = card.querySelector('[data-toggle="model"]');
      const haloToggle = card.querySelector('[data-toggle="halo"]');
      const opacitySlider = card.querySelector('[data-toggle="opacity"]');
      const obsPointsToggle = card.querySelector('[data-toggle="obsPoints"]');
      const obsLinesToggle = card.querySelector('[data-toggle="obsLines"]');

      function showByToggle(img, toggle) {
        if (!img) return;
        img.style.display = toggle && toggle.checked ? "block" : "none";
      }

      function apply() {
        const opacity = opacitySlider ? Number(opacitySlider.value || 100) / 100 : 1;
        const satelliteOpacity = satelliteOpacitySlider ? Number(satelliteOpacitySlider.value || 100) / 100 : 1;
        
        showByToggle(satelliteImg, satelliteToggle);
        showByToggle(activeAreaImg, activeAreaToggle);
        showByToggle(haloImg, haloToggle);
        showByToggle(obsPointsImg, obsPointsToggle);
        showByToggle(obsLinesImg, obsLinesToggle);

        if (satelliteImg) satelliteImg.style.opacity = String(satelliteOpacity);
        if (activeAreaImg) activeAreaImg.style.opacity = "1";
        if (haloImg) haloImg.style.opacity = "1";
        if (obsPointsImg) obsPointsImg.style.opacity = "1";
        if (obsLinesImg) obsLinesImg.style.opacity = "1";

        if (modelImg) {
          modelImg.style.display = modelToggle && modelToggle.checked ? "block" : "none";
          modelImg.style.opacity = String(opacity);
        }
      }

      [
        satelliteToggle,
        satelliteOpacitySlider,
        activeAreaToggle,
        modelToggle,
        haloToggle,
        opacitySlider,
        obsPointsToggle,
        obsLinesToggle,
      ].forEach((el) => {
        if (!el) return;
        el.addEventListener("input", apply);
        el.addEventListener("change", apply);
      });

      apply();
    });
  }






  function renderReviewMapReady(status, manifest) {
    state.mapStatus = status || null;
    state.mapJobStartedThisView = true;

    if (state.mapPollTimer) {
      window.clearTimeout(state.mapPollTimer);
      state.mapPollTimer = null;
    }
    
    const layers = (manifest && manifest.layers) || [];

    if (!layers.length) {
      $("review-tool-body").innerHTML = `
        <h3>Toggleable static maps</h3>
        ${renderSlurmStatus(status, "static map products")}
        <div class="empty-note">
          The map job finished, but no layers were listed in the manifest.
        </div>
      `;
      wireMapLayerToggles();
      return;
    }

    state.mapManifest = manifest;

    $("review-tool-body").innerHTML = `
      <h3>Toggleable static maps</h3>
      <p class="section-intro">
        Static map products built directly from sfincs_map.nc. Open any map image full-size by clicking it.
      </p>

      ${renderSlurmStatus(status, "static map products")}
      ${expectedMapLayerNote(layers)}

      <div class="review-map-layer-grid">
        ${layers.map((layer) => renderMapLayerCard(layer)).join("")}
      </div>

      <div class="empty-note" style="margin-top: 12px;">
        Lat/lon point lookup will be wired after both static map layers are stable.
      </div>
    `;

    wireMapLayerToggles();
  }



  function renderStaticMapSubmitPrompt() {
    const panel = $("review-tool-body");
    if (!panel) return;

    panel.innerHTML = `
      <h3>Toggleable static maps</h3>
      <p class="section-intro">
        Build static max-layer map products directly from sfincs_map.nc for this selected run.
      </p>

      <div class="review-map-controls">
        <button type="button" id="submit-review-map-cache-btn">Submit job</button>
        <button type="button" class="secondary" id="run-review-map-local-btn">Run locally</button>
      </div>
    `;

    $("submit-review-map-cache-btn").addEventListener("click", () => submitReviewMapCache(true));
    const localBtn = $("run-review-map-local-btn");
    if (localBtn) {
      localBtn.addEventListener("click", () => submitReviewMapCache(true, true));
    }
  }



  function renderReviewMapMissing(status) {
    state.mapStatus = status || null;

    $("review-tool-body").innerHTML = `
      <h3>Toggleable static maps</h3>
      <p class="section-intro">
        Build static max-layer map products directly from sfincs_map.nc.
      </p>

      ${renderSlurmStatus(status, "static map products")}

      <div class="review-map-controls">
        <button type="button" id="submit-review-map-cache-btn">Submit job</button>
        <button type="button" class="secondary" id="run-review-map-local-btn">Run locally</button>
      </div>
    `;

    $("submit-review-map-cache-btn").addEventListener("click", () => submitReviewMapCache(false));
    const localBtn = $("run-review-map-local-btn");
    if (localBtn) {
      localBtn.addEventListener("click", () => submitReviewMapCache(false, true));
    }
  }

  function renderReviewMapProgress(status) {
    state.mapStatus = status || null;

    $("review-tool-body").innerHTML = `
      <h3>Toggleable static maps</h3>
      ${renderSlurmStatus(status, "static map products")}
    `;

    if (state.mapPollTimer) {
      window.clearTimeout(state.mapPollTimer);
    }

    state.mapPollTimer = window.setTimeout(() => {
      if (state.activeReviewTool === "maps") {
        loadReviewMapStatus();
      }
    }, 3000);
  }

  function renderReviewMapFailed(status) {
    state.mapStatus = status || null;

    if (state.mapPollTimer) {
      window.clearTimeout(state.mapPollTimer);
      state.mapPollTimer = null;
    }

    $("review-tool-body").innerHTML = `
      <h3>Toggleable static maps</h3>
      ${renderSlurmStatus(status, "static map products")}

      <div class="warning warning-major">
        <h4>Map job failed</h4>
        <p>${escapeHtml((status && status.error) || "Unknown map job error.")}</p>
        ${status && status.traceback ? `<details><summary>Traceback</summary><pre>${escapeHtml(status.traceback)}</pre></details>` : ""}
      </div>

      <div class="review-map-controls">
        <button type="button" id="submit-review-map-cache-btn">Submit job</button>
        <button type="button" class="secondary" id="run-review-map-local-btn">Run locally</button>
      </div>
    `;

    $("submit-review-map-cache-btn").addEventListener("click", () => submitReviewMapCache(false));
    const localBtn = $("run-review-map-local-btn");
    if (localBtn) {
      localBtn.addEventListener("click", () => submitReviewMapCache(false, true));
    }
  }




  function renderReviewMapReadyButNoManifest(status, data) {
    state.mapStatus = status || null;

    const panel = $("review-tool-body");
    if (!panel) return;

    panel.innerHTML = `
      <h3>Toggleable static maps</h3>
      <div class="review-spinner-row">
        <div class="review-spinner"></div>
        <div>Static map job finished. Waiting for layer manifest to appear…</div>
      </div>

      <details>
        <summary>Status/API debug</summary>
        <div class="details-body">
          <pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>
        </div>
      </details>
    `;

    if (state.mapPollTimer) {
      window.clearTimeout(state.mapPollTimer);
    }

    state.mapPollTimer = window.setTimeout(() => {
      if (state.activeReviewTool === "maps") {
        loadReviewMapStatus();
      }
    }, 3000);
  }



  function formatSeconds(seconds) {
    const s = Number(seconds || 0);
    if (!Number.isFinite(s)) return "unknown";
    if (s < 60) return `${s.toFixed(1)} sec`;
    const m = Math.floor(s / 60);
    const rem = s - m * 60;
    return `${m} min ${rem.toFixed(0)} sec`;
  }

  function currentAnimationInputs() {
    const hpfEl = $("animation-hours-per-frame");
    const fpsEl = $("animation-fps");

    return {
      hours_per_frame: hpfEl ? Number(hpfEl.value || 6) : 6,
      fps: fpsEl ? Number(fpsEl.value || 10) : 10,
    };
  }

  async function loadReviewAnimationInfo() {
    if (!state.selectedRun || state.activeReviewTool !== "animation") return;

    const runAtStart = state.selectedRun;
    const panel = $("review-tool-body");
    if (panel) {
      panel.innerHTML = `
        <h3>Animation</h3>
        <div class="review-spinner-row">
          <div class="review-spinner"></div>
          <div>Reading animation time axis…</div>
        </div>
      `;
    }

    const params = new URLSearchParams({
      run: runAtStart,
      hours_per_frame: "6",
      fps: "10",
    });

    try {
      const data = await getJson(`/api/review/animation/info?${params.toString()}`);
      if (!isCurrentReviewTool("animation", runAtStart)) return;

      renderReviewAnimationPanel(data);
    } catch (err) {
      if (!isCurrentReviewTool("animation", runAtStart)) return;

      if (panel) {
        panel.innerHTML = `
          <h3>Animation</h3>
          <div class="warning warning-major">
            <h4>Could not read animation info</h4>
            <p>${escapeHtml(err.message)}</p>
          </div>
        `;
      }
    }
  }

  async function refreshReviewAnimationEstimate() {
    if (!state.selectedRun || state.activeReviewTool !== "animation") return;

    const runAtStart = state.selectedRun;
    const inputs = currentAnimationInputs();
    const params = new URLSearchParams({
      run: runAtStart,
      hours_per_frame: String(inputs.hours_per_frame),
      fps: String(inputs.fps),
    });

    try {
      const data = await getJson(`/api/review/animation/info?${params.toString()}`);
      if (!isCurrentReviewTool("animation", runAtStart)) return;

      renderReviewAnimationPanel(data, true);
    } catch (err) {
      if (!isCurrentReviewTool("animation", runAtStart)) return;

      const box = $("animation-estimate-box");
      if (box) {
        box.innerHTML = `<div class="warning warning-major"><p>${escapeHtml(err.message)}</p></div>`;
      }
    }
  }
  
  function renderAnimationExistingList(animations) {
    if (!animations || !animations.length) {
      return `<div class="empty-note">No saved animations yet for this run.</div>`;
    }

    return `
      <div class="animation-list">
        ${animations.slice().reverse().map((item) => `
          <div class="animation-list-item">
            <strong>${escapeHtml(item.output_relpath || "animation")}</strong>
            <span>
              ${escapeHtml(String(item.hours_per_frame))} hr/frame ·
              ${escapeHtml(String(item.fps))} fps ·
              ${escapeHtml(String(item.frame_count))} frames ·
              ${escapeHtml(formatSeconds(item.video_seconds))}
            </span>
          </div>
        `).join("")}
      </div>
    `;
  }

  function renderLatestAnimation(latest) {
    if (!latest || !latest.output_relpath) return "";

    const mp4Rel = latest.output_relpath || latest.relpath || latest.path || "";
    const browserRel = (latest.webm_relpath || latest.browser_relpath || mp4Rel.replace(/\.mp4$/i, ".webm"));
    const videoSrc = animationVideoUrl(browserRel);

    return `
      <div class="review-animation-player">
        <video
          class="review-animation-video"
          controls
          preload="metadata"
          data-review-animation-src="${escapeAttr(videoSrc)}"
          data-review-animation-note-id="review-animation-video-load-note"
        ></video>

        <div class="empty-note" id="review-animation-video-load-note">
          Preparing browser playback video...
        </div>

        <div class="empty-note">
          Browser playback file:
          <span class="mono">${escapeHtml(browserRel)}</span>
        </div>

        <div class="empty-note">
          Source animation:
          <span class="mono">${escapeHtml(latest.output_relpath)}</span>
          ${latest.size_bytes ? ` · ${escapeHtml(formatBytes(latest.size_bytes))}` : ""}
        </div>
      </div>
    `;
  }

  function renderReviewAnimationPanel(data, preserveInputs) {
    const panel = $("review-tool-body");
    if (!panel) return;

    const oldInputs = preserveInputs ? currentAnimationInputs() : null;

    const hpf = oldInputs ? oldInputs.hours_per_frame : Number(data.hours_per_frame || 6);
    const fps = oldInputs ? oldInputs.fps : Number(data.fps || 10);
    const status = data.status || {};
    const existing = data.existing_animations || [];
    const latest = data.latest_animation || null;

    panel.innerHTML = `
      <h3>Animation</h3>
      <p class="section-intro">
        Build a playable MP4 showing flood depth through time:
        <code>depth(t) = max(zs(t) - zb, 0)</code>.
      </p>

      ${["running", "submitted", "pending", "submitting"].includes(String(status.state || "").toLowerCase())
        ? `<div class="empty-note">Previous animation status: ${escapeHtml(status.message || status.state || "unknown")}</div>`
        : renderSlurmStatus(status)}

      <div class="review-map-controls review-animation-controls">
        <label>
          <span>Hours per frame</span>
          <input type="number" id="animation-hours-per-frame" min="0.5" step="0.5" value="${escapeHtml(String(hpf))}">
        </label>

        <label>
          <span>Frames per second</span>
          <input type="number" id="animation-fps" min="1" max="30" step="1" value="${escapeHtml(String(fps))}">
        </label>

        <button type="button" id="submit-review-animation-btn">Run animation job</button>
      </div>

      <div id="animation-estimate-box" class="details-body">
        <h4>Animation estimate</h4>
        <p>
          Source frames: <strong>${escapeHtml(String(data.source_time_count || "unknown"))}</strong>
          ${data.native_spacing_hours ? ` · native spacing: <strong>${escapeHtml(String(data.native_spacing_hours.p50))} hr</strong>` : ""}
        </p>
        <p>
          Selected frames: <strong>${escapeHtml(String(data.frame_count || "unknown"))}</strong>
          · estimated video length:
          <strong>${escapeHtml(formatSeconds(data.video_seconds))}</strong>
        </p>
        <p>
          Time range:
          <strong>${escapeHtml(data.first_selected_label || data.first_time_label || "unknown")}</strong>
          to
          <strong>${escapeHtml(data.last_selected_label || data.last_time_label || "unknown")}</strong>
        </p>
      </div>

      ${renderLatestAnimation(latest)}

      <details style="margin-top: 14px;">
        <summary>Saved animations in this run</summary>
        <div class="details-body">
          ${renderAnimationExistingList(existing)}
        </div>
      </details>
    `;
    hydrateReviewAnimationVideos();

    $("animation-hours-per-frame").addEventListener("change", refreshReviewAnimationEstimate);
    $("animation-fps").addEventListener("change", refreshReviewAnimationEstimate);
    $("submit-review-animation-btn").addEventListener("click", submitReviewAnimation);
  }

  function renderReviewAnimationProgress(status) {
    const panel = $("review-tool-body");
    if (!panel) return;

    panel.innerHTML = `
      <h3>Animation</h3>
      ${renderSlurmStatus(status, "animation products")}
      <div class="empty-note">
        Animation status refreshes automatically while the Slurm job is queued or running.
      </div>
    `;

    if (state.animationPollTimer) {
      window.clearTimeout(state.animationPollTimer);
    }

    state.animationPollTimer = window.setTimeout(loadReviewAnimationStatus, 3000);
  }

  async function loadReviewAnimationStatus() {
    if (!state.selectedRun || state.activeReviewTool !== "animation") return;

    const runAtStart = state.selectedRun;
    const params = new URLSearchParams({ run: runAtStart });

    try {
      const data = await getJson(`/api/review/animation/status?${params.toString()}`);
      if (!isCurrentReviewTool("animation", runAtStart)) return;

      const status = data.status || {};
      const stateText = String(status.state || "").toLowerCase();

      if (stateText === "ready") {
        await refreshReviewAnimationEstimate();
        return;
      }

      if (["failed", "submit_failed", "error"].includes(stateText)) {
        const panel = $("review-tool-body");
        if (panel) {
          panel.innerHTML = `
            <h3>Animation</h3>
            ${renderSlurmStatus(status, "animation products")}
            <div class="warning warning-major">
              <h4>Animation job failed</h4>
              <p>${escapeHtml(status.error || "Unknown animation job error.")}</p>
              ${status.traceback ? `<details><summary>Traceback</summary><pre>${escapeHtml(status.traceback)}</pre></details>` : ""}
            </div>
          `;
        }
        return;
      }

      renderReviewAnimationProgress(status);

    } catch (err) {
      if (!isCurrentReviewTool("animation", runAtStart)) return;

      const panel = $("review-tool-body");
      if (panel) {
        panel.innerHTML = `
          <h3>Animation</h3>
          <div class="warning warning-major">
            <h4>Could not load animation status</h4>
            <p>${escapeHtml(err.message)}</p>
          </div>
        `;
      }
    }
  }

  async function submitReviewAnimation() {
    if (!state.selectedRun || state.activeReviewTool !== "animation") return;

    const runAtSubmit = state.selectedRun;
    const inputs = currentAnimationInputs();
    const panel = $("review-tool-body");

    if (panel) {
      panel.innerHTML = `
        <h3>Animation</h3>
        <div class="review-spinner-row">
          <div class="review-spinner"></div>
          <div>Submitting animation job to Slurm…</div>
        </div>
      `;
    }

    try {
      const data = await postJson("/api/review/animation/submit", {
        run: runAtSubmit,
        hours_per_frame: inputs.hours_per_frame,
        fps: inputs.fps,
      });

      if (!isCurrentReviewTool("animation", runAtSubmit)) return;

      renderReviewAnimationProgress(data.status || {});
    } catch (err) {
      if (!isCurrentReviewTool("animation", runAtSubmit)) return;

      if (panel) {
        panel.innerHTML = `
          <h3>Animation</h3>
          <div class="warning warning-major">
            <h4>Could not submit animation job</h4>
            <p>${escapeHtml(err.message)}</p>
          </div>
          <div class="review-map-controls">
            <button type="button" id="retry-animation-info-btn">Back to animation panel</button>
          </div>
        `;
        $("retry-animation-info-btn").addEventListener("click", loadReviewAnimationInfo);
      }
    }
  }




  async function loadReviewMapStatus() {
    if (!state.selectedRun || state.activeReviewTool !== "maps") return;

    const runAtStart = state.selectedRun;
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
      const data = await getJson(`/api/review/maps/status?run=${encodeURIComponent(runAtStart)}`);
      if (!isCurrentReviewTool("maps", runAtStart)) return;

      const status = data.status || {};
      const manifest = data.manifest || null;
      const stateLabel = String(status.state || "missing").toLowerCase();

      if (stateLabel === "ready") {
        if (manifest && Array.isArray(manifest.layers) && manifest.layers.length) {
          renderReviewMapReady(status, manifest);
        } else {
          renderReviewMapReadyButNoManifest(status, data);
        }
      } else if (["failed", "submit_failed", "error"].includes(stateLabel)) {
        renderReviewMapFailed(status);
      } else if (["submitted", "queued", "pending", "running", "submitting"].includes(stateLabel)) {
        renderReviewMapProgress(status);
      } else {
        renderReviewMapMissing(status);
      }
    } catch (err) {
      if (!isCurrentReviewTool("maps", runAtStart)) return;

      panel.innerHTML = `
        <h3>Toggleable static maps</h3>
        <div class="warning warning-major">
          <h4>Could not load map status</h4>
          <p>${escapeHtml(err.message)}</p>
        </div>
      `;
    }
  }

  async function submitReviewMapCache(force, direct = false) {
    if (!state.selectedRun || state.activeReviewTool !== "maps") return;

    const runAtSubmit = state.selectedRun;
    state.mapJobStartedThisView = true;

    const panel = $("review-tool-body");
    if (panel) {
      panel.innerHTML = `
        <h3>Toggleable static maps</h3>
        <div class="review-spinner-row">
          <div class="review-spinner"></div>
          <div>${direct ? "Running static maps locally in this desktop session…" : "Sending static map job to Slurm…"}</div>
        </div>
      `;
    }

    try {
      const data = await postJson("/api/review/maps/submit", {
        run: runAtSubmit,
        force,
        direct,
      });

      if (!isCurrentReviewTool("maps", runAtSubmit)) return;

      const status = data.status || {};
      renderReviewMapProgress(status);
    } catch (err) {
      if (!isCurrentReviewTool("maps", runAtSubmit)) return;

      if (panel) {
        panel.innerHTML = `
          <h3>Toggleable static maps</h3>
          <div class="warning warning-major">
            <h4>Could not submit map job</h4>
            <p>${escapeHtml(err.message)}</p>
          </div>
          <div class="review-map-controls">
            <button type="button" id="submit-review-map-cache-btn">Submit job</button>
            <button type="button" class="secondary" id="run-review-map-local-btn">Run locally</button>
          </div>
        `;
        $("submit-review-map-cache-btn").addEventListener("click", () => submitReviewMapCache(false));
        const localBtn = $("run-review-map-local-btn");
        if (localBtn) {
          localBtn.addEventListener("click", () => submitReviewMapCache(false, true));
        }
      }
    }
  }

  function setReviewTool(toolId) {
    clearInactiveReviewToolTimers(toolId);
    state.activeReviewTool = toolId;

    document.querySelectorAll(".review-tool-choice").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tool === toolId);
    });

    const panel = $("review-tool-body");
    if (!panel) return;

    if (toolId === "maps") {
      if (
        state.mapManifest &&
        state.mapStatus &&
        String(state.mapStatus.state || "").toLowerCase() === "ready"
      ) {
        renderReviewMapReady(state.mapStatus, state.mapManifest);
      } else if (state.mapJobStartedThisView) {
        loadReviewMapStatus();
      } else {
        renderStaticMapSubmitPrompt();
      }
      return;
    }

    if (toolId === "obs") {
      loadObsGaugeStatus();
      return;
    }

    if (toolId === "animation") {
      loadReviewAnimationInfo();
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



  function fmtNumber(value, digits = 2, suffix = "") {
    if (value === null || value === undefined || value === "") return "—";

    const n = Number(value);
    if (!Number.isFinite(n)) return "—";

    return `${n.toFixed(digits)}${suffix}`;
  }

  function hasMetricValue(value) {
    if (value === null || value === undefined || value === "") return false;
    return Number.isFinite(Number(value));
  }

  function cleanObsId(value) {
    const text = String(value ?? "").trim();
    if (!text || text.toLowerCase() === "nan" || text.toLowerCase() === "none") return "";
    return text;
  }

  function displayGaugeId(value) {
    const text = cleanObsId(value);
    const digits = text.replace(/\D/g, "");
    if (digits.length === 7) return `0${digits}`;
    return text;
  }


  function obsGaugeArtifactUrl(relpath) {
    const base = artifactUrl(relpath);
    const token = state.obsStatus && state.obsStatus.updated_at
      ? encodeURIComponent(state.obsStatus.updated_at)
      : String(Date.now());
    return `${base}&v=${token}`;
  }


  function obsValidationStorageKey() {
    return `reviewObsValidationCsv:${state.selectedRun || "default"}`;
  }

  function configuredEventName() {
    const cfg = pickConfigSource(state.review || {});
    return cleanObsId(
      cfg.event_name ||
      (state.review && state.review.event_name) ||
      ""
    );
  }

  function launcherDefaultsApi() {
    return window.LauncherDefaults ||
           window.SFINCS_LAUNCHER_DEFAULTS ||
           window.SfincsLauncherDefaults ||
           window.launcherDefaults ||
           {};
  }

  function launcherDefault(key) {
    const cleanKey = String(key || "").trim();
    if (!cleanKey) return "";

    const api = launcherDefaultsApi();

    if (typeof api.get === "function") {
      return cleanObsId(api.get(cleanKey));
    }

    if (typeof api.getDefault === "function") {
      return cleanObsId(api.getDefault(cleanKey));
    }

    if (typeof api.getAll === "function") {
      const all = api.getAll() || {};
      return cleanObsId(all[cleanKey]);
    }

    if (api.defaults && api.defaults[cleanKey]) {
      return cleanObsId(api.defaults[cleanKey]);
    }

    if (Object.prototype.hasOwnProperty.call(api, cleanKey)) {
      return cleanObsId(api[cleanKey]);
    }

    return "";
  }

  function stripTrailingSlash(pathText) {
    return String(pathText || "").trim().replace(/\/+$/, "");
  }
  
  function configuredDataRoot() {
    const cfg = pickConfigSource(state.review || {});

    return cleanObsId(
      cfg.data_root ||
      launcherDefault("dataRoot") ||
      ""
    );
  }
  
  function inferEventCatalogRootFromPath(pathText) {
    const text = String(pathText || "").trim();
    const marker = "/catalogs/events/";
    const idx = text.indexOf(marker);
  
    if (idx < 0) return "";
  
    const after = text.slice(idx + marker.length);
    const eventName = after.split("/")[0];
  
    if (!eventName) return "";
  
    return text.slice(0, idx + marker.length + eventName.length);
  }
  

  function configuredEventsCatalogRoot() {
    const settingsEventRoot = stripTrailingSlash(launcherDefault("eventCatalogRoot"));

    if (settingsEventRoot) {
      return settingsEventRoot;
    }

    const dataRoot = stripTrailingSlash(configuredDataRoot());

    if (dataRoot) {
      return `${dataRoot}/catalogs/events`;
    }

    return "";
  }  

  function currentEventCatalogRoot() {
    const cfg = pickConfigSource(state.review || {});
  
    const catalogs = Array.isArray(cfg.data_catalogs) ? cfg.data_catalogs : [];
    for (const pathText of catalogs) {
      const root = inferEventCatalogRootFromPath(pathText);
      if (root) return root;
    }
  
    const pathCandidates = [
      cfg.obs_points_path,
      cfg.obs_lines_path,
      cfg.rainfall_path,
      cfg.waterlevel_path,
      cfg.discharge_path,
      cfg.wind_path,
      cfg.pressure_path,
    ];
  
    for (const pathText of pathCandidates) {
      const root = inferEventCatalogRootFromPath(pathText);
      if (root) return root;
    }
  
    const eventName = configuredEventName();
    const eventsRoot = configuredEventsCatalogRoot();
  
    if (eventName && eventsRoot) {
      return `${eventsRoot}/${eventName}`;
    }
  
    return "";
  }
  
  function eventsCatalogRoot() {
    const eventRoot = currentEventCatalogRoot();
  
    if (eventRoot) {
      return eventRoot.replace(/\/[^/]+$/, "");
    }
  
    return configuredEventsCatalogRoot();
  }
  
  function defaultObsValidationCsvPath() {
    const eventRoot = currentEventCatalogRoot();
  
    if (!eventRoot) {
      return "";
    }
  
    return `${eventRoot}/event_validation_gauges`;
  }

  function isLegacyObsValidationCsvPath(path) {
    const text = String(path || "").trim();
    return text.endsWith("/input_gauge_validation.csv")
      || text.endsWith("/observed_gauge_timeseries.csv");
  }

  function initObsValidationCsvPath() {
    if (state.obsValidationCsvPath && !isLegacyObsValidationCsvPath(state.obsValidationCsvPath)) {
      return state.obsValidationCsvPath;
    }

    try {
      const saved = window.localStorage.getItem(obsValidationStorageKey());
      if (saved && !isLegacyObsValidationCsvPath(saved)) {
        state.obsValidationCsvPath = saved;
        return saved;
      }
    } catch (err) {
      // localStorage is optional
    }

    const eventDefault = defaultObsValidationCsvPath();
    
    if (eventDefault) {
      state.obsValidationCsvPath = eventDefault;
      return eventDefault;
    }
    
    state.obsValidationCsvPath = "";
    return "";
  }

  function currentObsValidationCsvPath() {
    const input = $("obs-validation-csv-input");
    const value = input ? input.value.trim() : String(state.obsValidationCsvPath || "").trim();
    state.obsValidationCsvPath = value;

    try {
      if (value) {
        window.localStorage.setItem(obsValidationStorageKey(), value);
      }
    } catch (err) {
      // localStorage is optional
    }

    return value;
  }

  function setObsValidationCsvPath(path) {
    state.obsValidationCsvPath = String(path || "").trim();

    const input = $("obs-validation-csv-input");
    if (input) {
      input.value = state.obsValidationCsvPath;
    }

    try {
      if (state.obsValidationCsvPath) {
        window.localStorage.setItem(obsValidationStorageKey(), state.obsValidationCsvPath);
      }
    } catch (err) {
      // localStorage is optional
    }
  }

  function renderObsValidationPicker() {
    const value = initObsValidationCsvPath();

    return `
      <div class="obs-validation-picker">
        <label for="obs-validation-csv-input">Validation CSV</label>
        <div class="obs-validation-row">
          <input
            id="obs-validation-csv-input"
            class="mono"
            type="text"
            value="${escapeAttr(value)}"
            placeholder="/absolute/path/to/event_validation_gauges or validation CSV"
          >
          <button type="button" class="secondary" id="obs-validation-default-btn">Use event folder</button>
          <button type="button" class="secondary" id="obs-validation-browse-btn">Browse</button>
        </div>
        <div class="obs-validation-help">
          Auto-filled from this run's event_validation_gauges folder when possible. Files inside _misc are ignored. Browse or paste another CSV if needed.
        </div>
        <div id="obs-validation-browser" class="obs-file-browser" style="display:none;"></div>
      </div>
    `;
  }

  function isIgnoredObsValidationEntryName(name) {
    const text = String(name || "").toLowerCase();

    return text === "_misc"
      || text === "_quarantine"
      || text.includes("draft")
      || text.includes("backup")
      || text.includes("stale")
      || text.includes("do_not_use")
      || text.includes("original")
      || text.includes("candidate");
  }

  function obsValidationCandidateRank(entry) {
    const name = String(entry && entry.name || "").toLowerCase();

    if (!name.endsWith(".csv")) {
      return 99;
    }

    if (name.includes("validation") && (name.includes("timeseries") || name.includes("time_series"))) {
      return 0;
    }

    if (name.includes("gauge") && (name.includes("timeseries") || name.includes("time_series"))) {
      return 1;
    }

    if (name.includes("validation") && name.includes("gauge")) {
      return 2;
    }

    if (name.includes("observed") && (name.includes("timeseries") || name.includes("time_series"))) {
      return 3;
    }

    return 9;
  }

  function chooseObsValidationCsvFromEntries(entries) {
    const candidates = (Array.isArray(entries) ? entries : [])
      .filter((entry) => {
        const name = String(entry.name || "");
        return entry.is_file
          && name.toLowerCase().endsWith(".csv")
          && !isIgnoredObsValidationEntryName(name);
      })
      .sort((a, b) => {
        const ar = obsValidationCandidateRank(a);
        const br = obsValidationCandidateRank(b);
        if (ar !== br) return ar - br;
        return String(a.name || "").localeCompare(String(b.name || ""));
      });

    return candidates.length ? candidates[0] : null;
  }

  async function autofillObsValidationCsvFromFolder() {
    const current = String(state.obsValidationCsvPath || "").trim();
    const startPath = current && !current.endsWith(".csv")
      ? current
      : (defaultObsValidationCsvPath() || eventsCatalogRoot());

    try {
      const data = await postJson("/api/list-directory", { path: startPath });
      const entries = Array.isArray(data.entries) ? data.entries : [];
      const chosen = chooseObsValidationCsvFromEntries(entries);

      if (chosen && chosen.path) {
        setObsValidationCsvPath(chosen.path);
      }
    } catch (err) {
      // Autofill is convenience only. The user can still paste or browse.
    }
  }


  async function browseObsValidationPath(pathText) {
    const browser = $("obs-validation-browser");
    if (!browser) return;

    const startPath = String(
      pathText ||
      currentObsValidationCsvPath() ||
      defaultObsValidationCsvPath() ||
      eventsCatalogRoot()
    ).trim();

    browser.style.display = "block";
    browser.innerHTML = `<div class="empty-note">Loading ${escapeHtml(startPath)}…</div>`;

    try {
      const data = await postJson("/api/list-directory", { path: startPath });
      const entries = Array.isArray(data.entries) ? data.entries : [];

      const visible = entries.filter((entry) => {
        const name = String(entry.name || "").toLowerCase();

        if (isIgnoredObsValidationEntryName(name)) {
          return false;
        }

        if (entry.is_dir) {
          return true;
        }

        return entry.is_file && name.endsWith(".csv");
      });

      browser.innerHTML = `
        <div class="obs-browser-header">
          <strong>Browse validation CSV</strong>
          <span class="mono">${escapeHtml(data.path || startPath)}</span>
        </div>

        <div class="obs-browser-actions">
          ${data.parent ? `<button type="button" class="secondary" data-obs-browse-path="${escapeAttr(data.parent)}">Parent</button>` : ""}
          <button type="button" class="secondary" id="obs-validation-close-browser-btn">Close</button>
        </div>

        <div class="obs-browser-list">
          ${visible.length ? visible.map((entry) => `
            <button
              type="button"
              class="obs-browser-entry ${entry.is_dir ? "dir" : "file"}"
              data-obs-browse-path="${escapeAttr(entry.path)}"
              data-obs-is-file="${entry.is_file ? "1" : "0"}"
            >
              <span>${entry.is_dir ? "📁" : "📄"}</span>
              <span class="mono">${escapeHtml(entry.name || entry.path)}</span>
            </button>
          `).join("") : `<div class="empty-note">No folders or CSV files found here.</div>`}
        </div>
      `;

      const closeBtn = $("obs-validation-close-browser-btn");
      if (closeBtn) {
        closeBtn.addEventListener("click", () => {
          browser.style.display = "none";
          browser.innerHTML = "";
        });
      }

      browser.querySelectorAll("[data-obs-browse-path]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const p = btn.getAttribute("data-obs-browse-path") || "";
          const isFile = btn.getAttribute("data-obs-is-file") === "1";

          if (isFile) {
            setObsValidationCsvPath(p);
            browser.style.display = "none";
            browser.innerHTML = "";
          } else {
            browseObsValidationPath(p);
          }
        });
      });
    } catch (err) {
      browser.innerHTML = `
        <div class="warning warning-major">
          <h4>Could not browse path</h4>
          <p>${escapeHtml(err.message)}</p>
        </div>
      `;
    }
  }

  function wireObsValidationPicker() {
    const input = $("obs-validation-csv-input");
    const defaultBtn = $("obs-validation-default-btn");
    const browseBtn = $("obs-validation-browse-btn");

    if (input) {
      input.addEventListener("input", () => {
        setObsValidationCsvPath(input.value);
      });
    }

    if (defaultBtn) {
      defaultBtn.addEventListener("click", () => {
        setObsValidationCsvPath(defaultObsValidationCsvPath() || eventsCatalogRoot());
        autofillObsValidationCsvFromFolder();
      });
    }

    if (browseBtn) {
      browseBtn.addEventListener("click", () => {
        browseObsValidationPath(currentObsValidationCsvPath());
      });
    }
    
    const current = String(state.obsValidationCsvPath || "").trim();
    if (!current || !current.endsWith(".csv") || isLegacyObsValidationCsvPath(current)) {
      autofillObsValidationCsvFromFolder();
    }
    
  }

  function flowPeakPercentError(row) {
    if (hasMetricValue(row.flow_peak_error_pct)) {
      return Math.abs(Number(row.flow_peak_error_pct));
    }

    const err = Number(row.flow_peak_error_cms);
    const obs = Number(row.obs_flow_peak_cms);

    if (Number.isFinite(err) && Number.isFinite(obs) && Math.abs(obs) > 1e-12) {
      return 100 * Math.abs(err) / Math.abs(obs);
    }

    return null;
  }

  function flowMeanPercentError(row) {
    if (hasMetricValue(row.flow_mean_error_pct)) {
      return Math.abs(Number(row.flow_mean_error_pct));
    }

    const err = Number(row.flow_mean_error_cms);
    const obs = Number(row.obs_flow_mean_cms);

    if (Number.isFinite(err) && Number.isFinite(obs) && Math.abs(obs) > 1e-12) {
      return 100 * Math.abs(err) / Math.abs(obs);
    }

    return null;
  }

  function lineFlowErrorScore(row) {
    const peakPct = flowPeakPercentError(row);

    if (Number.isFinite(peakPct)) {
      return peakPct;
    }

    const vals = [];

    if (hasMetricValue(row.flow_mean_error_cms)) {
      vals.push(Math.abs(Number(row.flow_mean_error_cms)));
    }

    if (hasMetricValue(row.flow_peak_error_cms)) {
      vals.push(Math.abs(Number(row.flow_peak_error_cms)));
    }

    if (!vals.length) return null;

    return Math.max(...vals);
  }

  function percentile(values, q) {
    const nums = values
      .map((v) => Number(v))
      .filter((v) => Number.isFinite(v))
      .sort((a, b) => a - b);

    if (!nums.length) return null;
    if (nums.length === 1) return nums[0];

    const pos = (nums.length - 1) * q;
    const lo = Math.floor(pos);
    const hi = Math.ceil(pos);

    if (lo === hi) return nums[lo];

    const weight = pos - lo;
    return nums[lo] * (1 - weight) + nums[hi] * weight;
  }

  function addLineGradientStyles(rows) {
    const lineRows = rows.filter((row) => obsGaugeKind(row) === "line");
    const scores = lineRows
      .map(lineFlowErrorScore)
      .filter((v) => Number.isFinite(v));

    const robustMax = percentile(scores, 0.95) || Math.max(...scores, 1) || 1;

    return rows.map((row) => {
      if (obsGaugeKind(row) !== "line") return row;

      const rawScore = lineFlowErrorScore(row);

      if (!Number.isFinite(rawScore) || robustMax <= 0) {
        return {
          ...row,
          line_gradient_style: "",
          line_error_score_cms: rawScore,
        };
      }

      const normalized = Math.max(0, Math.min(1, rawScore / robustMax));

      // 0 = green, 0.5 = yellow, 1 = red.
      const hue = 120 * (1 - normalized);
      const bg = `hsl(${hue.toFixed(1)} 82% 94%)`;
      const border = `hsl(${hue.toFixed(1)} 72% 36%)`;

      return {
        ...row,
        line_error_score_cms: rawScore,
        line_error_normalized: normalized,
        line_gradient_style: `--ring:${border}; background:linear-gradient(180deg, ${bg} 0%, #ffffff 112%); border-color:${border};`,
      };
    });
  }

  function obsGaugeKind(row) {
    if (!row || typeof row !== "object") {
      return "";
    }
  
    const raw = String(row.map_kind || row.kind || row.role || row.validation_kind || "point")
      .trim()
      .toLowerCase();
  
    if ([
      "line",
      "line_flow",
      "flow",
      "discharge",
      "crs",
      "cross_section",
      "cross-section",
      "crosssection",
    ].includes(raw)) {
      return "line";
    }
  
    if ([
      "point",
      "point_stage",
      "point_wl",
      "stage",
      "water_level",
      "waterlevel",
      "wl",
    ].includes(raw)) {
      return "point";
    }
  
    return "point";
  }

  function obsGaugeMapKey(row) {
    if (!row || typeof row !== "object") {
      return "";
    }

    const kind = obsGaugeKind(row);
    if (!kind) {
      return "";
    }

    const rawId = kind === "line"
      ? (row.line_id || row.match_id || row.sim_id || row.gauge_id || "")
      : (row.gauge_id || row.match_id || row.sim_id || "");

    const cleanId = displayGaugeId(rawId || "");
    if (!cleanId) {
      return "";
    }

    return `${kind}:${cleanId}`;
  }

  function safePercentError(errorValue, observedValue) {
    const err = Number(errorValue);
    const obs = Number(observedValue);

    if (!Number.isFinite(err) || !Number.isFinite(obs) || Math.abs(obs) <= 1e-12) {
      return null;
    }

    return 100 * Math.abs(err) / Math.abs(obs);
  }

  function cardPercentError(row) {
    const kind = obsGaugeKind(row);

    if (kind === "line") {
      const peakPct = safePercentError(row.flow_peak_error_cms, row.obs_flow_peak_cms);
      if (hasMetricValue(peakPct)) {
        return {
          label: "Peak % error",
          value: peakPct,
        };
      }

      const meanPct = safePercentError(row.flow_mean_error_cms, row.obs_flow_mean_cms);
      if (hasMetricValue(meanPct)) {
        return {
          label: "Mean % error",
          value: meanPct,
        };
      }

      return null;
    }

    const wlPeakPct = safePercentError(row.wl_peak_error_m, row.obs_wl_peak_m);
    if (hasMetricValue(wlPeakPct)) {
      return {
        label: "Peak WL % error",
        value: wlPeakPct,
      };
    }

    const wlMeanPct = safePercentError(row.wl_mean_error_m, row.obs_wl_mean_m);
    if (hasMetricValue(wlMeanPct)) {
      return {
        label: "Mean WL % error",
        value: wlMeanPct,
      };
    }

    return null;
  }


  function renderObsOverallCard(label, value, suffix = "", digits = 2) {
    return `
      <div class="obs-overall-card">
        <strong>${escapeHtml(fmtNumber(value, digits, suffix))}</strong>
        <span>${escapeHtml(label)}</span>
      </div>
    `;
  }
  
  function obsGaugeFamilyKey(row) {
    const raw = String(row.gauge_id || row.match_id || row.sim_id || "").trim();
    let digits = raw.replace(/\D/g, "");

    // Normalize common USGS/HCFCD leading-zero loss:
    // 8069000 -> 08069000
    if (digits.length === 7 && digits.startsWith("80")) {
      digits = `0${digits}`;
    }

    return digits ? `gauge:${digits}` : "";
  }

  function markDualRoleGaugeRows(rows) {
    const list = Array.isArray(rows) ? rows : [];
    const kindsByFamily = new Map();

    list.forEach((row) => {
      const familyKey = obsGaugeFamilyKey(row);
      if (!familyKey) return;

      const kind = obsGaugeKind(row);
      if (!kindsByFamily.has(familyKey)) {
        kindsByFamily.set(familyKey, new Set());
      }
      kindsByFamily.get(familyKey).add(kind);
    });

    return list.map((row) => {
      const familyKey = obsGaugeFamilyKey(row);
      const kinds = familyKey ? kindsByFamily.get(familyKey) : null;
      const dualRole = Boolean(kinds && kinds.has("point") && kinds.has("line"));

      return {
        ...row,
        role_family_key: familyKey,
        dual_role: dualRole,
      };
    });
  }
  
  function buildObsGaugeDisplayRows(gauges) {
    const rows = Array.isArray(gauges) ? gauges : [];
    return addLineGradientStyles(markDualRoleGaugeRows(rows));
  }

  function renderObsGaugeDial(row) {
    const kind = obsGaugeKind(row);
    const isLine = kind === "line";
    const label = String(row.severity_label || "unknown").toLowerCase();

    const gaugeId = displayGaugeId(row.gauge_id || row.match_id || row.sim_id || "gauge");
    const lineId = cleanObsId(row.line_id || row.match_id || row.paired_line_id || "");
    const lineStyle = isLine ? String(row.line_gradient_style || "") : "";
    const mapKey = obsGaugeMapKey(row);
    const familyKey = row.role_family_key || obsGaugeFamilyKey(row);
    const dualClass = row.dual_role ? "dual-role" : "";

    const metrics = [];

    function addMetric(labelText, value, digits, suffix) {
      if (!hasMetricValue(value)) return;
      metrics.push(`
        <div class="obs-dial-metric">
          <span>${escapeHtml(labelText)}</span>
          <strong>${escapeHtml(fmtNumber(value, digits, suffix))}</strong>
        </div>
      `);
    }

    if (isLine) {
      addMetric("Mean bias", row.flow_mean_error_cms, 1, " m³/s");
      addMetric("Mean % error", flowMeanPercentError(row), 1, "%");
      addMetric("Mean abs. error", row.flow_mae_cms, 1, " m³/s");
      addMetric("RMSE", row.flow_rmse_cms, 1, " m³/s");
      addMetric("Peak error", row.flow_peak_error_cms, 1, " m³/s");
      addMetric("Peak % error", flowPeakPercentError(row), 1, "%");
      addMetric("Peak timing", row.flow_peak_timing_error_hr, 1, " hr");
      addMetric("NSE", row.flow_nse, 3, "");
      addMetric("KGE", row.flow_kge, 3, "");
      addMetric("PBIAS", row.flow_pbias_pct, 1, "%");
      addMetric("Peak flow", row.sim_flow_peak_cms, 1, " m³/s");
    } else {
          addMetric("Sim peak WL", row.sim_wl_peak_m, 2, " m");
          addMetric("Obs peak WL", row.obs_wl_peak_m, 2, " m");
          addMetric("Peak WL error", row.wl_error_m, 2, " m");
          addMetric("Peak WL % error", safePercentError(row.wl_error_m, row.obs_wl_peak_m), 1, "%");
        }

    if (!metrics.length) {
      metrics.push(`<div class="obs-dial-empty">No metric</div>`);
    }

    return `
      <div
        class="obs-dial obs-dial-clickable ${escapeHtml(kind)} ${escapeHtml(label)} ${escapeHtml(dualClass)}"
        style="${escapeAttr(lineStyle)}"
        title="${escapeAttr(JSON.stringify(row))}"
        data-obs-map-key="${escapeAttr(mapKey)}"
        data-obs-family-key="${escapeAttr(familyKey)}"
        tabindex="0"
        role="button"
        aria-label="Highlight ${escapeAttr(gaugeId)} on map"
      >
        <div class="obs-dial-kind">${escapeHtml(isLine ? lineId || "line" : "point")}</div>
        ${row.dual_role ? `<div class="obs-dial-name">Point + CRS gauge</div>` : ""}
        <div class="obs-dial-title">${escapeHtml(gaugeId)}</div>
        <div class="obs-dial-metrics">${metrics.join("")}</div>
      </div>
    `;
  }


  function obsGaugeTimeseriesKey(row) {
    return obsGaugeMapKey(row);
  }

  function indexObsGaugeTimeseries(data) {
    const items = Array.isArray(data && data.items)
      ? data.items
      : Object.values((data && data.items) || {});

    const byKey = new Map();

    items.forEach((item) => {
      const key = obsGaugeTimeseriesKey(item);
      if (key) {
        byKey.set(key, item);
      }
    });

    return byKey;
  }

  function renderObsGaugeTimeseriesPanel() {
    return `
      <section class="obs-gauge-timeseries-card" id="obs-gauge-timeseries-card">
        <div class="obs-gauge-timeseries-header">
          <div>
            <h3>Selected gauge time series</h3>
            <p class="obs-gauge-timeseries-subtitle" id="obs-gauge-timeseries-subtitle">
              Click a map marker or a gauge card to compare modeled and observed values over time.
            </p>
          </div>

          <div class="obs-gauge-timeseries-mode-row" aria-label="Selected gauge time-series metric">
            <button
              type="button"
              class="secondary obs-gauge-timeseries-mode-btn"
              id="obs-timeseries-flow-btn"
              data-obs-timeseries-mode="flow"
              disabled
            >
              Flow rate
            </button>

            <button
              type="button"
              class="secondary obs-gauge-timeseries-mode-btn"
              id="obs-timeseries-wl-btn"
              data-obs-timeseries-mode="water_level"
              disabled
            >
              Water level
            </button>
          </div>
        </div>

        <div class="empty-note" id="obs-gauge-timeseries-empty">
          No gauge selected yet.
        </div>

        <div
          class="obs-gauge-timeseries-plot"
          id="obs-gauge-timeseries-plot"
          hidden
        ></div>

        <div class="obs-gauge-timeseries-note" id="obs-gauge-timeseries-note"></div>
      </section>
    `;
  }

  function findObsGaugeDisplayRowByKey(key, familyKey = "") {
    const rows = buildObsGaugeDisplayRows(
      state.obsMetrics && Array.isArray(state.obsMetrics.gauges)
        ? state.obsMetrics.gauges
        : []
    );

    const exact = rows.find((row) => obsGaugeMapKey(row) === key);
    if (exact) return exact;

    if (familyKey) {
      return rows.find((row) => {
        const rowFamily = row.role_family_key || obsGaugeFamilyKey(row);
        return rowFamily && rowFamily === familyKey;
      }) || null;
    }

    return null;
  }

  function timeseriesMetricKind(item) {
    if (!item || typeof item !== "object") {
      return "";
    }

    const metric = String(item.metric || "").toLowerCase();
    const kind = obsGaugeKind(item);

    if (metric.includes("flow") || metric.includes("discharge") || kind === "line") {
      return "flow";
    }

    if (
      metric.includes("water") ||
      metric.includes("wl") ||
      metric.includes("stage") ||
      kind === "point"
    ) {
      return "water_level";
    }

    return "";
  }

  function allObsGaugeTimeseriesCandidates(key, familyKey = "") {
    const out = [];
    const seen = new Set();

    function add(item) {
      if (!item) return;
      const itemKey = obsGaugeTimeseriesKey(item);
      const sig = itemKey || JSON.stringify([item.gauge_id, item.line_id, item.kind, item.metric]);
      if (seen.has(sig)) return;
      seen.add(sig);
      out.push(item);
    }

    if (state.obsTimeseriesByKey && state.obsTimeseriesByKey.has(key)) {
      add(state.obsTimeseriesByKey.get(key));
    }

    if (state.obsTimeseriesByKey) {
      for (const item of state.obsTimeseriesByKey.values()) {
        const itemFamily = obsGaugeFamilyKey(item);
        if (familyKey && itemFamily && itemFamily === familyKey) {
          add(item);
        }
      }
    }

    return out;
  }

  function availableObsTimeseriesMetrics(key, familyKey = "") {
    const candidates = allObsGaugeTimeseriesCandidates(key, familyKey);
    return {
      flow: candidates.some((item) => timeseriesMetricKind(item) === "flow"),
      water_level: candidates.some((item) => timeseriesMetricKind(item) === "water_level"),
    };
  }

  function findObsGaugeTimeseriesItem(key, familyKey = "", preferredMetric = "auto") {
    const candidates = allObsGaugeTimeseriesCandidates(key, familyKey);

    if (!candidates.length) {
      return null;
    }

    if (preferredMetric && preferredMetric !== "auto") {
      const exact = candidates.find((item) => timeseriesMetricKind(item) === preferredMetric);
      if (exact) return exact;
    }

    const exactKey = candidates.find((item) => obsGaugeTimeseriesKey(item) === key);
    if (exactKey) return exactKey;

    return candidates[0] || null;
  }

  function downsampleSeries(time, sim, obs, maxPoints = 700) {
    const n = Math.min(
      Array.isArray(time) ? time.length : 0,
      Array.isArray(sim) ? sim.length : 0
    );

    if (n <= maxPoints) {
      return {
        time: time.slice(0, n),
        sim: sim.slice(0, n),
        obs: Array.isArray(obs) ? obs.slice(0, n) : null,
      };
    }

    const step = Math.ceil(n / maxPoints);
    const outTime = [];
    const outSim = [];
    const outObs = Array.isArray(obs) ? [] : null;

    for (let i = 0; i < n; i += step) {
      outTime.push(time[i]);
      outSim.push(sim[i]);
      if (outObs) outObs.push(obs[i]);
    }

    if (outTime[outTime.length - 1] !== time[n - 1]) {
      outTime.push(time[n - 1]);
      outSim.push(sim[n - 1]);
      if (outObs) outObs.push(obs[n - 1]);
    }

    return { time: outTime, sim: outSim, obs: outObs };
  }

  function shortTimeLabel(value) {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) {
      return String(value || "");
    }

    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
    });
  }

  function buildObsGaugeTimeseriesSvg(item) {
    const sampled = downsampleSeries(item.time || [], item.sim || [], item.obs || null);
    const time = sampled.time;
    const sim = sampled.sim;
    const obs = sampled.obs;

    const refs = [
      { value: item.obs_peak, label: "Obs peak" },
      { value: item.obs_mean, label: "Obs mean" },
    ].filter((r) => hasMetricValue(r.value));

    const values = [];

    sim.forEach((v) => {
      if (hasMetricValue(v)) values.push(Number(v));
    });

    if (Array.isArray(obs)) {
      obs.forEach((v) => {
        if (hasMetricValue(v)) values.push(Number(v));
      });
    }

    refs.forEach((r) => {
      values.push(Number(r.value));
    });

    if (!values.length || time.length < 2) {
      return `<div class="empty-note">No finite time-series values were available for this selected gauge.</div>`;
    }

    let ymin = Math.min(...values);
    let ymax = Math.max(...values);

    if (!Number.isFinite(ymin) || !Number.isFinite(ymax)) {
      return `<div class="empty-note">No finite time-series values were available for this selected gauge.</div>`;
    }

    if (Math.abs(ymax - ymin) < 1e-9) {
      ymin -= 1;
      ymax += 1;
    } else {
      const pad = 0.08 * (ymax - ymin);
      ymin -= pad;
      ymax += pad;
    }

    const width = 920;
    const height = 320;
    const left = 62;
    const right = 24;
    const top = 24;
    const bottom = 52;
    const plotW = width - left - right;
    const plotH = height - top - bottom;

    function xAt(i) {
      return left + (plotW * i) / Math.max(1, time.length - 1);
    }

    function yAt(v) {
      return top + plotH * (1 - ((Number(v) - ymin) / (ymax - ymin)));
    }

    function pathFor(valuesIn) {
      let d = "";
      let open = false;

      valuesIn.forEach((value, i) => {
        if (!hasMetricValue(value)) {
          open = false;
          return;
        }

        const x = xAt(i);
        const y = yAt(value);

        if (!open) {
          d += `M ${x.toFixed(2)} ${y.toFixed(2)}`;
          open = true;
        } else {
          d += ` L ${x.toFixed(2)} ${y.toFixed(2)}`;
        }
      });

      return d;
    }

    function refLine(ref) {
      const y = yAt(ref.value);
      return `
        <line x1="${left}" y1="${y.toFixed(2)}" x2="${width - right}" y2="${y.toFixed(2)}" class="obs-ts-ref-line"></line>
        <text x="${left + 8}" y="${(y - 6).toFixed(2)}" class="obs-ts-ref-label">${escapeHtml(ref.label)} ${escapeHtml(fmtNumber(ref.value, 2, ""))}</text>
      `;
    }

    const simPath = pathFor(sim);
    const obsPath = Array.isArray(obs) ? pathFor(obs) : "";

    const yTicks = [ymin, ymin + (ymax - ymin) / 2, ymax];
    const xTicks = [
      { i: 0, label: shortTimeLabel(time[0]) },
      { i: Math.floor((time.length - 1) / 2), label: shortTimeLabel(time[Math.floor((time.length - 1) / 2)]) },
      { i: time.length - 1, label: shortTimeLabel(time[time.length - 1]) },
    ];

    return `
      <svg class="obs-gauge-timeseries-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Selected gauge time-series chart">
        <style>
          .obs-ts-axis { stroke: #667085; stroke-width: 1; }
          .obs-ts-grid { stroke: #d0d5dd; stroke-width: 1; opacity: 0.72; }
          .obs-ts-label { fill: #667085; font-size: 12px; font-weight: 700; }
          .obs-ts-title { fill: #172033; font-size: 13px; font-weight: 800; }
          .obs-ts-sim { fill: none; stroke: #2563eb; stroke-width: 2.4; }
          .obs-ts-obs { fill: none; stroke: #111827; stroke-width: 2.1; }
          .obs-ts-ref-line { stroke: #b25e09; stroke-width: 1.5; stroke-dasharray: 6 5; }
          .obs-ts-ref-label { fill: #92400e; font-size: 12px; font-weight: 800; }
        </style>

        <rect x="0" y="0" width="${width}" height="${height}" fill="#f8fafc"></rect>

        ${yTicks.map((tick) => {
          const y = yAt(tick);
          return `
            <line x1="${left}" y1="${y.toFixed(2)}" x2="${width - right}" y2="${y.toFixed(2)}" class="obs-ts-grid"></line>
            <text x="${left - 10}" y="${(y + 4).toFixed(2)}" text-anchor="end" class="obs-ts-label">${escapeHtml(fmtNumber(tick, 2, ""))}</text>
          `;
        }).join("")}

        <line x1="${left}" y1="${top}" x2="${left}" y2="${height - bottom}" class="obs-ts-axis"></line>
        <line x1="${left}" y1="${height - bottom}" x2="${width - right}" y2="${height - bottom}" class="obs-ts-axis"></line>

        ${xTicks.map((tick) => {
          const x = xAt(tick.i);
          return `
            <line x1="${x.toFixed(2)}" y1="${height - bottom}" x2="${x.toFixed(2)}" y2="${height - bottom + 5}" class="obs-ts-axis"></line>
            <text x="${x.toFixed(2)}" y="${height - 22}" text-anchor="middle" class="obs-ts-label">${escapeHtml(tick.label)}</text>
          `;
        }).join("")}

        ${refs.map(refLine).join("")}

        ${simPath ? `<path d="${simPath}" class="obs-ts-sim"></path>` : ""}
        ${obsPath ? `<path d="${obsPath}" class="obs-ts-obs"></path>` : ""}

        <text x="${left}" y="18" class="obs-ts-title">${escapeHtml(item.metric === "flow" ? "Flow rate" : item.metric === "water_level" ? "Water level" : item.metric || "metric")} (${escapeHtml(item.unit || "")})</text>
      </svg>

      <div class="obs-gauge-timeseries-legend">
        <span style="color:#2563eb;"><span class="obs-gauge-timeseries-swatch"></span>Simulated</span>
        ${obsPath ? `<span style="color:#111827;"><span class="obs-gauge-timeseries-swatch"></span>Observed hydrograph</span>` : ""}
        ${refs.length ? `<span style="color:#b25e09;"><span class="obs-gauge-timeseries-swatch"></span>Observed scalar reference</span>` : ""}
      </div>
    `;
  }

  function updateObsGaugeTimeseriesModeButtons(availability, item) {
    const flowBtn = $("obs-timeseries-flow-btn");
    const wlBtn = $("obs-timeseries-wl-btn");

    if (!flowBtn || !wlBtn) return;

    const currentMetric = item ? timeseriesMetricKind(item) : "";
    const hasFlow = Boolean(availability && availability.flow);
    const hasWl = Boolean(availability && availability.water_level);

    flowBtn.disabled = !hasFlow;
    wlBtn.disabled = !hasWl;

    flowBtn.classList.toggle("active", currentMetric === "flow");
    wlBtn.classList.toggle("active", currentMetric === "water_level");

    flowBtn.textContent = hasFlow ? "Flow rate" : "Flow unavailable";
    wlBtn.textContent = hasWl ? "Water level" : "WL unavailable";
  }

  function wireObsGaugeTimeseriesModeButtons() {
    document.querySelectorAll("[data-obs-timeseries-mode]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const mode = btn.getAttribute("data-obs-timeseries-mode") || "auto";
        if (btn.disabled) return;

        state.selectedObsTimeseriesMetric = mode;
        renderSelectedObsGaugeTimeseries();
      });
    });
  }

  function renderSelectedObsGaugeTimeseries() {
    const subtitle = $("obs-gauge-timeseries-subtitle");
    const empty = $("obs-gauge-timeseries-empty");
    const plot = $("obs-gauge-timeseries-plot");
    const note = $("obs-gauge-timeseries-note");

    if (!subtitle || !empty || !plot || !note) return;

    const key = state.selectedObsTimeseriesKey || "";
    const familyKey = state.selectedObsTimeseriesFamilyKey || "";
    const preferredMetric = state.selectedObsTimeseriesMetric || "auto";

    if (!key) {
      subtitle.textContent = "Click a map marker or a gauge card to compare modeled and observed values over time.";
      empty.hidden = false;
      empty.textContent = "No gauge selected yet.";
      plot.hidden = true;
      plot.innerHTML = "";
      note.textContent = "";
      updateObsGaugeTimeseriesModeButtons({ flow: false, water_level: false }, null);
      return;
    }

    const row = findObsGaugeDisplayRowByKey(key, familyKey);
    const availability = availableObsTimeseriesMetrics(key, familyKey);
    const item = findObsGaugeTimeseriesItem(key, familyKey, preferredMetric);

    updateObsGaugeTimeseriesModeButtons(availability, item);

    const itemMetric = timeseriesMetricKind(item);
    const roleLabel = itemMetric === "flow"
      ? " — CRS / flow"
      : itemMetric === "water_level"
        ? " — point / water level"
        : "";

    const label = row
      ? `${displayGaugeId(row.gauge_id || row.match_id || row.sim_id || key)}${roleLabel}`
      : `${key}${roleLabel}`;

    subtitle.textContent = label;

    if (state.obsTimeseriesLoading) {
      empty.hidden = false;
      empty.textContent = "Loading selected-gauge time-series product…";
      plot.hidden = true;
      plot.innerHTML = "";
      note.textContent = "";
      return;
    }

    if (state.obsTimeseriesError) {
      empty.hidden = false;
      empty.textContent = state.obsTimeseriesError;
      plot.hidden = true;
      plot.innerHTML = "";
      note.textContent = "";
      return;
    }

    if (!item) {
      empty.hidden = false;
      empty.textContent = "No time-series product was found for this selected gauge.";
      plot.hidden = true;
      plot.innerHTML = "";
      note.textContent = "";
      return;
    }

    empty.hidden = true;
    plot.hidden = false;
    plot.innerHTML = buildObsGaugeTimeseriesSvg(item);
    note.textContent = item.note || "";
  }

  function selectObsGaugeTimeseries(key, familyKey = "") {
    state.selectedObsTimeseriesKey = key || "";
    state.selectedObsTimeseriesFamilyKey = familyKey || "";

    const row = findObsGaugeDisplayRowByKey(key, familyKey);
    const clickedKind = row ? obsGaugeKind(row) : "";

    if (clickedKind === "line") {
      state.selectedObsTimeseriesMetric = "flow";
    } else if (clickedKind === "point") {
      state.selectedObsTimeseriesMetric = "water_level";
    } else {
      state.selectedObsTimeseriesMetric = "auto";
    }

    renderSelectedObsGaugeTimeseries();
  }

  async function loadObsGaugeTimeseries(relpath) {
    state.obsTimeseries = null;
    state.obsTimeseriesByKey = new Map();
    state.obsTimeseriesError = "";

    if (!relpath) {
      state.obsTimeseriesLoading = false;
      state.obsTimeseriesError = "No obs/gauge time-series product was listed in the manifest. Rerun Obs/Gauges locally after the backend edit.";
      renderSelectedObsGaugeTimeseries();
      return;
    }

    state.obsTimeseriesLoading = true;
    renderSelectedObsGaugeTimeseries();

    try {
      const data = await getJson(obsGaugeArtifactUrl(relpath));
      state.obsTimeseries = data;
      state.obsTimeseriesByKey = indexObsGaugeTimeseries(data);
      state.obsTimeseriesError = "";
    } catch (err) {
      state.obsTimeseries = null;
      state.obsTimeseriesByKey = new Map();
      state.obsTimeseriesError = `Could not load obs/gauge time-series product: ${err.message}`;
    } finally {
      state.obsTimeseriesLoading = false;
      renderSelectedObsGaugeTimeseries();
    }
  }

  function renderObsGaugeMissing(status) {
    state.obsStatus = status || null;
    const panel = $("review-tool-body");
    if (!panel) return;

    panel.innerHTML = `
      <h3>Obs / gauges</h3>
      <p class="section-intro">
        Build cached observed-vs-modeled gauge metrics from model/sfincs_his.nc and a validation CSV.
      </p>
      ${renderSlurmStatus(status, "obs/gauge validation products")}
      ${renderObsValidationPicker()}
      <div class="review-map-controls" style="margin-top: 12px;">
        <button type="button" id="submit-obs-gauges-btn">Submit Slurm</button>
        <button type="button" class="secondary" id="run-obs-gauges-local-btn">Run locally</button>
      </div>
    `;

    wireObsValidationPicker();
    $("submit-obs-gauges-btn").addEventListener("click", () => submitObsGaugeJob(false));

    const localObsBtn = $("run-obs-gauges-local-btn");
    if (localObsBtn) {
      localObsBtn.addEventListener("click", () => submitObsGaugeJob(true));
    }
  }

  function renderObsGaugeProgress(status) {
    state.obsStatus = status || null;
    const panel = $("review-tool-body");
    if (!panel) return;

    panel.innerHTML = `
      <h3>Obs / gauges</h3>
      ${renderSlurmStatus(status, "obs/gauge validation products")}
      <div class="empty-note">Obs/gauge status refreshes automatically while the job is queued or running.</div>
    `;

    if (state.obsPollTimer) {
      window.clearTimeout(state.obsPollTimer);
    }
    state.obsPollTimer = window.setTimeout(loadObsGaugeStatus, 3000);
  }

  function renderObsGaugeFailed(status) {
    state.obsStatus = status || null;
    const panel = $("review-tool-body");
    if (!panel) return;

    panel.innerHTML = `
      <h3>Obs / gauges</h3>
      ${renderSlurmStatus(status, "obs/gauge validation products")}
      <div class="warning warning-major">
        <h4>Obs/gauge job failed</h4>
        <p>${escapeHtml((status && status.error) || "Unknown obs/gauge job error.")}</p>
        ${status && status.traceback ? `<details><summary>Traceback</summary><pre>${escapeHtml(status.traceback)}</pre></details>` : ""}
      </div>
      ${renderObsValidationPicker()}
      <div class="review-map-controls">
        <button type="button" id="submit-obs-gauges-btn">Submit Slurm</button>
        <button type="button" class="secondary" id="run-obs-gauges-local-btn">Run locally</button>
      </div>
    `;

    wireObsValidationPicker();
    $("submit-obs-gauges-btn").addEventListener("click", () => submitObsGaugeJob(false));

    const localObsBtn = $("run-obs-gauges-local-btn");
    if (localObsBtn) {
      localObsBtn.addEventListener("click", () => submitObsGaugeJob(true));
    }
  }

  function obsMapPctFromXY(row, extent) {
    const xmin = Number(extent.xmin);
    const xmax = Number(extent.xmax);
    const ymin = Number(extent.ymin);
    const ymax = Number(extent.ymax);

    let x = Number(row.x);
    let y = Number(row.y);

    if ((!Number.isFinite(x) || !Number.isFinite(y)) && row.x1 !== undefined && row.x2 !== undefined) {
      const x1 = Number(row.x1);
      const x2 = Number(row.x2);
      const y1 = Number(row.y1);
      const y2 = Number(row.y2);

      if (Number.isFinite(x1) && Number.isFinite(x2) && Number.isFinite(y1) && Number.isFinite(y2)) {
        x = (x1 + x2) / 2;
        y = (y1 + y2) / 2;
      }
    }

    if (
      !Number.isFinite(x) ||
      !Number.isFinite(y) ||
      !Number.isFinite(xmin) ||
      !Number.isFinite(xmax) ||
      !Number.isFinite(ymin) ||
      !Number.isFinite(ymax) ||
      xmax <= xmin ||
      ymax <= ymin
    ) {
      return null;
    }

    return {
      left_pct: 100 * (x - xmin) / (xmax - xmin),
      top_pct: 100 * (1 - ((y - ymin) / (ymax - ymin))),
    };
  }

  function buildObsMapHotspots(metrics) {
    const mapView = (metrics && metrics.map_view) || {};
    const extent = mapView.extent || {};
    const gauges = markDualRoleGaugeRows(
      Array.isArray(metrics && metrics.gauges) ? metrics.gauges : []
    );

    const fullMetricByKey = new Map();
    const lineMetricByFamily = new Map();

    gauges.forEach((row) => {
      const kind = obsGaugeKind(row);
      if (kind !== "line") return;

      const familyKey = row.role_family_key || obsGaugeFamilyKey(row);
      if (!familyKey) return;

      lineMetricByFamily.set(familyKey, row);
    });

    gauges.forEach((row) => {
      const kind = obsGaugeKind(row);
      const key = obsGaugeMapKey({ ...row, map_kind: kind });
      if (key) fullMetricByKey.set(key, row);
    });

    function mergeFullMetric(row, kind) {
      const geometryRow = { ...row, map_kind: kind };
      const key = obsGaugeMapKey(geometryRow);
      const fullRow = fullMetricByKey.get(key) || {};
      const merged = {
        ...fullRow,
        ...geometryRow,
      };

      const familyKey = merged.role_family_key || obsGaugeFamilyKey(merged);
      const fullFamilyRows = gauges.filter((g) => obsGaugeFamilyKey(g) === familyKey);
      const kinds = new Set(fullFamilyRows.map((g) => obsGaugeKind(g)));
      const dualRole = Boolean(familyKey && kinds.has("point") && kinds.has("line"));

      const pairedLine = dualRole ? lineMetricByFamily.get(familyKey) || null : null;

      return {
        ...merged,
        role_family_key: familyKey,
        dual_role: dualRole,

        paired_line_id: pairedLine ? pairedLine.line_id : null,
        paired_line_gauge_name: pairedLine ? pairedLine.gauge_name : null,
        paired_sim_flow_peak_cms: pairedLine ? pairedLine.sim_flow_peak_cms : null,
        paired_obs_flow_peak_cms: pairedLine ? pairedLine.obs_flow_peak_cms : null,
        paired_flow_peak_error_cms: pairedLine ? pairedLine.flow_peak_error_cms : null,
        paired_flow_peak_error_pct: pairedLine ? flowPeakPercentError(pairedLine) : null,
        paired_flow_mean_error_cms: pairedLine ? pairedLine.flow_mean_error_cms : null,
        paired_flow_mean_error_pct: pairedLine ? flowMeanPercentError(pairedLine) : null,
      };
    }

    const rawPoints = Array.isArray(mapView.points) && mapView.points.length
      ? mapView.points
      : gauges.filter((row) => obsGaugeKind(row) !== "line");

    const rawLines = Array.isArray(mapView.lines) && mapView.lines.length
      ? mapView.lines
      : gauges.filter((row) => obsGaugeKind(row) === "line");

    const points = rawPoints.map((row) => {
      const merged = mergeFullMetric(row, "point");

      const pct = Number.isFinite(Number(merged.left_pct)) && Number.isFinite(Number(merged.top_pct))
        ? { left_pct: Number(merged.left_pct), top_pct: Number(merged.top_pct) }
        : obsMapPctFromXY(merged, extent);

      if (!pct) return null;

      return {
        ...merged,
        ...pct,
        map_kind: "point",
      };
    }).filter(Boolean);

    const lines = rawLines.map((row) => {
      const merged = mergeFullMetric(row, "line");

      const pct = Number.isFinite(Number(merged.left_pct)) && Number.isFinite(Number(merged.top_pct))
        ? { left_pct: Number(merged.left_pct), top_pct: Number(merged.top_pct) }
        : obsMapPctFromXY(merged, extent);

      if (!pct) return null;

      return {
        ...merged,
        ...pct,
        map_kind: "line",
      };
    }).filter(Boolean);

    const pointDualFamilies = new Set(
      points
        .filter((row) => row.dual_role && row.role_family_key)
        .map((row) => row.role_family_key)
    );

    const visibleLines = lines.filter((row) => {
      if (!row.dual_role) return true;
      if (!row.role_family_key) return true;
      return !pointDualFamilies.has(row.role_family_key);
    });

    return [...points, ...visibleLines];
  }

  function renderObsMapHotspot(row) {
    const left = Number(row.left_pct);
    const top = Number(row.top_pct);

    if (!Number.isFinite(left) || !Number.isFinite(top)) {
      return "";
    }

    const kind = String(row.map_kind || row.kind || "point").toLowerCase();
    const mapKey = obsGaugeMapKey(row);
    const familyKey = row.role_family_key || obsGaugeFamilyKey(row);
    const isDual = Boolean(row.dual_role);
    const severity = String(row.severity_label || "unknown")
      .toLowerCase()
      .replace(/[^a-z0-9_-]/g, "");

    const payload = {
      type: kind,
      gauge_id: displayGaugeId(row.gauge_id || row.match_id || row.sim_id || ""),
      gauge_name: cleanObsId(row.gauge_name || ""),
      line_id: kind === "line" ? cleanObsId(row.line_id || row.match_id || "") : "",

      role_family_key: familyKey,
      dual_role: isDual,

      // Point / water-level values
      sim_wl_peak_m: kind === "line" ? null : row.sim_wl_peak_m,
      obs_wl_peak_m: kind === "line" ? null : row.obs_wl_peak_m,
      wl_error_m: kind === "line" ? null : row.wl_error_m,
      wl_error_pct: kind === "line" ? null : safePercentError(row.wl_error_m, row.obs_wl_peak_m),

      // Line / flow values for normal line markers
      flow_peak_error_pct: kind === "line" ? flowPeakPercentError(row) : null,
      sim_flow_peak_cms: kind === "line" ? row.sim_flow_peak_cms : null,
      obs_flow_peak_cms: kind === "line" ? row.obs_flow_peak_cms : null,
      flow_peak_error_cms: kind === "line" ? row.flow_peak_error_cms : null,
      flow_mean_error_cms: kind === "line" ? row.flow_mean_error_cms : null,
      flow_mean_error_pct: kind === "line" ? flowMeanPercentError(row) : null,

      // Paired CRS/line values for dual-role triangle markers
      paired_line_id: isDual ? cleanObsId(row.paired_line_id || "") : "",
      paired_sim_flow_peak_cms: isDual ? row.paired_sim_flow_peak_cms : null,
      paired_obs_flow_peak_cms: isDual ? row.paired_obs_flow_peak_cms : null,
      paired_flow_peak_error_cms: isDual ? row.paired_flow_peak_error_cms : null,
      paired_flow_peak_error_pct: isDual ? row.paired_flow_peak_error_pct : null,
      paired_flow_mean_error_cms: isDual ? row.paired_flow_mean_error_cms : null,
      paired_flow_mean_error_pct: isDual ? row.paired_flow_mean_error_pct : null,
    };

    return `
      <button
        type="button"
        class="obs-map-hotspot obs-map-hotspot-${escapeAttr(kind)} ${isDual ? "obs-map-hotspot-dual" : ""}"
        style="left:${left.toFixed(4)}%; top:${top.toFixed(4)}%;"
        data-obs-point="${escapeAttr(JSON.stringify(payload))}"
        data-obs-map-key="${escapeAttr(mapKey)}"
        data-obs-family-key="${escapeAttr(familyKey)}"
        aria-label="${escapeAttr(payload.gauge_id || payload.line_id || "gauge")}"
      ></button>
    `;
  }

  function renderObsSpatialMap(metrics, manifest = null) {
    const mapView = (metrics && metrics.map_view) || {};
    const overlays = mapView.overlays || {};
    const manifestOverlays = (manifest && manifest.optional_overlays) || {};
    const hotspots = buildObsMapHotspots(metrics);

    function overlayRel(key, fallback = "") {
      if (overlays[key]) return overlays[key];

      const item = manifestOverlays[key] || null;
      if (item && item.relpath) return item.relpath;
      if (item && item.path) return item.path;

      return fallback;
    }

    const baseRel = overlayRel(
      "satellite_background",
      "review/maps/satellite_background.png"
    );

    const activeAreaRel = overlayRel(
      "model_active_area",
      "review/maps/model_active_area_overlay.png"
    );

    const flowSurfaceRel = overlayRel("obs_flow_error_surface", "");
    const wlSurfaceRel = overlayRel("obs_wl_error_surface", "");

    return `
      <figure class="obs-map-frame">
        <div class="obs-map-layout">
          <div class="obs-context-map-stage" id="obs-map-stage">
            <a href="${obsGaugeArtifactUrl(baseRel)}" target="_blank" rel="noopener" class="obs-context-map-link">
              <img
                class="obs-context-map-img"
                src="${obsGaugeArtifactUrl(baseRel)}"
                alt="Satellite background"
              >
            </a>

            ${activeAreaRel ? `
              <img
                id="obs-active-area-overlay"
                class="obs-map-base-overlay"
                src="${obsGaugeArtifactUrl(activeAreaRel)}"
                alt="Model active area"
              >
            ` : ""}

            ${wlSurfaceRel ? `
              <img
                id="obs-wl-error-surface"
                class="obs-error-surface"
                src="${obsGaugeArtifactUrl(wlSurfaceRel)}"
                alt="Water-level error surface"
              >
            ` : ""}

            ${flowSurfaceRel ? `
              <img
                id="obs-flow-error-surface"
                class="obs-error-surface"
                src="${obsGaugeArtifactUrl(flowSurfaceRel)}"
                alt="Flow error surface"
              >
            ` : ""}

            <div class="obs-map-hotspot-layer">
              ${hotspots.map(renderObsMapHotspot).join("")}
            </div>

            <div id="obs-map-tooltip" class="obs-map-tooltip" style="display:none;"></div>
          </div>

          <aside class="obs-map-toggle-panel">
            <h4>Error maps</h4>

            <button
              type="button"
              class="secondary obs-error-toggle"
              id="obs-flow-error-toggle"
              data-target="obs-flow-error-surface"
              ${flowSurfaceRel ? "" : "disabled"}
            >
              Flow error map
            </button>

            <button
              type="button"
              class="secondary obs-error-toggle"
              id="obs-wl-error-toggle"
              data-target="obs-wl-error-surface"
              ${wlSurfaceRel ? "" : "disabled"}
            >
              Water-level error map
            </button>

            <p class="obs-map-toggle-note">
              Green = lower relative error; red = higher relative error within this run.
              ${wlSurfaceRel ? "" : "<br>Water-level error is unavailable until NAVD88 observed WL values are added."}
            </p>
          </aside>
        </div>

        <figcaption>
          Obs/gauge validation map with optional error surfaces. Point-only gauges are circles; CRS-only gauges are rectangles; shared point + CRS gauges are triangles.
        </figcaption>
      </figure>
    `;
  }

  function renderObsMapPoint(point) {
    const left = Number(point.left_pct);
    const top = Number(point.top_pct);

    if (!Number.isFinite(left) || !Number.isFinite(top)) {
      return "";
    }

    const payload = {
      type: "point",
      gauge_id: displayGaugeId(point.gauge_id || ""),
      gauge_name: cleanObsId(point.gauge_name || ""),
      sim_wl_peak_m: point.sim_wl_peak_m,
      flow_mean_error_cms: point.flow_mean_error_cms,
      flow_peak_error_cms: point.flow_peak_error_cms,
    };

    return `
      <button
        type="button"
        class="obs-map-marker obs-map-point"
        style="left:${left.toFixed(4)}%; top:${top.toFixed(4)}%;"
        data-obs-point="${escapeAttr(JSON.stringify(payload))}"
        aria-label="${escapeAttr(payload.gauge_id || "gauge")}"
      ></button>
    `;
  }

  function renderObsMapLine(line) {
    const left = Number(line.left_pct);
    const top = Number(line.top_pct);

    if (!Number.isFinite(left) || !Number.isFinite(top)) {
      return "";
    }

    const payload = {
      type: "line",
      gauge_id: displayGaugeId(line.gauge_id || ""),
      gauge_name: cleanObsId(line.gauge_name || ""),
      line_id: cleanObsId(line.line_id || ""),
      flow_mean_error_cms: line.flow_mean_error_cms,
      flow_peak_error_cms: line.flow_peak_error_cms,
    };

    return `
      <button
        type="button"
        class="obs-map-marker obs-map-line"
        style="left:${left.toFixed(4)}%; top:${top.toFixed(4)}%;"
        data-obs-point="${escapeAttr(JSON.stringify(payload))}"
        aria-label="${escapeAttr(payload.line_id || payload.gauge_id || "line gauge")}"
      ></button>
    `;
  }

  function wireObsDialMapHighlight() {
    const stage = $("obs-map-stage");
    if (!stage) return;

    const cards = Array.from(document.querySelectorAll(".obs-dial[data-obs-map-key]"));
    const hotspots = Array.from(stage.querySelectorAll(".obs-map-hotspot[data-obs-map-key]"));

    function getFamilyForKey(key) {
      const card = cards.find((el) => el.getAttribute("data-obs-map-key") === key);
      if (card && card.getAttribute("data-obs-family-key")) {
        return card.getAttribute("data-obs-family-key");
      }

      const spot = hotspots.find((el) => el.getAttribute("data-obs-map-key") === key);
      if (spot && spot.getAttribute("data-obs-family-key")) {
        return spot.getAttribute("data-obs-family-key");
      }

      return "";
    }

    function elementMatchesSelection(el, key, familyKey) {
      const elKey = el.getAttribute("data-obs-map-key") || "";
      const elFamily = el.getAttribute("data-obs-family-key") || "";

      if (elKey === key) return true;
      if (familyKey && elFamily && elFamily === familyKey) return true;

      return false;
    }

    function selectMapKey(key, shouldScroll = false) {
      if (!key) return;

      const familyKey = getFamilyForKey(key);
      
      selectObsGaugeTimeseries(key, familyKey);

      cards.forEach((card) => {
        card.classList.toggle("selected", elementMatchesSelection(card, key, familyKey));
      });

      const selectedHotspots = [];

      hotspots.forEach((spot) => {
        const selected = elementMatchesSelection(spot, key, familyKey);
        spot.classList.toggle("selected", selected);
        if (selected) selectedHotspots.push(spot);
      });

      selectedHotspots.forEach((spot) => {
        spot.classList.remove("pulse");
        void spot.offsetWidth;
        spot.classList.add("pulse");
      });

      if (shouldScroll) {
        stage.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }

    cards.forEach((card) => {
      card.addEventListener("click", () => {
        selectMapKey(card.getAttribute("data-obs-map-key") || "", false);
      });

      card.addEventListener("keydown", (ev) => {
        if (ev.key !== "Enter" && ev.key !== " ") return;
        ev.preventDefault();
        selectMapKey(card.getAttribute("data-obs-map-key") || "", false);
      });
    });

    hotspots.forEach((spot) => {
      spot.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        selectMapKey(spot.getAttribute("data-obs-map-key") || "", false);
      });
    });
  }

  function wireObsErrorMapToggles() {
    const buttons = Array.from(document.querySelectorAll(".obs-error-toggle"));

    function setSurface(targetId) {
      document.querySelectorAll(".obs-error-surface").forEach((img) => {
        img.classList.toggle("active", img.id === targetId);
      });

      buttons.forEach((button) => {
        button.classList.toggle("active", button.dataset.target === targetId);
        button.setAttribute("aria-pressed", button.dataset.target === targetId ? "true" : "false");
      });
    }

    buttons.forEach((button) => {
      button.setAttribute("aria-pressed", "false");

      button.addEventListener("click", () => {
        if (button.disabled) return;

        const targetId = button.dataset.target || "";
        const target = targetId ? document.getElementById(targetId) : null;

        if (!target) return;

        const alreadyActive = target.classList.contains("active");

        if (alreadyActive) {
          setSurface("");
        } else {
          setSurface(targetId);
        }
      });
    });
  }

  function wireObsSpatialMapTooltip() {
    const stage = $("obs-map-stage");
    const tooltip = $("obs-map-tooltip");

    if (!stage || !tooltip) return;

    function tooltipHtml(data) {
      const lines = [];
      if (data.gauge_id) lines.push(`<strong>${escapeHtml(data.gauge_id)}</strong>`);
      if (data.gauge_name) lines.push(`<span>${escapeHtml(data.gauge_name)}</span>`);
      if (data.line_id) lines.push(`<span>CRS: ${escapeHtml(data.line_id)}</span>`);
      if (hasMetricValue(data.sim_wl_peak_m)) {
        lines.push(`<span>Peak WL: ${escapeHtml(fmtNumber(data.sim_wl_peak_m, 2, " m"))}</span>`);
      }
      if (hasMetricValue(data.obs_wl_peak_m)) {
        lines.push(`<span>Obs peak WL: ${escapeHtml(fmtNumber(data.obs_wl_peak_m, 2, " m"))}</span>`);
      }

      if (hasMetricValue(data.wl_error_m)) {
        lines.push(`<span>Peak WL error: ${escapeHtml(fmtNumber(data.wl_error_m, 2, " m"))}</span>`);
      }

      if (hasMetricValue(data.wl_error_pct)) {
        lines.push(`<span>Peak WL % error: ${escapeHtml(fmtNumber(data.wl_error_pct, 1, "%"))}</span>`);
      }

      if (data.dual_role) {
        lines.push(`<span><strong>CRS / flow role</strong></span>`);

        if (data.paired_line_id) {
          lines.push(`<span>Line: ${escapeHtml(data.paired_line_id)}</span>`);
        }

        if (hasMetricValue(data.paired_sim_flow_peak_cms)) {
          lines.push(`<span>Sim peak flow: ${escapeHtml(fmtNumber(data.paired_sim_flow_peak_cms, 1, " m³/s"))}</span>`);
        }

        if (hasMetricValue(data.paired_obs_flow_peak_cms)) {
          lines.push(`<span>Obs peak flow: ${escapeHtml(fmtNumber(data.paired_obs_flow_peak_cms, 1, " m³/s"))}</span>`);
        }

        if (hasMetricValue(data.paired_flow_peak_error_cms)) {
          lines.push(`<span>Peak flow error: ${escapeHtml(fmtNumber(data.paired_flow_peak_error_cms, 1, " m³/s"))}</span>`);
        }

        if (hasMetricValue(data.paired_flow_peak_error_pct)) {
          lines.push(`<span>Peak flow % error: ${escapeHtml(fmtNumber(data.paired_flow_peak_error_pct, 1, "%"))}</span>`);
        }

        if (hasMetricValue(data.paired_flow_mean_error_cms)) {
          lines.push(`<span>Mean flow bias: ${escapeHtml(fmtNumber(data.paired_flow_mean_error_cms, 1, " m³/s"))}</span>`);
        }
      }

      if (hasMetricValue(data.flow_peak_error_pct)) {
        lines.push(`<span>Peak % error: ${escapeHtml(fmtNumber(data.flow_peak_error_pct, 1, "%"))}</span>`);
      }

      if (hasMetricValue(data.sim_flow_peak_cms)) {
        lines.push(`<span>Peak flow: ${escapeHtml(fmtNumber(data.sim_flow_peak_cms, 1, " m³/s"))}</span>`);
      }

      if (hasMetricValue(data.flow_mean_error_cms)) {
        lines.push(`<span>Mean bias: ${escapeHtml(fmtNumber(data.flow_mean_error_cms, 1, " m³/s"))}</span>`);
      }
      return lines.join("");
    }

    stage.querySelectorAll(".obs-map-hotspot").forEach((dot) => {
      dot.addEventListener("mousemove", (ev) => {
        let data = {};
        try {
          data = JSON.parse(dot.getAttribute("data-obs-point") || "{}");
        } catch (err) {
          data = {};
        }

        tooltip.innerHTML = tooltipHtml(data);
        tooltip.style.display = "grid";

        const rect = stage.getBoundingClientRect();
        const x = ev.clientX - rect.left + 14;
        const y = ev.clientY - rect.top + 14;

        tooltip.style.left = `${x}px`;
        tooltip.style.top = `${y}px`;
      });

      dot.addEventListener("mouseleave", () => {
        tooltip.style.display = "none";
      });
    });
  }

  function renderObsGaugeReady(status, manifest, metrics) {
    state.obsStatus = status || null;
    state.obsManifest = manifest || null;
    state.obsMetrics = metrics || null;

    state.obsTimeseries = null;
    state.obsTimeseriesByKey = new Map();
    state.obsTimeseriesLoading = false;
    state.obsTimeseriesError = "";
    state.selectedObsTimeseriesKey = "";
    state.selectedObsTimeseriesFamilyKey = "";
    state.selectedObsTimeseriesMetric = "auto";


    if (state.obsPollTimer) {
      window.clearTimeout(state.obsPollTimer);
      state.obsPollTimer = null;
    }

    const panel = $("review-tool-body");
    if (!panel) return;

    const overall = (metrics && metrics.overall) || (manifest && manifest.overall) || {};
    const gauges = (metrics && Array.isArray(metrics.gauges)) ? metrics.gauges : [];
    const displayGauges = buildObsGaugeDisplayRows(gauges);
    const pointRows = displayGauges.filter((row) => obsGaugeKind(row) !== "line");
    const lineRows = displayGauges.filter((row) => obsGaugeKind(row) === "line");
    const files = (manifest && manifest.files) || {};

    const hasWlError = gauges.some((row) => hasMetricValue(row.wl_error_m) || hasMetricValue(row.wl_rmse_m));
    const hasFlowMeanError = gauges.some((row) => hasMetricValue(row.flow_mean_error_cms));
    const hasFlowPeakError = gauges.some((row) => hasMetricValue(row.flow_peak_error_cms));

    panel.innerHTML = `
      <h3>Obs / gauges</h3>
      <p class="section-intro">
        Cached validation metrics stored inside this run folder. Point circles show modeled peak WL. CRS line boxes show signed mean/peak flow error and peak simulated flow, with color normalized by flow-error magnitude.
      </p>
      ${renderSlurmStatus(status, "obs/gauge validation products")}
      ${renderObsValidationPicker()}

      <div class="review-map-controls obs-rerun-controls">
        <button type="button" id="rerun-obs-gauges-btn">Rerun Slurm</button>
        <button type="button" class="secondary" id="rerun-obs-gauges-local-btn">Rerun locally</button>
      </div>

      <div class="obs-overall-grid">
        ${renderObsOverallCard("WL RMSE", hasWlError ? overall.waterlevel_rmse_m : null, " m", 2)}
        ${renderObsOverallCard("WL MAE", hasWlError ? overall.waterlevel_mae_m : null, " m", 2)}
        ${renderObsOverallCard("Flow mean RMSE", hasFlowMeanError ? overall.flow_mean_rmse_cms : null, " cms", 1)}
        ${renderObsOverallCard("Flow peak RMSE", hasFlowPeakError ? overall.flow_peak_rmse_cms : null, " cms", 1)}
        ${renderObsOverallCard("Matched", overall.matched_count, "", 0)}
        ${renderObsOverallCard("Unmatched", overall.unmatched_count, "", 0)}
      </div>

      ${renderObsSpatialMap(metrics, manifest)}

      ${renderObsGaugeTimeseriesPanel()}

      <h3 style="margin-top: 16px;">Point gauges</h3>
      <div class="obs-dial-grid">
        ${pointRows.length ? pointRows.map(renderObsGaugeDial).join("") : `<div class="empty-note">No point gauge rows were available.</div>`}
      </div>

      <h3 style="margin-top: 18px;">CRS line gauges</h3>
      <div class="obs-line-grid">
        ${lineRows.length ? lineRows.map(renderObsGaugeDial).join("") : `<div class="empty-note">No line gauge rows were available.</div>`}
      </div>

      <details style="margin-top: 16px;">
        <summary>Obs/gauge metrics JSON</summary>
        <div class="details-body"><pre>${escapeHtml(JSON.stringify(metrics || {}, null, 2))}</pre></div>
      </details>
    `;

    wireObsValidationPicker();
    wireObsSpatialMapTooltip();
    wireObsErrorMapToggles();
    wireObsDialMapHighlight();

    renderSelectedObsGaugeTimeseries();
    loadObsGaugeTimeseries(files.timeseries || (metrics && metrics.timeseries && metrics.timeseries.relpath) || "");
    wireObsGaugeTimeseriesModeButtons();

    const rerunBtn = $("rerun-obs-gauges-btn");
    if (rerunBtn) {
      rerunBtn.addEventListener("click", () => submitObsGaugeJob(false));
    }
    const rerunLocalBtn = $("rerun-obs-gauges-local-btn");
    if (rerunLocalBtn) {
      rerunLocalBtn.addEventListener("click", () => submitObsGaugeJob(true));
    }
  }



  function obsGaugeProductHasErrorSurfacePaths(metrics, manifest) {
    const overlays = ((metrics && metrics.map_view) || {}).overlays || {};
    const manifestOverlays = (manifest && manifest.optional_overlays) || {};
  
    const flowRel =
      overlays.obs_flow_error_surface ||
      (manifestOverlays.obs_flow_error_surface && manifestOverlays.obs_flow_error_surface.relpath);
  
    const wlRel =
      overlays.obs_wl_error_surface ||
      (manifestOverlays.obs_wl_error_surface && manifestOverlays.obs_wl_error_surface.relpath);
  
    return Boolean(flowRel && wlRel);
  }
  
  async function loadObsGaugeProductsFresh() {
    const out = {
      metrics: null,
      obsManifest: null,
      mapManifest: null,
    };
  
    try {
      out.metrics = await getJson(obsGaugeArtifactUrl("review/obs_gauges/obs_gauges_metrics.json"));
    } catch (err) {
      out.metrics = null;
    }
  
    try {
      out.obsManifest = await getJson(obsGaugeArtifactUrl("review/obs_gauges/obs_gauges_manifest.json"));
    } catch (err) {
      out.obsManifest = null;
    }
  
    try {
      out.mapManifest = await getJson(obsGaugeArtifactUrl("review/maps/layers_manifest.json"));
    } catch (err) {
      out.mapManifest = null;
    }
  
    return out;
  }
  
  function mergeObsGaugeManifests(obsManifest, mapManifest) {
    const obs = obsManifest || {};
    const map = mapManifest || {};
  
    return {
      ...obs,
      map_layers_manifest: mapManifest || null,
      optional_overlays: {
        ...((obs && obs.optional_overlays) || {}),
        ...((map && map.optional_overlays) || {}),
      },
    };
  }



  async function loadObsGaugeStatus() {
    if (!state.selectedRun || state.activeReviewTool !== "obs") return;

    const runAtStart = state.selectedRun;
    const panel = $("review-tool-body");
  
    try {
      const data = await getJson(`/api/review/obs-gauges/status?run=${encodeURIComponent(runAtStart)}`);
      if (!isCurrentReviewTool("obs", runAtStart)) return;

      const status = data.status || {};
      const stateText = String(status.state || "").toLowerCase();
  
      state.obsStatus = status;
      state.obsManifest = data.manifest || null;
      state.obsMetrics = data.metrics || null;
  
      if (stateText === "ready") {
        const fresh = await loadObsGaugeProductsFresh();
        if (!isCurrentReviewTool("obs", runAtStart)) return;

        state.obsMapManifest = fresh.mapManifest || null;
  
        const metrics = fresh.metrics || data.metrics || null;
        const mergedManifest = mergeObsGaugeManifests(
          fresh.obsManifest || data.manifest || null,
          fresh.mapManifest || null
        );
  
        if (metrics && typeof metrics === "object") {
          state.obsManifest = mergedManifest;
          state.obsMetrics = metrics;
          renderObsGaugeReady(status, mergedManifest, metrics);
          return;
        }
  
        renderObsGaugeProgress({
          ...status,
          state: "running",
          message: "Obs/gauge job finished. Waiting for fresh metrics JSON to become readable.",
        });
        return;
      }
  
      if (["submitted", "queued", "pending", "running", "submitting"].includes(stateText)) {
        renderObsGaugeProgress(status);
        return;
      }
  
      if (["failed", "submit_failed", "error"].includes(stateText)) {
        renderObsGaugeFailed(status);
        return;
      }
  
      renderObsGaugeMissing(status);
  
    } catch (err) {
      if (!isCurrentReviewTool("obs", runAtStart)) return;

      if (panel) {
        panel.innerHTML = `
          <h3>Obs / gauges</h3>
          <div class="warning warning-major">
            <h4>Could not load obs/gauge status</h4>
            <p>${escapeHtml(err.message)}</p>
          </div>
        `;
      }
    }
  }

  async function submitObsGaugeJob(direct = false) {
    if (!state.selectedRun || state.activeReviewTool !== "obs") return;

    const runAtSubmit = state.selectedRun;
    const validationCsv = currentObsValidationCsvPath();
    state.obsJobStartedThisView = true;

    const panel = $("review-tool-body");
    if (panel) {
      panel.innerHTML = `
        <h3>Obs / gauges</h3>
        <div class="review-spinner-row">
          <div class="review-spinner"></div>
          <div>${direct ? "Running obs/gauge validation locally in this desktop session…" : "Sending obs/gauge validation job to Slurm…"}</div>
        </div>
        <div class="empty-note">
          Validation CSV: <span class="mono">${escapeHtml(validationCsv || "(auto-discover)")}</span>
        </div>
      `;
    }

    try {
      const payload = {
        run: runAtSubmit,
        force: true,
      };

      if (direct) {
        payload.direct = true;
      }

      if (validationCsv) {
        payload.validation_csv = validationCsv;
      }

      const data = await postJson("/api/review/obs-gauges/submit", payload);
      if (!isCurrentReviewTool("obs", runAtSubmit)) return;

      const status = data.status || {};
      renderObsGaugeProgress(status);
    } catch (err) {
      if (!isCurrentReviewTool("obs", runAtSubmit)) return;

      if (panel) {
        panel.innerHTML = `
          <h3>Obs / gauges</h3>
          <div class="warning warning-major">
            <h4>Could not submit obs/gauge job</h4>
            <p>${escapeHtml(err.message)}</p>
          </div>
          ${renderObsValidationPicker()}
          <div class="review-map-controls">
            <button type="button" id="submit-obs-gauges-btn">Submit Slurm</button>
            <button type="button" class="secondary" id="run-obs-gauges-local-btn">Run locally</button>
          </div>
        `;

        wireObsValidationPicker();
        $("submit-obs-gauges-btn").addEventListener("click", () => submitObsGaugeJob(false));

        const localObsBtn = $("run-obs-gauges-local-btn");
        if (localObsBtn) {
          localObsBtn.addEventListener("click", () => submitObsGaugeJob(true));
        }
      }
    }
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
