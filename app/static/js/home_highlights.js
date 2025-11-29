// static/js/home_highlights.js
(function () {
    function formatNumber(value) {
        if (typeof value !== 'number') return '--';
        return new Intl.NumberFormat().format(value);
    }

    function formatDate(isoString) {
        if (!isoString) return '--';
        const date = new Date(isoString);
        if (Number.isNaN(date.getTime())) {
            return '--';
        }
        return date.toLocaleDateString(undefined, {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }

    function animateCount(element, value) {
        if (!element || typeof value !== 'number') return;

        const startValue = 0;
        const startTime = performance.now();
        const duration = 1200;

        function step(currentTime) {
            const progress = Math.min((currentTime - startTime) / duration, 1);
            const currentValue = Math.floor(
                startValue + (value - startValue) * progress
            );
            element.textContent = new Intl.NumberFormat().format(currentValue);

            if (progress < 1) {
                requestAnimationFrame(step);
            }
        }

        requestAnimationFrame(step);
    }

    function updateHighlights(data) {
        const jurisdictionsEl = document.getElementById('highlight-jurisdictions');
        const speciesEl = document.getElementById('highlight-species');
        const lastUpdatedEl = document.getElementById('highlight-last-updated');
        const lastUpdatedBadge = document.getElementById('highlight-last-updated-badge');
        const latestCountryEl = document.getElementById('highlight-latest-country');
        const countryJurisdictionsEl = document.getElementById('highlight-country-jurisdictions');
        const blogLink = document.getElementById('highlight-blog-link');
        const blogDate = document.getElementById('highlight-blog-date');
        const pressLink = document.getElementById('highlight-press-link');

        if (jurisdictionsEl && data.stats) {
            animateCount(jurisdictionsEl, data.stats.jurisdictions);
        }

        if (speciesEl && data.stats) {
            animateCount(speciesEl, data.stats.species);
        }

        const formattedDate = formatDate(data.lastUpdated);
        if (lastUpdatedEl) {
            lastUpdatedEl.textContent = formattedDate;
        }
        if (lastUpdatedBadge) {
            lastUpdatedBadge.textContent = formattedDate === '--' ? 'Awaiting sync' : `Updated ${formattedDate}`;
        }

        const latestCountry = data.latestCountry || {};
        if (latestCountryEl) {
            latestCountryEl.textContent = latestCountry.name || 'New regions on the way';
        }
        if (countryJurisdictionsEl) {
            const count = latestCountry.jurisdictions || 0;
            if (count) {
                animateCount(countryJurisdictionsEl, count);
            } else {
                countryJurisdictionsEl.textContent = '--';
            }
        }

        if (blogLink && data.latestBlog) {
            blogLink.textContent = data.latestBlog.title;
            blogLink.href = data.latestBlog.url;
            if (blogDate) {
                blogDate.textContent = `Published ${formatDate(data.latestBlog.date)}`;
            }
        }

        if (pressLink && data.pressRelease) {
            pressLink.textContent = data.pressRelease.title;
            pressLink.href = data.pressRelease.url;
        }
    }

    function initHighlights() {
        const section = document.getElementById('home-highlights');
        if (!section) {
            return;
        }

        fetch('/api/home-highlights')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to load highlights');
                }
                return response.json();
            })
            .then(updateHighlights)
            .catch(error => {
                console.error(error);
                const badge = document.getElementById('highlight-last-updated-badge');
                if (badge) {
                    badge.textContent = 'Highlights unavailable';
                }
            });
    }

    document.addEventListener('DOMContentLoaded', initHighlights);
})();
