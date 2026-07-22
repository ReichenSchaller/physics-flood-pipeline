

(function () {
  let modal = null;
  let currentTargetInput = null;
  let currentMode = 'directory';
  let currentPath = '';

  function ensureModal() {
    if (modal) return modal;

    const style = document.createElement('style');
    style.textContent = `
      .path-browser-backdrop {
        position: fixed;
        inset: 0;
        background: rgba(16, 24, 40, 0.45);
        z-index: 1000;
        display: none;
        align-items: center;
        justify-content: center;
        padding: 24px;
      }

      .path-browser-modal {
        width: min(920px, 96vw);
        max-height: 86vh;
        background: white;
        border-radius: 18px;
        border: 1px solid #d9dee8;
        box-shadow: 0 24px 60px rgba(16, 24, 40, 0.24);
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }

      .path-browser-header {
        padding: 16px 18px;
        border-bottom: 1px solid #d9dee8;
        background: #f6f7fb;
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: center;
      }

      .path-browser-title {
        font-weight: 900;
        color: #172033;
      }

      .path-browser-path {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
        font-size: 0.82rem;
        color: #667085;
        overflow-wrap: anywhere;
        padding: 12px 18px;
        border-bottom: 1px solid #d9dee8;
        background: #fbfcff;
      }

      .path-browser-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding: 12px 18px;
        border-bottom: 1px solid #d9dee8;
      }

      .path-browser-body {
        overflow: auto;
        padding: 8px;
      }

      .path-browser-row {
        display: grid;
        grid-template-columns: 34px minmax(0, 1fr) auto auto;
        gap: 8px;
        align-items: center;
        padding: 8px 10px;
        border-radius: 12px;
      }

      .path-browser-row:hover {
        background: #f0f3f8;
      }

      .path-browser-name {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
        overflow-wrap: anywhere;
        color: #172033;
      }

      .path-browser-muted {
        color: #667085;
        font-size: 0.82rem;
      }

      .path-browser-empty {
        padding: 28px;
        text-align: center;
        color: #667085;
      }

      .path-browser-error {
        padding: 14px 18px;
        background: #fff0ef;
        color: #b42318;
        border-bottom: 1px solid #ffbdb8;
        display: none;
      }
    `;
    document.head.appendChild(style);

    modal = document.createElement('div');
    modal.className = 'path-browser-backdrop';
    modal.innerHTML = `
      <div class="path-browser-modal" role="dialog" aria-modal="true" aria-label="Path browser">
        <div class="path-browser-header">
          <div>
            <div class="path-browser-title">Browse Longleaf paths</div>
            <div class="path-browser-muted">Choose a directory or file from allowed project roots.</div>
          </div>
          <button type="button" id="path-browser-close">Close</button>
        </div>

        <div id="path-browser-error" class="path-browser-error"></div>
        <div id="path-browser-path" class="path-browser-path"></div>

        <div class="path-browser-actions">
          <button type="button" id="path-browser-up">Up one folder</button>
          <button type="button" id="path-browser-use-current">Use current folder</button>
          <button type="button" id="path-browser-refresh">Refresh</button>
        </div>

        <div id="path-browser-body" class="path-browser-body"></div>
      </div>
    `;

    document.body.appendChild(modal);

    modal.querySelector('#path-browser-close').addEventListener('click', closeBrowser);
    modal.querySelector('#path-browser-refresh').addEventListener('click', () => loadPath(currentPath));
    modal.querySelector('#path-browser-up').addEventListener('click', () => {
      const parent = modal.dataset.parent || '';
      loadPath(parent);
    });
    modal.querySelector('#path-browser-use-current').addEventListener('click', () => {
      if (currentPath) choosePath(currentPath);
    });

    modal.addEventListener('click', event => {
      if (event.target === modal) closeBrowser();
    });

    return modal;
  }

  function showError(message) {
    const box = modal.querySelector('#path-browser-error');
    box.textContent = message;
    box.style.display = message ? 'block' : 'none';
  }

  function closeBrowser() {
    if (modal) modal.style.display = 'none';
  }

  function choosePath(path) {
    if (!currentTargetInput) return;

    currentTargetInput.value = path;
    currentTargetInput.dispatchEvent(new Event('input', { bubbles: true }));
    currentTargetInput.dispatchEvent(new Event('change', { bubbles: true }));

    closeBrowser();
  }

  async function listDirectory(path) {
    const response = await fetch('/api/list-directory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path })
    });

    const result = await response.json();

    if (!response.ok || !result.ok) {
      throw new Error(result.error || 'Directory listing failed.');
    }

    return result;
  }

  async function loadPath(path) {
    ensureModal();
    showError('');

    const body = modal.querySelector('#path-browser-body');
    const pathBox = modal.querySelector('#path-browser-path');
    const upButton = modal.querySelector('#path-browser-up');
    const useCurrentButton = modal.querySelector('#path-browser-use-current');

    body.innerHTML = '<div class="path-browser-empty">Loading...</div>';

    try {
      const result = await listDirectory(path || '');

      currentPath = result.path || '';
      modal.dataset.parent = result.parent || '';

      pathBox.textContent = currentPath || 'Allowed roots';
      upButton.disabled = !result.parent;
      useCurrentButton.disabled = !currentPath || currentMode !== 'directory';

      renderEntries(result.entries || []);

    } catch (err) {
      body.innerHTML = '';
      showError(err.message);
    }
  }

  function renderEntries(entries) {
    const body = modal.querySelector('#path-browser-body');
    body.innerHTML = '';

    if (!entries.length) {
      body.innerHTML = '<div class="path-browser-empty">No visible entries in this folder.</div>';
      return;
    }

    entries.forEach(entry => {
      const row = document.createElement('div');
      row.className = 'path-browser-row';

      const icon = document.createElement('div');
      icon.textContent = entry.is_dir ? '📁' : '📄';

      const name = document.createElement('div');
      name.className = 'path-browser-name';
      name.textContent = entry.name;

      const openButton = document.createElement('button');
      openButton.type = 'button';
      openButton.textContent = entry.is_dir ? 'Open' : 'View parent';
      openButton.addEventListener('click', () => {
        if (entry.is_dir) {
          loadPath(entry.path);
        } else {
          const parent = entry.path.split('/').slice(0, -1).join('/') || '/';
          loadPath(parent);
        }
      });

      const useButton = document.createElement('button');
      useButton.type = 'button';

      if (entry.is_dir && currentMode === 'directory') {
        useButton.textContent = 'Use folder';
        useButton.disabled = false;
      } else if (entry.is_file && currentMode === 'file') {
        useButton.textContent = 'Use file';
        useButton.disabled = false;
      } else {
        useButton.textContent = 'Use';
        useButton.disabled = true;
      }

      useButton.addEventListener('click', () => choosePath(entry.path));

      row.appendChild(icon);
      row.appendChild(name);
      row.appendChild(openButton);
      row.appendChild(useButton);

      body.appendChild(row);
    });
  }

  function extractUsableStartPath(rawValue) {
    const text = String(rawValue || '').trim();

    if (!text) {
      return '';
    }

    // List-like fields such as data_catalogs may store a JSON list.
    // Use the first absolute path inside the list instead of sending
    // the literal JSON string to /api/list-directory.
    if (text.startsWith('[')) {
      try {
        const parsed = JSON.parse(text);

        if (Array.isArray(parsed)) {
          const firstAbsolute = parsed
            .map(item => String(item || '').trim())
            .find(item => item.startsWith('/'));

          return firstAbsolute || '';
        }
      } catch (err) {
        return '';
      }
    }

    // Plain path fields should be absolute paths. If the value is a
    // catalog nickname, blank label, or malformed value, fall back to
    // the browse-start default instead of showing a scary error.
    if (text.startsWith('/')) {
      return text;
    }

    return '';
  }

  function getLauncherDefaultsApi() {
    return (
      window.LauncherDefaults ||
      window.SFINCS_LAUNCHER_DEFAULTS ||
      window.SfincsLauncherDefaults ||
      window.launcherDefaults ||
      null
    );
  }

  function getLauncherDefaultPath(key) {
    const cleanKey = String(key || '').trim();
    if (!cleanKey) return '';

    const api = getLauncherDefaultsApi();
    if (!api) return '';

    if (typeof api.get === 'function') {
      return extractUsableStartPath(api.get(cleanKey));
    }

    if (typeof api.getDefault === 'function') {
      return extractUsableStartPath(api.getDefault(cleanKey));
    }

    if (Object.prototype.hasOwnProperty.call(api, cleanKey)) {
      return extractUsableStartPath(api[cleanKey]);
    }

    return '';
  }

  function resolveButtonBrowseStart(button, inputStart) {
    const defaultKey = String(button.dataset.browseDefaultKey || '').trim();
    const settingsStart = getLauncherDefaultPath(defaultKey);
    const buttonStart = extractUsableStartPath(button.dataset.browseStart);
    const forceStart = button.dataset.browseForceStart === 'true';

    if (forceStart) {
      return settingsStart || buttonStart || inputStart || '';
    }

    return inputStart || settingsStart || buttonStart || '';
  }

  function getLauncherDefaultsApi() {
    return (
      window.LauncherDefaults ||
      window.SFINCS_LAUNCHER_DEFAULTS ||
      window.SfincsLauncherDefaults ||
      window.launcherDefaults ||
      null
    );
  }

  function getLauncherDefaultPath(key) {
    const cleanKey = String(key || '').trim();
    if (!cleanKey) return '';

    const api = getLauncherDefaultsApi();
    if (!api) return '';

    if (typeof api.get === 'function') {
      return extractUsableStartPath(api.get(cleanKey));
    }

    if (typeof api.getDefault === 'function') {
      return extractUsableStartPath(api.getDefault(cleanKey));
    }

    if (typeof api.getAll === 'function') {
      const all = api.getAll() || {};
      return extractUsableStartPath(all[cleanKey]);
    }

    if (Object.prototype.hasOwnProperty.call(api, cleanKey)) {
      return extractUsableStartPath(api[cleanKey]);
    }

    return '';
  }

  function resolveButtonBrowseStart(button, inputStart) {
    const defaultKey = String(button.dataset.browseDefaultKey || '').trim();
    const settingsStart = getLauncherDefaultPath(defaultKey);
    const buttonStart = extractUsableStartPath(button.dataset.browseStart);
    const forceStart = button.dataset.browseForceStart === 'true';

    if (forceStart) {
      return settingsStart || buttonStart || inputStart || '';
    }

    return inputStart || settingsStart || buttonStart || '';
  }

  function openBrowserForButton(button) {
    ensureModal();

    const targetId = button.dataset.browseTarget;
    currentMode = button.dataset.browseMode || 'directory';

    currentTargetInput = document.getElementById(targetId);

    if (!currentTargetInput) {
      alert(`Browse target not found: ${targetId}`);
      return;
    }

    const inputStart = extractUsableStartPath(currentTargetInput.value);
    const startPath = resolveButtonBrowseStart(button, inputStart);

    modal.style.display = 'flex';
    loadPath(startPath);
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-browse-target]');
    if (!button) return;

    event.preventDefault();
    openBrowserForButton(button);
  });
})();