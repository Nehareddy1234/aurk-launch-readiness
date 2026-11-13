const sizeChart = document.getElementById('aurk-size-chart');
if (sizeChart) {
  let opener;
  document.querySelectorAll('[data-size-chart-open]').forEach((button) => {
    button.addEventListener('click', () => {
      opener = button;
      sizeChart.showModal();
      sizeChart.scrollTop = 0;
      document.documentElement.classList.add('size-chart-open');
    });
  });
  sizeChart.querySelector('[data-size-chart-close]').addEventListener('click', () => sizeChart.close());
  sizeChart.addEventListener('click', (event) => {
    const box = sizeChart.getBoundingClientRect();
    if (event.target === sizeChart && (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom)) sizeChart.close();
  });
  sizeChart.addEventListener('close', () => {
    document.documentElement.classList.remove('size-chart-open');
    if (opener && opener.isConnected) opener.focus();
  });
}
