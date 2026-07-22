(function () {
  "use strict";

  const STORAGE_KEY = "sfincs_web_launcher_defaults_v1";
  const SERVER_DEFAULTS_URL = "/api/launcher-defaults";
  let SERVER_DEFAULTS = {};
  let SERVER_DEFAULTS_LOADED = false;

  const DEFAULTS = {
    dataRoot: "",
    catalogRoot: "",
    eventCatalogRoot: "",
    nativeSfincsRoot: "",
    overrideSourceRoot: "",
    runRoot: "",
    projectRoot: "",
    condaEnvPath: "",
    condaPython: "",
    contextilyPython: "",
    sfincsContainerPath: "",
    browseAllowedRoots: ""
  };

  const DEFAULT_LABELS = {
    dataRoot: "Data root",
    catalogRoot: "Catalog root",
    eventCatalogRoot: "Event catalog root",
    nativeSfincsRoot: "Native SFINCS root",
    overrideSourceRoot: "Override detect/source browse root",
    runRoot: "Run/output root",
    projectRoot: "Project/pipeline root",
    condaEnvPath: "SFINCS conda env path",
    condaPython: "SFINCS Python executable",
    contextilyPython: "Contextily/map Python executable",
    sfincsContainerPath: "SFINCS container path",
    browseAllowedRoots: "Additional allowed Browse roots"
  };

  const DEFAULT_HELP = {
    dataRoot: "Fallback root for general input files.",
    catalogRoot: "Root for static, event, validation, and reduced catalogs.",
    eventCatalogRoot: "Default place to browse for event catalog folders.",
    nativeSfincsRoot: "Default place to browse for folders containing native sfincs.* files.",
    overrideSourceRoot: "Default starting folder for Override Mode Detect + overrides source Browse buttons.",
    runRoot: "Default place for completed runs, Review, Compare, and normal launcher outputs.",
    projectRoot: "Shared pipeline bundle root used by backend runner.",
    condaEnvPath: "Shared SFINCS/HydroMT environment path.",
    condaPython: "Python executable used by backend preprocessing/postprocessing stages.",
    contextilyPython: "Python executable used for Review static-map generation. Usually the sfincs_contextily environment.",
    sfincsContainerPath: "Apptainer/Singularity SFINCS container image path.",
    browseAllowedRoots: "Optional extra absolute roots the backend path browser may access. Separate multiple paths with commas or new lines."
  };

  function readStoredDefaults() {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (err) {
      console.warn("Could not read launcher defaults:", err);
      return {};
    }
  }

  function getAllDefaults() {
    if (SERVER_DEFAULTS_LOADED) {
      return Object.assign({}, DEFAULTS, SERVER_DEFAULTS);
    }

    return Object.assign({}, DEFAULTS, readStoredDefaults());
  }
  
  async function saveDefaults(values) {
    const cleaned = {};

    Object.keys(DEFAULTS).forEach((key) => {
      const value = String(values[key] || "").trim();
      if (value) cleaned[key] = value;
    });

    try {
      const response = await fetch(SERVER_DEFAULTS_URL, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({defaults: cleaned})
      });

      const data = await response.json();

      if (!response.ok || !data.ok) {
        throw new Error(data.error || "Server rejected launcher defaults.");
      }

      SERVER_DEFAULTS = data.defaults || cleaned;
      SERVER_DEFAULTS_LOADED = true;

      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(SERVER_DEFAULTS, null, 2));
      return getAllDefaults();
    } catch (err) {
      console.warn("Could not save launcher defaults to server; using browser fallback:", err);
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(cleaned, null, 2));
      return getAllDefaults();
    }
  }

  async function resetDefaults() {
    try {
      const response = await fetch(SERVER_DEFAULTS_URL, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({defaults: {}})
      });

      const data = await response.json();

      if (!response.ok || !data.ok) {
        throw new Error(data.error || "Server rejected launcher defaults reset.");
      }

      SERVER_DEFAULTS = data.defaults || {};
      SERVER_DEFAULTS_LOADED = true;
      window.localStorage.removeItem(STORAGE_KEY);
      return getAllDefaults();
    } catch (err) {
      console.warn("Could not reset launcher defaults on server; resetting browser fallback:", err);
      window.localStorage.removeItem(STORAGE_KEY);
      return getAllDefaults();
    }
  }

  function getDefault(key) {
    return getAllDefaults()[key] || DEFAULTS[key] || "";
  }

  async function loadServerDefaults() {
    try {
      const response = await fetch(SERVER_DEFAULTS_URL);
      const data = await response.json();

      if (!response.ok || !data.ok) {
        throw new Error(data.error || "Could not load server launcher defaults.");
      }

      SERVER_DEFAULTS = data.defaults || {};
      SERVER_DEFAULTS_LOADED = true;

      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(SERVER_DEFAULTS, null, 2));

      window.dispatchEvent(new CustomEvent("launcher-defaults-changed", {
        detail: getAllDefaults()
      }));
    } catch (err) {
      console.warn("Could not load server launcher defaults; using browser fallback:", err);
      SERVER_DEFAULTS_LOADED = false;
    }
  }

  function ensureStyle() {
    if (document.getElementById("launcher-defaults-style")) return;

    const style = document.createElement("style");
    style.id = "launcher-defaults-style";
    style.textContent = `
      .launcher-settings-button {
        position: fixed;
        left: 74px;
        bottom: 18px;
        z-index: 2000;
        width: 46px;
        height: 46px;
        border-radius: 999px;
        border: 1px solid var(--border, #d0d7de);
        background: var(--panel, #ffffff);
        box-shadow: 0 8px 24px rgba(0,0,0,0.18);
        cursor: pointer;
        font-size: 20px;
        line-height: 1;
      }

      .launcher-settings-button:hover {
        transform: translateY(-1px);
      }

      .launcher-settings-backdrop {
        position: fixed;
        inset: 0;
        z-index: 2500;
        background: rgba(0,0,0,0.35);
        display: none;
        align-items: center;
        justify-content: center;
        padding: 24px;
      }

      .launcher-settings-backdrop.open {
        display: flex;
      }

      .launcher-settings-modal {
        width: min(920px, 96vw);
        max-height: 88vh;
        overflow: auto;
        background: var(--panel, #ffffff);
        color: var(--text, #111827);
        border: 1px solid var(--border, #d0d7de);
        border-radius: 18px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.28);
        padding: 22px;
      }

      .launcher-settings-modal h2 {
        margin-top: 0;
      }

      .launcher-settings-grid {
        display: grid;
        grid-template-columns: 220px minmax(0, 1fr);
        gap: 12px 14px;
        align-items: center;
      }

      .launcher-settings-grid label {
        font-weight: 650;
      }

      .launcher-settings-grid input {
        width: 100%;
        min-width: 0;
      }

      .launcher-settings-help {
        margin: 10px 0 18px;
        opacity: 0.82;
        line-height: 1.45;
      }

      .launcher-settings-actions {
        display: flex;
        gap: 10px;
        justify-content: flex-end;
        margin-top: 18px;
        flex-wrap: wrap;
      }
    `;

    document.head.appendChild(style);
  }

  function makeInputRow(grid, key, label, help) {
    const labelEl = document.createElement("label");
    labelEl.htmlFor = `launcher-default-${key}`;
    labelEl.textContent = DEFAULT_LABELS[key] || label;

    const wrap = document.createElement("div");

    const input = document.createElement("input");
    input.id = `launcher-default-${key}`;
    input.dataset.launcherDefaultKey = key;
    input.type = "text";
    input.value = getDefault(key);
    input.placeholder = DEFAULTS[key] || "";

    const small = document.createElement("div");
    small.className = "muted launcher-settings-help";
    small.textContent = DEFAULT_HELP[key] || help;

    wrap.appendChild(input);
    wrap.appendChild(small);

    grid.appendChild(labelEl);
    grid.appendChild(wrap);
  }

  function buildSettingsUi() {
    if (document.getElementById("launcher-settings-button")) return;

    ensureStyle();

    const button = document.createElement("button");
    button.id = "launcher-settings-button";
    button.className = "launcher-settings-button";
    button.type = "button";
    button.title = "Launcher settings";
    button.textContent = "⚙";

    const backdrop = document.createElement("div");
    backdrop.id = "launcher-settings-backdrop";
    backdrop.className = "launcher-settings-backdrop";

    const modal = document.createElement("div");
    modal.className = "launcher-settings-modal";
    modal.setAttribute("role", "dialog");
    modal.setAttribute("aria-modal", "true");
    modal.setAttribute("aria-label", "Launcher settings");

    const title = document.createElement("h2");
    title.textContent = "Launcher settings";

    const intro = document.createElement("p");
    intro.className = "launcher-settings-help";
    intro.textContent =
      "These settings control where Browse buttons start. They are saved to this launcher folder when possible, so they persist across app restarts and browser sessions. Browser storage is used only as a fallback.";

    const grid = document.createElement("div");
    grid.className = "launcher-settings-grid";

    makeInputRow(
      grid,
      "dataRoot",
      "Data root",
      "Fallback root for general input files."
    );

    makeInputRow(
      grid,
      "catalogRoot",
      "Catalog root",
      "Root for static, event, validation, and reduced catalogs."
    );

    makeInputRow(
      grid,
      "eventCatalogRoot",
      "Event catalog root",
      "Default place to browse for event catalog folders."
    );
    
    makeInputRow(
      grid,
      "nativeSfincsRoot",
      "Native SFINCS root",
      "Default place to browse for folders containing native sfincs.* files."
    );
    
    makeInputRow(
      grid,
      "overrideSourceRoot",
      "Override detect/source browse root",
      "Default starting folder for Override Mode Detect + overrides source Browse buttons."
    );

    makeInputRow(
      grid,
      "runRoot",
      "Run/output root",
      "Default place for completed runs and compare inputs."
    );
    
    makeInputRow(
      grid,
      "projectRoot",
      "Project/pipeline root",
      "Shared pipeline bundle root used by backend runner."
    );

    makeInputRow(
      grid,
      "condaEnvPath",
      "SFINCS conda env path",
      "Shared SFINCS/HydroMT environment path."
    );

    makeInputRow(
      grid,
      "condaPython",
      "SFINCS Python executable",
      "Python executable used by backend preprocessing/postprocessing stages."
    );

    makeInputRow(
      grid,
      "contextilyPython",
      "Contextily/map Python executable",
      "Python executable used for Review static-map generation. Usually the sfincs_contextily environment."
    );

    makeInputRow(
      grid,
      "sfincsContainerPath",
      "SFINCS container path",
      "Apptainer/Singularity SFINCS container image path."
    );

    makeInputRow(
      grid,
      "browseAllowedRoots",
      "Additional allowed Browse roots",
      "Optional extra absolute roots the backend path browser may access. Separate multiple paths with commas or new lines."
    );

    const actions = document.createElement("div");
    actions.className = "launcher-settings-actions";

    const reset = document.createElement("button");
    reset.type = "button";
    reset.className = "secondary";
    reset.textContent = "Reset defaults";

    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "secondary";
    cancel.textContent = "Cancel";

    const save = document.createElement("button");
    save.type = "button";
    save.textContent = "Save settings";

    actions.appendChild(reset);
    actions.appendChild(cancel);
    actions.appendChild(save);

    modal.appendChild(title);
    modal.appendChild(intro);
    modal.appendChild(grid);
    modal.appendChild(actions);
    backdrop.appendChild(modal);

    document.body.appendChild(button);
    document.body.appendChild(backdrop);

    function openModal() {
      document.querySelectorAll("[data-launcher-default-key]").forEach((input) => {
        const key = input.dataset.launcherDefaultKey;
        input.value = getDefault(key);
      });
      backdrop.classList.add("open");
    }

    function closeModal() {
      backdrop.classList.remove("open");
    }

    button.addEventListener("click", openModal);
    cancel.addEventListener("click", closeModal);

    backdrop.addEventListener("click", function (event) {
      if (event.target === backdrop) closeModal();
    });

    reset.addEventListener("click", async function () {
      await resetDefaults();
      document.querySelectorAll("[data-launcher-default-key]").forEach((input) => {
        const key = input.dataset.launcherDefaultKey;
        input.value = getDefault(key);
      });
      window.dispatchEvent(new CustomEvent("launcher-defaults-changed", {
        detail: getAllDefaults()
      }));
    });
    
    save.addEventListener("click", async function () {
      const values = {};
      document.querySelectorAll("[data-launcher-default-key]").forEach((input) => {
        values[input.dataset.launcherDefaultKey] = input.value;
      });

      const saved = await saveDefaults(values);

      window.dispatchEvent(new CustomEvent("launcher-defaults-changed", {
        detail: saved
      }));

      closeModal();
    });
  }

  window.LauncherDefaults = {
    get: getDefault,
    getAll: getAllDefaults,
    save: saveDefaults,
    reset: resetDefaults,
    loadServer: loadServerDefaults,
    storageKey: STORAGE_KEY,
    serverUrl: SERVER_DEFAULTS_URL
  };

  function refreshSettingsInputsFromDefaults() {
    document.querySelectorAll("[data-launcher-default-key]").forEach((input) => {
      const key = input.dataset.launcherDefaultKey;
      input.value = getDefault(key);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Build the UI immediately so the gear button always appears.
    // Server/project-level defaults load afterward and then refresh the modal fields.
    buildSettingsUi();

    loadServerDefaults()
      .then(function () {
        refreshSettingsInputsFromDefaults();
      })
      .catch(function (err) {
        console.warn("Launcher defaults load failed after UI build:", err);
      });
  });
})();