document.addEventListener('DOMContentLoaded', function() {
    const toggle = document.getElementById('sourcesToggle');
    const content = document.getElementById('sourcesContent');

    toggle.addEventListener('click', function() {
        const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
        
        toggle.setAttribute('aria-expanded', !isExpanded);
        content.classList.toggle('open');
    });
});