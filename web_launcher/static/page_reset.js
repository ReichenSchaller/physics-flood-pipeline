(function () {
  function startNewRun() {
    const ok = confirm(
      'Start a new run and wipe the current page state?\n\n' +
      'This only resets the browser page. It does not delete saved JSON files or run folders.'
    );

    if (!ok) return;

    const url = new URL(window.location.href);
    url.searchParams.set('new_run', Date.now().toString());

    window.location.href = url.toString();
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-new-run-button]');
    if (!button) return;

    event.preventDefault();
    startNewRun();
  });
})();