(function () {
  let preflightPassed = false;

  function getConfigFromPage() {
    if (typeof window.getConfig === 'function') {
      return window.getConfig();
    }

    if (typeof getConfig === 'function') {
      return getConfig();
    }

    throw new Error('This page does not expose a getConfig() function.');
  }

  function setOutput(targetId, text) {
    const output = document.getElementById(targetId);
    if (!output) return;
    output.textContent = text;
    output.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function appendOutput(targetId, text) {
    const output = document.getElementById(targetId);
    if (!output) return;
    output.textContent += text;
  }

  function setRunnerBusy(isBusy) {
    document.querySelectorAll('[data-pipeline-action]').forEach(button => {
      button.disabled = isBusy || (
        button.dataset.requiresPreflight === 'true' && !preflightPassed
      );
    });
  }

  function refreshPreflightButtons() {
    document.querySelectorAll('[data-pipeline-action]').forEach(button => {
      if (button.dataset.requiresPreflight === 'true') {
        button.disabled = !preflightPassed;
      }
    });
  }

  function commandText(command) {
    if (!Array.isArray(command)) return '';
    return command.join(' ');
  }

  function modeSuccessMessage(mode) {
    if (mode === 'preflight') {
      return '✅ PREFLIGHT PASSED — Build Scripts and Submit are now enabled.';
    }

    if (mode === 'build_scripts') {
      return '✅ SLURM SCRIPTS BUILT SUCCESSFULLY.';
    }

    if (mode === 'submit') {
      return '✅ SLURM CHAIN SUBMITTED SUCCESSFULLY.';
    }

    return '✅ ACTION COMPLETED SUCCESSFULLY.';
  }

  function modeFailureMessage(mode) {
    if (mode === 'preflight') {
      return '❌ PREFLIGHT FAILED.';
    }

    if (mode === 'build_scripts') {
      return '❌ SLURM SCRIPT BUILD FAILED.';
    }

    if (mode === 'submit') {
      return '❌ SLURM SUBMIT FAILED.';
    }

    return '❌ ACTION FAILED.';
  }

  function formatResult(result) {
    const parts = [];
    const ok = Boolean(result.ok);

    parts.push(ok ? modeSuccessMessage(result.mode) : modeFailureMessage(result.mode));
    parts.push('='.repeat(80));
    parts.push('');

    if (!ok) {
      parts.push('Runner finished with a nonzero return code. Read stdout/stderr below.');
      parts.push('');
    }

    parts.push(`Mode: ${result.mode}`);
    parts.push(`Return code: ${result.returncode}`);
    parts.push(`Run root: ${result.run_root || ''}`);
    parts.push(`Config path: ${result.config_path || ''}`);
    parts.push(`Command: ${commandText(result.command)}`);
    parts.push('');
    parts.push(`stdout log: ${result.stdout_log || ''}`);
    parts.push(`stderr log: ${result.stderr_log || ''}`);
    parts.push('');
    parts.push('----- STDOUT -----');
    parts.push(result.stdout || '');
    parts.push('');
    parts.push('----- STDERR -----');
    parts.push(result.stderr || '');

    return parts.join('\n');
  }

  async function runPipelineAction(button) {
    const mode = button.dataset.pipelineAction;
    const outputTarget = button.dataset.outputTarget || 'runner-output';

    if (mode === 'submit') {
      const ok = confirm(
        'Submit this run to Slurm?\n\n' +
        'This will call pipeline_runner.py --mode submit.\n' +
        'Make sure preflight passed and the run_name/output_root are correct.'
      );
      if (!ok) return;
    }

    let cfg;
    try {
      cfg = getConfigFromPage();
    } catch (err) {
      alert(err.message);
      return;
    }

    setRunnerBusy(true);
    setOutput(outputTarget, `Running ${mode}...\n\n`);

    try {
      const response = await fetch('/api/run-pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, config: cfg })
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || 'Runner request failed.');
      }

      setOutput(outputTarget, formatResult(result));
    
      if (mode === 'preflight' && result.ok) {
        preflightPassed = true;
      }

    } catch (err) {
      setOutput(outputTarget, `Runner request failed:\n\n${err.message}`);
    } finally {
      setRunnerBusy(false);
      refreshPreflightButtons();
    }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-pipeline-action]');
    if (!button) return;

    event.preventDefault();
    runPipelineAction(button);
  });

  document.addEventListener('DOMContentLoaded', refreshPreflightButtons);
})();