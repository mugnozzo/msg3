function setupMainMenu() {
  const menuToggle = document.getElementById('menu-toggle');
  const mainNav = document.getElementById('main-nav');

  if (!menuToggle || !mainNav) return;

  mainNav.hidden = true;
  menuToggle.setAttribute('aria-expanded', 'false');

  menuToggle.addEventListener('click', () => {
    const isOpen = !mainNav.hidden;
    mainNav.hidden = isOpen;
    menuToggle.setAttribute('aria-expanded', String(!isOpen));
  });
}

function setupFullscreenButton() {
  const fullscreenToggle = document.getElementById('fullscreen-toggle');
  if (!fullscreenToggle) return;

  const label = fullscreenToggle.querySelector('span:last-child');

  fullscreenToggle.addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else {
        await document.documentElement.requestFullscreen();
      }
    } catch (error) {
      console.error('Fullscreen non disponibile:', error);
    } finally {
      updateLabel();
    }
  });

  document.addEventListener('fullscreenchange', updateLabel);
  updateLabel();
}

document.addEventListener('DOMContentLoaded', () => {
  setupMainMenu();
  setupFullscreenButton();
});
