document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const filter = btn.dataset.filter;
    document.querySelectorAll('#cards-grid .card').forEach(card => {
      card.style.display = (filter === 'all' || card.dataset.competition === filter) ? '' : 'none';
    });
  });
});
