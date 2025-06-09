document.addEventListener('DOMContentLoaded', () => {
  const moduleName = document.body.dataset.module;
  if (!moduleName) return;
  fetch(`/modules/${moduleName}`).then(r => r.text()).then(t => {
    document.getElementById('code').textContent = t;
  }).catch(err => {
    document.getElementById('code').textContent = 'Failed to load module';
  });
});
