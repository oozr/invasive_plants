// static/js/map.js
document.addEventListener('DOMContentLoaded', function () {
    /******************************
     * BASIC CONFIG
     ******************************/
    const GEOJSON_PATH = '/static/data/geographic/';
    const MAP_CONFIG = window.MAP_CONFIG || {};
    const EU_MEMBERS = new Set([
        "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia",
        "Denmark", "Estonia", "Finland", "France", "Germany", "Greece",
        "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg",
        "Malta", "Netherlands", "Poland", "Portugal", "Romania", "Slovakia",
        "Slovenia", "Spain", "Sweden"
    ]);
    const EU_LABEL = "European Union";

    // Region counts lookup:
    // key = `${country}::${region}` -> { country, region, count }
    let regionWeedData = {};
    let geojsonLayer = null;

    // Current selection
    let currentSelected = null; // { country, region }
    let pendingScrollToTable = false;

    // Toggle state management (new model)
    // Default ON for all three (as you want: "show all regulations that exist")
    const toggleState = {
        region: true,
        national: true,
        international: true
    };
    const SAMPLE_PLANT_LIMIT = 10;
    const ANONYMOUS_USER_COOKIE = 'anonymous_user_id';
    const AHA_ACTIVATED_COOKIE = 'aha_activated';
    const COOKIE_MAX_AGE_DAYS = 730;
    let activationInFlight = false;

    /******************************
     * UTILITY FUNCTIONS
     ******************************/

    // Simple hash so we can pick a colour ramp based on country name
    function hashString(str) {
        let hash = 0;
        if (!str) return 0;
        for (let i = 0; i < str.length; i++) {
            hash = (hash << 5) - hash + str.charCodeAt(i);
            hash |= 0; // convert to 32-bit int
        }
        return Math.abs(hash);
    }

    // Get a colour config (thresholds + scheme) for a given country name
    function getCountryConfig(countryName) {
        const isEU = EU_MEMBERS.has(countryName);
        const cacheKey = isEU ? 'EU' : (countryName || 'default');

        MAP_CONFIG._countryCache = MAP_CONFIG._countryCache || {};
        if (MAP_CONFIG._countryCache[cacheKey]) return MAP_CONFIG._countryCache[cacheKey];

        if (isEU) {
            const thresholds = MAP_CONFIG.euThresholds || MAP_CONFIG.defaultThresholds || [0, 1, 2, 3, 4, 5];
            const scheme = MAP_CONFIG.euColorRamp || ["#e9f2ff", "#d3e5ff", "#b7d4ff", "#97c1ff", "#74a9ff", "#4f90f0", "#2c74d4"];
            const config = { thresholds, scheme };
            MAP_CONFIG._countryCache[cacheKey] = config;
            return config;
        }

        const ramps = MAP_CONFIG.defaultColorRamps || [];
        const thresholds = MAP_CONFIG.defaultThresholds || [0, 1, 2, 3, 4, 5];

        let scheme;
        if (!ramps.length) {
            scheme = ['#f0f0f0', '#f0f0f0', '#f0f0f0', '#f0f0f0', '#f0f0f0', '#f0f0f0', '#f0f0f0'];
        } else {
            const idx = hashString(cacheKey) % ramps.length;
            scheme = ramps[idx];
        }

        const config = { thresholds, scheme };
        MAP_CONFIG._countryCache[cacheKey] = config;
        return config;
    }

    function getColor(value, countryName) {
        const countryConfig = getCountryConfig(countryName);
        const thresholds = countryConfig.thresholds;
        const scheme = countryConfig.scheme;

        if (value > thresholds[5]) return scheme[6];
        if (value > thresholds[4]) return scheme[5];
        if (value > thresholds[3]) return scheme[4];
        if (value > thresholds[2]) return scheme[3];
        if (value > thresholds[1]) return scheme[2];
        if (value > thresholds[0]) return scheme[1];
        return scheme[0];
    }

    function inferCountryFromFilename(filename) {
        // e.g. "united_states.geojson" -> "United States"
        const base = filename.replace(/\.geojson$/i, '');
        return base
            .replace(/[_-]+/g, ' ')
            .replace(/\b\w/g, c => c.toUpperCase())
            .trim();
    }

    function extractRegionName(feature) {
        const props = feature && feature.properties ? feature.properties : {};
        const country = extractCountryName(feature);
        // Prefer canonical `region`; fall back to source-specific names.
        const possibleNameProps = ['region', 'REGION', 'shapeName', 'STATE_NAME', 'state', 'STATE', 'name', 'NAME'];
        for (const prop of possibleNameProps) {
            if (props[prop]) {
                const v = String(props[prop]).trim();
                if (!v) continue;
                if ((prop === 'name' || prop === 'NAME') && country && v.toLowerCase() === country.toLowerCase()) {
                    // `name` can be country-level on ADM1 files; skip it.
                    continue;
                }
                return v;
            }
        }
        return null;
    }

    function extractCountryName(feature) {
        const props = feature && feature.properties ? feature.properties : {};
        if (props.country) {
            const v = String(props.country).trim();
            if (v) return v;
        }
        return '';
    }

    function regionKey(country, region) {
        return `${country}::${region}`;
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function primaryCommonName(value) {
        const raw = String(value || '').trim();
        if (!raw) return '';
        return raw.split(',').map(part => part.trim()).find(Boolean) || raw;
    }

    function getCookie(name) {
        const encodedName = encodeURIComponent(name);
        const cookieParts = document.cookie ? document.cookie.split('; ') : [];
        for (const part of cookieParts) {
            const [rawKey, rawValue = ''] = part.split('=');
            if (rawKey === encodedName) {
                return decodeURIComponent(rawValue);
            }
        }
        return null;
    }

    function setCookie(name, value, maxAgeDays) {
        const expires = new Date(Date.now() + maxAgeDays * 24 * 60 * 60 * 1000).toUTCString();
        const secure = window.location.protocol === 'https:' ? '; Secure' : '';
        document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)}; Expires=${expires}; Path=/; SameSite=Lax${secure}`;
    }

    function generateAnonymousId() {
        if (window.crypto && typeof window.crypto.randomUUID === 'function') {
            return window.crypto.randomUUID();
        }
        return `anon-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    function ensureAnonymousId() {
        let anonymousId = getCookie(ANONYMOUS_USER_COOKIE);
        if (!anonymousId) {
            anonymousId = generateAnonymousId();
            setCookie(ANONYMOUS_USER_COOKIE, anonymousId, COOKIE_MAX_AGE_DAYS);
        }
        return anonymousId;
    }

    function metricsEnabled() {
        return MAP_CONFIG.oozrMetricsEnabled === true;
    }

    function oozrBaseUrl() {
        return String(MAP_CONFIG.oozrBaseUrl || '').trim().replace(/\/$/, '');
    }

    function oozrProjectSlug() {
        const configured = String(MAP_CONFIG.oozrProjectSlug || '').trim();
        return configured || 'regulatedplants';
    }

    async function sendAhaActivationIfNeeded(weedsCount) {
        if (!metricsEnabled()) return;
        if (!Number.isFinite(weedsCount) || weedsCount <= 0) return;
        if (getCookie(AHA_ACTIVATED_COOKIE) === '1') return;
        if (activationInFlight) return;

        const baseUrl = oozrBaseUrl();
        if (!baseUrl) return;

        activationInFlight = true;
        try {
            const response = await fetch(`${baseUrl}/api/activate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project: oozrProjectSlug(),
                    anonymous_id: ensureAnonymousId(),
                    timestamp: new Date().toISOString()
                })
            });

            if (response.ok) {
                setCookie(AHA_ACTIVATED_COOKIE, '1', COOKIE_MAX_AGE_DAYS);
            }
        } catch (error) {
            console.error('Error sending activation event:', error);
        } finally {
            activationInFlight = false;
        }
    }

    function buildRegionLookup(list) {
        const lookup = {};
        if (!Array.isArray(list)) return lookup;

        for (const row of list) {
            if (!row || !row.country || !row.region) continue;
            lookup[regionKey(row.country, row.region)] = {
                count: row.count || 0,
                country: row.country,
                region: row.region
            };
        }
        return lookup;
    }

    function displayCountryLabel(country) {
        if (!country) return "";
        return EU_MEMBERS.has(country) ? EU_LABEL : country;
    }

    function formatLocation(region, country) {
        const displayCountry = displayCountryLabel(country);
        if (!region) return displayCountry || "Unknown";

        // Avoid duplication when region == country (e.g., New Zealand)
        if (region === displayCountry) return displayCountry || region;

        // EU: use group label as country part
        if (EU_MEMBERS.has(country)) return `${region}, ${EU_LABEL}`;

        return displayCountry ? `${region}, ${displayCountry}` : region;
    }

    // ✅ Correct querystring builder (prevents your `...?region=X?includeY=...` bug forever)
    function buildQueryParams() {
        const params = new URLSearchParams();
        params.set('includeRegion', toggleState.region ? 'true' : 'false');
        params.set('includeNational', toggleState.national ? 'true' : 'false');
        params.set('includeInternational', toggleState.international ? 'true' : 'false');
        return params.toString();
    }

    function allTogglesOff() {
        return (!toggleState.region && !toggleState.national && !toggleState.international);
    }

    function validateToggles() {
        const errorElement = document.getElementById('toggleError');
        if (!errorElement) return;

        if (allTogglesOff()) {
            errorElement.classList.remove('d-none');

            const tableElement = document.getElementById('state-species');
            if (tableElement) tableElement.classList.add('d-none');

            currentSelected = null;

            // Close and unbind all tooltips
            if (geojsonLayer) {
                geojsonLayer.eachLayer(function (layer) {
                    layer.closeTooltip();
                    layer.unbindTooltip();
                });
            }
        } else {
            errorElement.classList.add('d-none');
        }
    }

    /******************************
     * API: COUNTS + MAP COLORING
     ******************************/

    function refreshMapColors() {
        if (allTogglesOff()) {
            if (geojsonLayer) geojsonLayer.setStyle(styleFeature);
            return;
        }

        fetch(`/api/region-weed-counts?${buildQueryParams()}`)
            .then(r => r.json())
            .then(list => {
                regionWeedData = buildRegionLookup(list);
                if (geojsonLayer) geojsonLayer.setStyle(styleFeature);
            })
            .catch(err => console.error('Error refreshing map colors:', err));
    }

    function refreshTableData() {
        if (!currentSelected) return;
        loadRegionDetails(currentSelected.country, currentSelected.region);
    }

    /******************************
     * TABLE RENDERING
     ******************************/

    function buildScopeText() {
        const parts = [];
        if (toggleState.region) parts.push('Regional');
        if (toggleState.national) parts.push('National');
        if (toggleState.international) parts.push('International');
        return parts.length ? parts.join(' + ') : 'No layers selected';
    }

    function updateTable(country, region, weeds, hasAnyData) {
        const scopeText = buildScopeText();
        const allWeeds = Array.isArray(weeds) ? weeds : [];
        const sampleWeeds = allWeeds.slice(0, SAMPLE_PLANT_LIMIT);

        // Title
        const titleLocation = formatLocation(region, country);
        const title = `Regulated plants in ${titleLocation}`;
        const titleEl = document.getElementById('state-title');
        if (titleEl) titleEl.textContent = title;

        const warningEl = document.getElementById('state-warning');
        if (warningEl) {
            warningEl.innerHTML = '<strong>Sample only.</strong> For full list please contact our team.';
            warningEl.classList.remove('d-none');
        }

        const subtitleEl = document.getElementById('state-subtitle');
        if (subtitleEl) {
            subtitleEl.textContent = scopeText ? `Filters: ${scopeText}` : '';
        }

        const table = document.getElementById('species-table');
        if (!table) return;

        const hasDataAnyLevel = !!hasAnyData;
        const isEUCountry = EU_MEMBERS.has(country);
        let emptyMessage = 'No plants are available for the selected filters. Please change the level of regulation using the toggles.';
        if (!hasDataAnyLevel && !isEUCountry) {
            emptyMessage = 'No published species specific regulations have been found for this country.';
        }

        if ($.fn.DataTable.isDataTable(table)) {
            $(table).DataTable().destroy();
            $(table).empty();
            $(table).html('<thead><tr><th>Scientific Name</th><th>Common Name</th><th>Family</th><th>Source</th></tr></thead>');
        }

        $(table).DataTable({
            data: sampleWeeds,
            columns: [
                {
                    data: 'canonical_name',
                    title: 'Scientific Name',
                    width: '27%',
                    render: function (data, type, row) {
                        if (type !== 'display') return data || '';
                        if (type === 'display' && data) {
                            return `<a href="/species?name=${encodeURIComponent(data)}" class="species-link" target="_blank"><em>${escapeHtml(data)}</em></a>`;
                        }
                        return 'Unknown';
                    }
                },
                {
                    data: 'common_name',
                    title: 'Common Name',
                    width: '23%',
                    render: function (data, type, row) {
                        const displayCommonName = primaryCommonName(data);
                        if (type !== 'display') return data || '';
                        if (!displayCommonName || String(data).includes('No English common names available')) {
                            return `(${escapeHtml(row.canonical_name || 'Unknown')})`;
                        }
                        return escapeHtml(displayCommonName);
                    }
                },
                {
                    data: 'family_name',
                    title: 'Family',
                    width: '15%',
                    render: function (data) {
                        return escapeHtml(data || 'Unknown');
                    }
                },
                {
                    data: 'source_authority',
                    title: 'Source',
                    width: '35%',
                    render: function (data, type, row) {
                        const sourceAuthority = data || row.level || 'Unknown';
                        if (type !== 'display') return sourceAuthority;
                        return `<span>${escapeHtml(sourceAuthority)}</span>`;
                    }
                }
            ],
            paging: false,
            searching: false,
            info: false,
            lengthChange: false,
            order: [[0, 'asc']],
            autoWidth: false,
            width: '100%',
            language: {
                emptyTable: emptyMessage
            },
            initComplete: function () {
                const element = document.getElementById('state-species');
                if (element) {
                    element.classList.remove('d-none');
                    element.classList.add('updated');
                    setTimeout(() => element.classList.remove('updated'), 1000);


                    if (pendingScrollToTable || (window.L && L.Browser && L.Browser.mobile)) {
                        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                        pendingScrollToTable = false;
                    }
                }
            }
        });
    }

    function loadRegionDetails(country, region) {
        if (!country || !region) return;

        const url =
            `/api/region?country=${encodeURIComponent(country)}&region=${encodeURIComponent(region)}&${buildQueryParams()}`;

        fetch(url)
            .then(r => r.json())
            .then(result => {
                const weeds = Array.isArray(result) ? result : (result.weeds || []);
                const hasAnyData = Array.isArray(result) ? weeds.length > 0 : !!result.has_any_data;
                updateTable(country, region, weeds, hasAnyData);
                sendAhaActivationIfNeeded(weeds.length);
            })
            .catch(err => {
                console.error('Error fetching region data:', err);
                const titleEl = document.getElementById('state-title');
                if (titleEl) titleEl.textContent = `Error loading data for ${formatLocation(region, country)}`;
                const warningEl = document.getElementById('state-warning');
                if (warningEl) {
                    warningEl.innerHTML = '';
                    warningEl.classList.add('d-none');
                }
                const subtitleEl = document.getElementById('state-subtitle');
                if (subtitleEl) subtitleEl.textContent = '';
            });
    }

    /******************************
     * STYLE FUNCTION
     ******************************/
    function styleFeature(feature) {
        if (allTogglesOff()) {
            return {
                fillColor: '#ffffff',
                weight: 1,
                opacity: 1,
                color: '#cccccc',
                fillOpacity: 0.3
            };
        }

        const region = extractRegionName(feature);
        const country = extractCountryName(feature);

        if (!region || !country) {
            return {
                fillColor: '#cccccc',
                weight: 1,
                opacity: 1,
                color: 'white',
                fillOpacity: 0.5
            };
        }

        const key = regionKey(country, region);
        const data = regionWeedData[key] || { count: 0, country, region };
        const weedCount = data.count || 0;
        const locationLabel = formatLocation(region, country);

        return {
            fillColor: getColor(weedCount, country),
            weight: 1,
            opacity: 1,
            color: 'white',
            fillOpacity: 0.7
        };
    }

    /******************************
     * MAP INITIALIZATION
     ******************************/
    const map = L.map('map', {
        dragging: !L.Browser.mobile,
        tap: !L.Browser.mobile,
        worldCopyJump: false,
        maxBoundsViscosity: 1.0,
        attributionControl: true,
        zoomControl: true
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    /******************************
     * DATA LOADING
     ******************************/
    fetch(`/api/region-weed-counts?${buildQueryParams()}`)
        .then(r => r.json())
        .then(list => {
            regionWeedData = buildRegionLookup(list);
            return fetch('/api/geojson-files');
        })
        .then(r => {
            if (!r.ok) throw new Error('Failed to load GeoJSON file list');
            return r.json();
        })
        .then(geojsonFiles => {
            const geojsonPath = MAP_CONFIG.geojsonPath || GEOJSON_PATH;

            const geoJsonPromises = geojsonFiles.map(filename =>
                fetch(geojsonPath + filename)
                    .then(response => {
                        if (!response.ok) throw new Error(`Failed to load ${filename}`);
                        return response.json();
                    })
                    .then(geojson => {
                        // Attach country to each feature (inferred from filename) if not present
                        const inferredCountry = inferCountryFromFilename(filename);
                        if (geojson && Array.isArray(geojson.features)) {
                            geojson.features.forEach(f => {
                                f.properties = f.properties || {};
                                if (!f.properties.country) f.properties.country = inferredCountry;
                            });
                        }
                        return geojson;
                    })
                    .catch(error => {
                        console.error(`Error loading ${filename}:`, error);
                        return { type: 'FeatureCollection', features: [] };
                    })
            );

            return Promise.all(geoJsonPromises);
        })
        .then(results => {
            const combinedFeatures = [];
            results.forEach(result => {
                if (result.features && Array.isArray(result.features)) {
                    combinedFeatures.push(...result.features);
                }
            });

            const combinedGeoJSON = {
                type: 'FeatureCollection',
                features: combinedFeatures
            };

            /******************************
             * MAP INTERACTION
             ******************************/
            let previouslyClickedLayer = null;

            geojsonLayer = L.geoJson(combinedGeoJSON, {
                style: styleFeature,
                onEachFeature: function (feature, layer) {
                    const region = extractRegionName(feature);
                    const country = extractCountryName(feature);
                    if (!region || !country) return;

                    const key = regionKey(country, region);

                    // Click
                    layer.on('click', function () {
                        if (allTogglesOff()) return;

                        if (previouslyClickedLayer) geojsonLayer.resetStyle(previouslyClickedLayer);
                        previouslyClickedLayer = layer;

                        currentSelected = { country, region };
                        pendingScrollToTable = true;
                        loadRegionDetails(country, region);
                    });

                    // Hover
                    layer.on('mouseover', function () {
                        if (allTogglesOff()) {
                            layer.closeTooltip();
                            layer.unbindTooltip();
                            return;
                        }

                        layer.setStyle({ weight: 2, fillOpacity: 0.9 });

                        const data = regionWeedData[key] || { count: 0, country, region };
                        const weedCount = data.count || 0;
                        const locationLabel = formatLocation(region, country);
                        const safeLocationLabel = escapeHtml(locationLabel);

                        const tooltipContent = `
                            <strong>${safeLocationLabel}</strong><br>
                            Regulated Plants: ${weedCount}
                        `;

                        layer
                            .bindTooltip(tooltipContent, {
                                sticky: true,
                                direction: 'top',
                                opacity: 0.9
                            })
                            .openTooltip();
                    });

                    layer.on('mouseout', function () {
                        if (allTogglesOff()) return;

                        geojsonLayer.resetStyle(layer);
                        if (layer === previouslyClickedLayer) {
                            layer.setStyle({ weight: 2, fillOpacity: 0.9 });
                        }
                    });

                    // For highlight event matching (region name)
                    layer.featureRegionName = region;
                    layer.featureRegionNameLower = region.toLowerCase();
                    layer.featureCountryName = country;
                    layer.featureKey = key;
                }
            }).addTo(map);

            // Bounds
            const northAmericaAndAustraliaBounds = [
                [-45, -170],
                [70, 155]
            ];

            map.fitBounds(northAmericaAndAustraliaBounds, {
                padding: [20, 20],
                maxZoom: 3
            });

            map.setMaxBounds([
                [-90, -190],
                [90, 190]
            ]);

            map.options.worldCopyJump = false;
            map.setMinZoom(map.getZoom());
        })
        .catch(error => {
            console.error('Error loading map data:', error);
            const mapElement = document.getElementById('map');
            if (mapElement) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'map-error-message';
                errorDiv.innerHTML = '<strong>Error:</strong> Failed to load map data.';
                mapElement.appendChild(errorDiv);
            }
        });

    /******************************
     * HIGHLIGHT EVENT (home_highlights.js)
     ******************************/
    window.addEventListener('highlight:showState', function (event) {
        // We keep the same event name so home_highlights.js doesn't need changes.
        // It passes "state", but in the new model that is actually "region".
        const targetRegion = event.detail && event.detail.state;
        if (!targetRegion) return;

        const normalizedTarget = targetRegion.toLowerCase();
        if (event.detail && event.detail.scroll) pendingScrollToTable = true;

        if (allTogglesOff()) {
            validateToggles();
            return;
        }

        let matchedLayer = null;

        if (geojsonLayer) {
            geojsonLayer.eachLayer(function (layer) {
                if (layer.featureRegionNameLower && layer.featureRegionNameLower === normalizedTarget) {
                    matchedLayer = layer;
                }
            });
        }

        if (matchedLayer) {
            matchedLayer.fire('click');
        } else {
            console.warn('No matching region found for highlight:', targetRegion);
        }
    });

    /******************************
     * TOGGLE EVENT LISTENERS
     ******************************/
    const nationalToggle = document.getElementById('nationalToggle');
    const regionToggle = document.getElementById('regionToggle');
    const internationalToggle = document.getElementById('internationalToggle');

    if (nationalToggle) {
        nationalToggle.addEventListener('change', function () {
            toggleState.national = this.checked;
            validateToggles();
            refreshMapColors();
            if (currentSelected && !allTogglesOff()) refreshTableData();
        });
    }

    if (regionToggle) {
        regionToggle.addEventListener('change', function () {
            toggleState.region = this.checked;
            validateToggles();
            refreshMapColors();
            if (currentSelected && !allTogglesOff()) refreshTableData();
        });
    }

    if (internationalToggle) {
        internationalToggle.addEventListener('change', function () {
            toggleState.international = this.checked;
            validateToggles();
            refreshMapColors();
            if (currentSelected && !allTogglesOff()) refreshTableData();
        });
    }

    // Initial validation
    validateToggles();
});
