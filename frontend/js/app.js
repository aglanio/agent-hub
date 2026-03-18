/**
 * Entry point — inicializacao e event listeners.
 */

// Auto-resize textarea
document.getElementById('chatInput').addEventListener('input', function () {
  this.style.height = '38px';
  this.style.height = Math.min(this.scrollHeight, 100) + 'px';
});

// Load flow on start
loadFlow();

// Auto-refresh every 30s
setInterval(loadFlow, 30000);
