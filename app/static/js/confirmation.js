/* Shared in-page confirmation; the original form and submitter are preserved. */
(() => {
  const dialog = document.createElement('dialog');
  dialog.className = 'aurk-confirm-dialog';
  dialog.setAttribute('aria-labelledby', 'aurk-confirm-title');
  dialog.setAttribute('aria-describedby', 'aurk-confirm-message');
  dialog.innerHTML = '<h2 id="aurk-confirm-title">Confirm action</h2><p id="aurk-confirm-message"></p><div class="aurk-confirm-actions"><button type="button" data-cancel>Cancel</button><button type="button" data-accept>Continue</button></div>';
  document.body.append(dialog);
  const cancel = dialog.querySelector('[data-cancel]');
  const accept = dialog.querySelector('[data-accept]');
  const approved = new WeakSet();
  let pending = null;
  document.addEventListener('submit', event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.dataset.confirm) return;
    if (approved.has(form)) { approved.delete(form); return; }
    event.preventDefault();
    event.stopImmediatePropagation();
    if (pending) return;
    pending = { form, submitter: event.submitter, focus: document.activeElement };
    const destructive = /delete|remove|cancel|revoke/i.test(form.dataset.confirm);
    dialog.querySelector('h2').textContent = destructive ? 'Confirm removal or cancellation' : 'Confirm action';
    dialog.querySelector('p').textContent = form.dataset.confirm;
    accept.textContent = event.submitter?.textContent.trim() || 'Confirm';
    accept.classList.toggle('is-destructive', destructive);
    dialog.showModal();
    cancel.focus();
  }, true);
  cancel.addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    const previous = pending;
    pending = null;
    previous?.focus?.focus();
  });
  accept.addEventListener('click', () => {
    if (!pending) return;
    const { form, submitter } = pending;
    pending = null;
    dialog.close();
    approved.add(form);
    try { form.requestSubmit(submitter || undefined); }
    finally { approved.delete(form); }
  });
})();
