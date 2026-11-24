document.addEventListener('DOMContentLoaded', () => {
  console.log('NOVA Generated Website Loaded Successfully!');
  let count = 0;
  const counterVal = document.getElementById('counterVal');
  const incBtn = document.getElementById('incBtn');
  const decBtn = document.getElementById('decBtn');
  const resetBtn = document.getElementById('resetBtn');
  const themeToggle = document.getElementById('themeToggle');
  const exploreBtn = document.getElementById('exploreBtn');

  incBtn?.addEventListener('click', () => { count++; counterVal.textContent = count; });
  decBtn?.addEventListener('click', () => { count--; counterVal.textContent = count; });
  resetBtn?.addEventListener('click', () => { count = 0; counterVal.textContent = count; });

  themeToggle?.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    document.documentElement.setAttribute('data-theme', current === 'light' ? 'dark' : 'light');
  });

  exploreBtn?.addEventListener('click', () => {
    document.querySelector('.cards-grid')?.scrollIntoView({ behavior: 'smooth' });
  });
});
