// static/js/species_search.js
document.addEventListener('DOMContentLoaded', function () {
    /******************************
     * URL PARAMS
     ******************************/
    function getUrlParameter(name) {
        name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
        const regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
        const results = regex.exec(location.search);
        return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
    }

    /******************************
     * SELECT2 SEARCH
     ******************************/
    $('#weedSearch').select2({
        placeholder: 'Start typing a common or scientific name...',
        minimumInputLength: 2,
        ajax: {
            url: '/species/api/search',
            dataType: 'json',
            delay: 250,
            data: function (params) {
                return { q: params.term };
            },
            processResults: function (data) {
                return {
                    results: data.map(weed => {
                        let displayCommonName = weed.common_name;
                        if (!displayCommonName || displayCommonName.includes('No English common names available')) {
                            displayCommonName = null;
                        }

                        return {
                            id: weed.usage_key,
                            text: displayCommonName
                                ? `${displayCommonName} (${weed.canonical_name})`
                                : `(${weed.canonical_name})`,
                            common_name: displayCommonName || weed.canonical_name,
                            canonical_name: weed.canonical_name,
                            family_name: weed.family_name,
                            synonyms: weed.synonyms,
                            usage_key: weed.usage_key
                        };
                    })
                };
            },
            cache: true
        },
        templateResult: function (weed) {
            if (!weed.id) return weed.text;

            let commonName = weed.common_name || '';
            if (commonName.includes('No English common names available')) commonName = '';

            const canonicalName = weed.canonical_name || '';
            const container = $('<div>');

            if (commonName) {
                $('<div>')
                    .addClass('common-name')
                    .text(commonName)
                    .appendTo(container);
            }

            $('<div>')
                .addClass(`canonical-name ${commonName ? 'text-muted small' : ''}`.trim())
                .text(commonName ? canonicalName : `(${canonicalName})`)
                .appendTo(container);

            return container;
        }
    });

    $('#weedSearch').on('select2:select', function (e) {
        const selectedWeed = e.params.data;
        displayWeedDetails(selectedWeed);
    });

    $('#weedSearch').on('select2:clear', function () {
        document.getElementById('results').classList.add('d-none');
    });

    /******************************
     * DETAILS RENDER
     ******************************/
    function displayCountryName(country) {
        if (!country) return country;
        const normalized = String(country).trim();
        if (normalized.toUpperCase() === 'EU') return 'European Union';
        return normalized;
    }

    function displayWeedDetails(selectedWeed) {
        // Common name display (truncate)
        const commonName = selectedWeed.common_name || '';
        const commonNameParts = commonName.split(',');
        const truncatedCommonName = commonNameParts.length > 3
            ? commonNameParts.slice(0, 3).join(', ')
            : commonName;

        let displayName = truncatedCommonName;
        if (!displayName || displayName.includes('No English common names available')) {
            displayName = `(${selectedWeed.canonical_name || 'Unknown'})`;
        }

        document.getElementById('weedTitle').textContent = displayName;
        document.getElementById('weedCanonicalName').textContent = selectedWeed.canonical_name;
        document.getElementById('weedFamily').textContent = selectedWeed.family_name || 'Not available';

        // Synonyms (first 3)
        const synonymsSection = document.getElementById('synonymsSection');
        const weedSynonyms = document.getElementById('weedSynonyms');

        if (selectedWeed.synonyms && selectedWeed.synonyms.trim() !== '') {
            const allSynonyms = selectedWeed.synonyms.split(',');
            const truncatedSynonyms = allSynonyms.length > 3
                ? allSynonyms.slice(0, 3).join(', ')
                : selectedWeed.synonyms;

            weedSynonyms.textContent = truncatedSynonyms;
            synonymsSection.classList.remove('d-none');
        } else {
            synonymsSection.classList.add('d-none');
        }

        // GBIF link
        const gbifLink = document.getElementById('gbifLink');
        gbifLink.href = `https://www.gbif.org/species/${selectedWeed.usage_key}`;

        // Fetch regulation jurisdictions by usage_key
        fetch(`/species/api/weed-states/by-key/${selectedWeed.usage_key}`)
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(regulationsByCountry => {
                const statesList = document.getElementById('statesList');
                statesList.innerHTML = '';

                if (!regulationsByCountry || Object.keys(regulationsByCountry).length === 0) {
                    statesList.innerHTML = `
                        <div class="list-group-item">
                            <p class="mb-1">No regulations found for this species.</p>
                        </div>
                    `;
                    document.getElementById('results').classList.remove('d-none');
                    return;
                }

                // Expected shape:
                // { "United States": ["National Level", "California", ...],
                //   "European Union": ["International Level", ...],
                //   "New Zealand": ["National Level"] }
                for (const [countryKey, jurisdictions] of Object.entries(regulationsByCountry)) {
                    const country = displayCountryName(countryKey);
                    const list = Array.isArray(jurisdictions) ? jurisdictions : [];

                    const hasNational = list.includes('National Level');
                    const hasInternational = list.includes('International Level');

                    // Everything else is treated as a regional jurisdiction name
                    const regional = list.filter(x =>
                        x !== 'National Level' &&
                        x !== 'International Level'
                    );

                    const countryElement = document.createElement('div');
                    countryElement.className = 'list-group-item';

                    const countryHeader = document.createElement('h5');
                    countryHeader.className = 'mb-2';
                    countryHeader.textContent = country;
                    countryElement.appendChild(countryHeader);

                    if (hasInternational) {
                        const intlInfo = document.createElement('p');
                        intlInfo.className = 'mb-1';
                        intlInfo.innerHTML = '<strong>International Level:</strong> Regulated at international level';
                        countryElement.appendChild(intlInfo);
                    }

                    if (hasNational) {
                        const nationalInfo = document.createElement('p');
                        nationalInfo.className = 'mb-1';
                        nationalInfo.innerHTML = '<strong>National Level:</strong> Regulated nationwide';
                        countryElement.appendChild(nationalInfo);
                    }

                    if (regional.length > 0) {
                        const regionsRow = document.createElement('p');
                        regionsRow.className = 'mb-0';

                        const label = regional.length === 1 ? 'Region' : 'Regions';
                        const labelElement = document.createElement('strong');
                        labelElement.textContent = `${label}:`;
                        regionsRow.appendChild(labelElement);
                        regionsRow.appendChild(document.createTextNode(` ${regional.join(', ')}`));

                        countryElement.appendChild(regionsRow);
                    }

                    // If it’s only international/national and no region list, keep it clean (no extra line)
                    statesList.appendChild(countryElement);
                }

                document.getElementById('results').classList.remove('d-none');
            })
            .catch(error => {
                console.error('Error fetching weed jurisdictions:', error);
                const statesList = document.getElementById('statesList');
                statesList.innerHTML = `
                    <div class="list-group-item text-danger">
                        <p class="mb-1">Error loading data. Please try again.</p>
                    </div>
                `;
                document.getElementById('results').classList.remove('d-none');
            });
    }

    /******************************
     * AUTOLOAD BY URL ?name=
     ******************************/
    const plantName = getUrlParameter('name');
    if (plantName) {
        fetch(`/species/api/search?q=${encodeURIComponent(plantName)}`)
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(results => {
                const exactMatch = results.find(weed =>
                    weed.canonical_name.toLowerCase() === plantName.toLowerCase()
                );

                const weedData = exactMatch || results[0];
                if (!weedData) return;

                let displayCommonName = weedData.common_name;
                if (!displayCommonName || displayCommonName.includes('No English common names available')) {
                    displayCommonName = null;
                }

                const formattedData = {
                    id: weedData.usage_key,
                    text: displayCommonName
                        ? `${displayCommonName} (${weedData.canonical_name})`
                        : `(${weedData.canonical_name})`,
                    common_name: displayCommonName || weedData.canonical_name,
                    canonical_name: weedData.canonical_name,
                    family_name: weedData.family_name,
                    synonyms: weedData.synonyms,
                    usage_key: weedData.usage_key
                };

                const newOption = new Option(formattedData.text, formattedData.id, true, true);
                $('#weedSearch').append(newOption).trigger('change');

                displayWeedDetails(formattedData);
            })
            .catch(error => {
                console.error('Error fetching plant data:', error);
            });
    }
});
