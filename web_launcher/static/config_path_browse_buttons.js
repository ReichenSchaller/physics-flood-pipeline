(function () {
  "use strict";

  const DEFAULT_DATA_ROOT = "";

  function getConfigPathBrowseSettings() {
    return window.CONFIG_PATH_BROWSE_SETTINGS || {};
  }

  function getLauncherDefaults() {
    if (window.LauncherDefaults) {
      if (typeof window.LauncherDefaults.getAll === "function") {
        return window.LauncherDefaults.getAll() || {};
      }

      if (typeof window.LauncherDefaults === "object") {
        return window.LauncherDefaults;
      }
    }

    return {};
  }

  function launcherDefault(key) {
    const cleanKey = String(key || "").trim();
    if (!cleanKey) return "";

    if (window.LauncherDefaults) {
      if (typeof window.LauncherDefaults.get === "function") {
        const value = String(window.LauncherDefaults.get(cleanKey) || "").trim();
        if (value) return value;
      }

      if (typeof window.LauncherDefaults.getDefault === "function") {
        const value = String(window.LauncherDefaults.getDefault(cleanKey) || "").trim();
        if (value) return value;
      }
    }

    const allDefaults = getLauncherDefaults();
    return String(allDefaults[cleanKey] || "").trim();
  }

  function firstNonEmptyValueForKey(key) {
    const el = document.querySelector(`[data-key="${key}"]`);
    if (!el) return "";

    const raw = String(el.value || "").trim();
    if (!raw) return "";

    if (raw.startsWith("[")) {
      try {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return String(parsed[0] || "").trim();
        }
      } catch (err) {
        return raw;
      }
    }

    return raw;
  }

  function currentDataRoot() {
    const settings = getConfigPathBrowseSettings();
    const settingsDefaultStart = String(settings.defaultStart || "").trim();
    const launcherDataRoot = launcherDefault("dataRoot");

    const dataRootInput = document.querySelector('[data-key="data_root"]');
    const pageValue = dataRootInput ? String(dataRootInput.value || "").trim() : "";

    // Settings are the source of truth for machine-specific roots.
    // Hidden page defaults are allowed only as a fallback when Settings are absent.
    if (launcherDataRoot) {
      if (dataRootInput && pageValue !== launcherDataRoot) {
        dataRootInput.value = launcherDataRoot;
      }
      return launcherDataRoot;
    }

    return pageValue || settingsDefaultStart || DEFAULT_DATA_ROOT;
  }

  function currentCatalogRoot() {
    const launcherDefaults = getLauncherDefaults();

    return (
      firstNonEmptyValueForKey("reduced_event_catalog_path") ||
      firstNonEmptyValueForKey("event_catalog_path") ||
      firstNonEmptyValueForKey("data_catalogs") ||
      launcherDefaults.eventCatalogRoot ||
      launcherDefaults.catalogRoot ||
      currentDataRoot()
    );
  }

  function currentPipelineRoot() {
    const settings = getConfigPathBrowseSettings();
    const launcherDefaults = getLauncherDefaults();

    return (
      launcherDefaults.projectRoot ||
      settings.backendStart ||
      settings.pipelineStart ||
      ""
    );
  }

  function keyIsBackendRuntimePath(key) {
    return new Set([
      "project_root",
      "runner_file",
      "runner_python",
      "launcher_file",
      "launcher_python",
      "preprocess_stage_script",
      "postprocess_stage_script",
      "sfincs_container",
      "sfincs_container_path"
    ]).has(key);
  }


  function defaultKeyForInput(input) {
    const key = input ? String(input.dataset.key || "") : "";

    if (!key) return "";

    if (key === "conda_env_path") {
      return "condaEnvPath";
    }

    if (key === "conda_python") {
      return "condaPython";
    }

    if (key === "output_root" || key.includes("run")) {
      return "runRoot";
    }

    if (keyIsBackendRuntimePath(key)) {
      return "projectRoot";
    }

    if (
      key.includes("native") ||
      key.endsWith("_input_dirs")
    ) {
      return "nativeSfincsRoot";
    }

    if (
      key === "reduced_event_catalog_path" ||
      key === "event_catalog_path" ||
      key === "event_catalog_paths" ||
      key === "data_catalogs"
    ) {
      return "eventCatalogRoot";
    }

    return "catalogRoot";
  }

  function currentBrowseStartForInput(input) {
    const key = input ? String(input.dataset.key || "") : "";
    const launcherDefaults = getLauncherDefaults();

    const pipelineRoot = currentPipelineRoot();
    const envRoot = `${pipelineRoot.replace(/\/+$/, "")}/envs`;

    // Environment folder picker: start at the folder containing all envs.
    if (key === "conda_env_path") {
      return envRoot;
    }

    // Python executable picker: start in bin/ of the currently selected env.
    if (key === "conda_python") {
      const selectedEnv =
        firstNonEmptyValueForKey("conda_env_path") ||
        launcherDefaults.condaEnvPath ||
        `${envRoot}/sfincs`;

      return `${String(selectedEnv).replace(/\/+$/, "")}/bin`;
    }

    // Other backend/runtime files should start at the pipeline root.
    if (keyIsBackendRuntimePath(key)) {
      return pipelineRoot;
    }

    if (
      key.includes("native") ||
      key.endsWith("_input_dirs")
    ) {
      return launcherDefaults.nativeSfincsRoot || currentDataRoot();
    }

    if (
      key === "reduced_event_catalog_path" ||
      key === "event_catalog_path" ||
      key === "data_catalogs"
    ) {
      return launcherDefaults.eventCatalogRoot || launcherDefaults.catalogRoot || currentDataRoot();
    }

    if (
      key.includes("run") ||
      key === "output_root"
    ) {
      return launcherDefaults.runRoot || currentDataRoot();
    }

    return currentCatalogRoot();
  }

  function keyIsPathLike(key) {
    if (!key) return false;

    const settings = getConfigPathBrowseSettings();
    const specialPathKeys = settings.specialPathKeys || [
      "data_catalogs",
      "event_catalog_paths",
      "reduced_event_catalog_path"
    ];

    return (
      specialPathKeys.includes(key) ||
      key.endsWith("_path") ||
      key.endsWith("_paths") ||
      key.endsWith("_file_path") ||
      key.endsWith("_input_dirs")
    );
  }

  function keyIsListLike(key, input) {
    if (!key) return false;

    const dataType = String(input.dataset.type || "").toLowerCase();

    return (
      key === "data_catalogs" ||
      key === "event_catalog_paths" ||
      key.endsWith("_paths") ||
      key.endsWith("_input_dirs") ||
      dataType === "list" ||
      dataType === "json" ||
      dataType === "array"
    );
  }

  function ensureInputId(input, key) {
    if (input.id) return input.id;

    const safeKey = String(key || "path")
      .replace(/[^A-Za-z0-9_-]+/g, "-")
      .replace(/^-+|-+$/g, "");

    let id = `auto-browse-${safeKey}`;
    let i = 2;

    while (document.getElementById(id)) {
      id = `auto-browse-${safeKey}-${i}`;
      i += 1;
    }

    input.id = id;
    return id;
  }

  function selectedSectionRoots() {
    const settings = getConfigPathBrowseSettings();
    const sectionNumbers = settings.sectionNumbers || ["5", "6", "11", "12"];

    const roots = [];

    document.querySelectorAll("h2").forEach((h2) => {
      const text = String(h2.textContent || "").trim();

      const matched = sectionNumbers.some((num) => {
        return text.startsWith(`${num}.`) || text.startsWith(`${num} `);
      });

      if (matched) {
        roots.push(h2.parentElement || h2);
      }
    });

    return roots;
  }

  function addBrowseStyles() {
    if (document.getElementById("config-path-browse-style")) return;

    const style = document.createElement("style");
    style.id = "config-path-browse-style";
    style.textContent = `
      .path-browse-wrap {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 8px;
        align-items: center;
      }

      .path-browse-wrap textarea {
        min-height: 42px;
      }

      .path-browse-wrap input,
      .path-browse-wrap textarea {
        width: 100%;
        min-width: 0;
      }

      .path-browse-wrap button {
        white-space: nowrap;
      }
    `;
    document.head.appendChild(style);
  }
  
  function dirname(pathText) {
    const text = String(pathText || "").trim();
    if (!text || !text.startsWith("/")) return "";

    const cleaned = text.replace(/\/+$/, "");
    const idx = cleaned.lastIndexOf("/");
    if (idx <= 0) return "/";

    return cleaned.slice(0, idx);
  }

  function inferBrowseModeForKey(key) {
    const directoryKeys = new Set([
      "project_root",
      "output_root",
      "data_root",
      "conda_env_path",
      "data_catalogs",
      "event_catalog_path",
      "event_catalog_paths",
      "reduced_event_catalog_path",
      "native_sfincs_input_dirs",
      "native_static_sfincs_input_dirs",
      "native_event_sfincs_input_dirs",
      "sfincs_file_override_search_dirs"
    ]);

    const fileKeys = new Set([
      "conda_python",
      "runner_python",
      "launcher_python",
      "sfincs_container",
      "sfincs_container_path",
      "preprocess_stage_script",
      "postprocess_stage_script"
    ]);

    if (directoryKeys.has(key)) return "directory";
    if (fileKeys.has(key)) return "file";

    if (key.endsWith("_root")) return "directory";
    if (key.endsWith("_dir")) return "directory";
    if (key.endsWith("_dirs")) return "directory";
    if (key.endsWith("_input_dirs")) return "directory";

    return "file";
  }
  

  function wrapWithBrowseButton(input) {
    if (!input || input.dataset.autoBrowseAdded === "true") return;

    const key = input.dataset.key || "";
    if (!keyIsPathLike(key)) return;

    const inputId = ensureInputId(input, key);
    const mode = inferBrowseModeForKey(key);

    const wrapper = document.createElement("div");
    wrapper.className = "path-browse-wrap";

    const button = document.createElement("button");
    button.className = "secondary";
    button.type = "button";
    button.textContent = "Browse";
    button.dataset.browseTarget = inputId;
    button.dataset.browseMode = mode;

    const defaultKey = defaultKeyForInput(input);
    if (defaultKey) {
      button.dataset.browseDefaultKey = defaultKey;
    }

    button.dataset.browseStart = currentBrowseStartForInput(input);
    
    if (key === "conda_env_path" || key === "conda_python") {
      button.dataset.browseForceStart = "true";
    }
    
    button.dataset.autoBrowseButton = "true";

    if (keyIsListLike(key, input)) {
      input.dataset.autoBrowseListLike = "true";
    }

    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);
    wrapper.appendChild(button);

    input.dataset.autoBrowseAdded = "true";
  }

  function enhanceConfigPathFields() {
    addBrowseStyles();

    const roots = selectedSectionRoots();

    roots.forEach((root) => {
      root.querySelectorAll("input[data-key], textarea[data-key]").forEach((input) => {
        wrapWithBrowseButton(input);
      });
    });

    const settings = getConfigPathBrowseSettings();
    const specialPathKeys = settings.specialPathKeys || [
      "data_catalogs",
      "event_catalog_paths",
      "reduced_event_catalog_path"
    ];

    specialPathKeys.forEach((key) => {
      document.querySelectorAll(`[data-key="${key}"]`).forEach((input) => {
        wrapWithBrowseButton(input);
      });
    });
  }

  function normalizeListLikeValue(input) {
    if (!input || input.dataset.autoBrowseListLike !== "true") return;

    const raw = String(input.value || "").trim();
    if (!raw) return;

    if (raw.startsWith("[") || raw.startsWith("{")) return;

    input.value = JSON.stringify([raw]);
  }

  document.addEventListener("DOMContentLoaded", enhanceConfigPathFields);

  document.addEventListener(
    "click",
    function (event) {
      const button = event.target.closest("[data-auto-browse-button='true']");
      if (!button) return;

      const targetId = button.dataset.browseTarget || "";
      const input = targetId ? document.getElementById(targetId) : null;

      const defaultKey = defaultKeyForInput(input);
      if (defaultKey) {
        button.dataset.browseDefaultKey = defaultKey;
      } else {
        delete button.dataset.browseDefaultKey;
      }

      button.dataset.browseStart = currentBrowseStartForInput(input);

      if (input && ["conda_env_path", "conda_python"].includes(String(input.dataset.key || ""))) {
        button.dataset.browseForceStart = "true";
      } else {
        delete button.dataset.browseForceStart;
      }
      
    },
    true
  );

  document.addEventListener("change", function (event) {
    const input = event.target;
    if (!input || !input.matches("[data-auto-browse-list-like='true']")) return;
    normalizeListLikeValue(input);
  });

  window.enhanceConfigPathFields = enhanceConfigPathFields;
})();