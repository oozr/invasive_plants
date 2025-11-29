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
        const latestCountryLink = document.getElementById('highlight-latest-country-link');
        const topSpeciesLink = document.getElementById('highlight-top-species-link');
        const topSpeciesNameEl = document.getElementById('highlight-top-species-name');
        const topSpeciesCommonEl = document.getElementById('highlight-top-species-common');
        const topSpeciesCountEl = document.getElementById('highlight-top-species-count');
        const topJurisdictionNameEl = document.getElementById('highlight-top-jurisdiction-name');
        const topJurisdictionCountEl = document.getElementById('highlight-top-jurisdiction-count');
        const topJurisdictionLink = document.getElementById('highlight-top-jurisdiction-link');

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
        if (latestCountryLink) {
            const targetState = latestCountry.stateName || latestCountry.name;
            if (targetState) {
                latestCountryLink.dataset.state = targetState;
                latestCountryLink.classList.remove('disabled');
            } else {
                latestCountryLink.dataset.state = '';
                latestCountryLink.classList.add('disabled');
            }
        }
        if (topSpeciesLink && topSpeciesNameEl && topSpeciesCountEl && topSpeciesCommonEl) {
            const topSpecies = data.topSpecies;
            if (topSpecies && topSpecies.name) {
                topSpeciesNameEl.textContent = topSpecies.name;
                topSpeciesCommonEl.textContent = topSpecies.common_name || '';
                topSpeciesLink.href = `/species?name=${encodeURIComponent(topSpecies.name)}`;
                topSpeciesLink.classList.remove('disabled');
                if (topSpecies.jurisdiction_count) {
                    animateCount(topSpeciesCountEl, topSpecies.jurisdiction_count);
                } else {
                    topSpeciesCountEl.textContent = '--';
                }
            } else {
                topSpeciesNameEl.textContent = 'Data pending';
                topSpeciesCommonEl.textContent = '';
                topSpeciesLink.href = '#';
                topSpeciesLink.classList.add('disabled');
                topSpeciesCountEl.textContent = '--';
            }
        }
        if (topJurisdictionNameEl && topJurisdictionLink) {
            if (data.topJurisdiction && data.topJurisdiction.name) {
                const country = data.topJurisdiction.country
                    ? `, ${data.topJurisdiction.country}`
                    : '';
                topJurisdictionNameEl.textContent = `${data.topJurisdiction.name}${country}`;
                topJurisdictionLink.dataset.state = data.topJurisdiction.name;
                topJurisdictionLink.classList.remove('disabled');
            } else {
                topJurisdictionNameEl.textContent = 'Data pending';
                topJurisdictionLink.dataset.state = '';
                topJurisdictionLink.classList.add('disabled');
            }
        }
        if (topJurisdictionCountEl) {
            const topJurisdictionCount =
                data.topJurisdiction && data.topJurisdiction.species_count
                    ? data.topJurisdiction.species_count
                    : 0;
            if (topJurisdictionCount) {
                animateCount(topJurisdictionCountEl, topJurisdictionCount);
            } else {
                topJurisdictionCountEl.textContent = '--';
            }
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

    function handleTopJurisdictionClick(event) {
        const stateName = event.currentTarget.dataset.state;
        if (!stateName) {
            return;
        }
        event.preventDefault();
        window.dispatchEvent(
            new CustomEvent('highlight:showState', {
                detail: { state: stateName, scroll: true }
            })
        );
    }

    document.addEventListener('DOMContentLoaded', function () {
        const topJurisdictionLink = document.getElementById('highlight-top-jurisdiction-link');
        const latestCountryLink = document.getElementById('highlight-latest-country-link');
        if (topJurisdictionLink) {
            topJurisdictionLink.addEventListener('click', handleTopJurisdictionClick);
        }
        if (latestCountryLink) {
            latestCountryLink.addEventListener('click', handleTopJurisdictionClick);
        }
        initHighlights();
    });
})();
