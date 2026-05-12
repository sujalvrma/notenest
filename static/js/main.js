// Auto-dismiss flash messages after 4 seconds
document.addEventListener('DOMContentLoaded', function () {
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(function (f) {
    setTimeout(function () {
      f.style.transition = 'opacity 0.4s';
      f.style.opacity = '0';
      setTimeout(function () { f.remove(); }, 400);
    }, 4000);
  });

  // Animate progress bar on result page
  const fill = document.querySelector('.progress-fill');
  if (fill) {
    const target = fill.style.width;
    fill.style.width = '0%';
    setTimeout(function () { fill.style.width = target; }, 200);
  }
});
