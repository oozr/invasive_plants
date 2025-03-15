document.addEventListener('DOMContentLoaded', function() {
    /******************************
     * CONFIGURATION & CONSTANTS
     ******************************/
    const mapConfig = {
        center: [45, -95],
        zoom: 3,
        // Default color schemes that can be extended
        countryColors: {
            'US': {
                thresholds: [0, 100, 135, 170, 205, 240],
                scheme: ['#FFEDA0', '#FEB24C', '#FD8D3C', '#FC4E2A', '#E31A1C', '#BD0026', '#800026']
            },
            'Canada': {
                thresholds: [0, 100, 135, 170, 205, 240],
                scheme: ['#f2f0f7', '#d8daeb', '#bcbddc', '#9e9ac8', '#807dba', '#6a51a3', '#4a1486']
            },
            // Default scheme for any new countries - can be customized later
            'default': {
                thresholds: [0, 100, 135, 170, 205, 240],
                scheme: ['#edf8e9', '#c7e9c0', '#a1d99b', '#74c476', '#41ab5d', '#238b45', '#005a32']
            }
        }
    };

    // Store our state data globally for reference
    let stateWeedData = {};
    // Track unique countries for legend creation
    let countriesInData = new Set();

    /******************************
     * UTILITY FUNCTIONS
     ******************************/
    // Get color based on data value and country
    function getColor(d, country) {
        // Get the color scheme for this country, fall back to default if not defined
        const colorConfig = mapConfig.countryColors[country] || mapConfig.countryColors['default'];
        const { thresholds, scheme } = colorConfig;
        
        if (d > thresholds[5]) return scheme[6];
        if (d > thresholds[4]) return scheme[5];
        if (d > thresholds[3]) return scheme[4];
        if (d > thresholds[2]) return scheme[3];
        if (d > thresholds[1]) return scheme[2];
        if (d > thresholds[0]) return scheme[1];
        return scheme[0];
    }

    // Get the country for a state/province from our data
    function getCountryForState(stateName) {
        return (stateWeedData[stateName] && stateWeedData[stateName].country) || 'default';
    }

    // Set map height based on screen size
    function setMapHeight() {
        const mapElement = document.getElementById('map');
        if (window.innerWidth <= 768) {
            mapElement.style.height = '300px';
        } else {
            mapElement.style.height = '500px';
        }
    }

    // Highlight results after data loads
    function highlightResults() {
        const element = document.getElementById('state-species');
        element.classList.add('updated');
        setTimeout(() => {
            element.classList.remove('updated');
        }, 1000);
    }

    // Style function for GeoJSON features
    function styleFeature(feature) {
        let stateName = feature.properties.name || feature.properties.NAME;
        stateName = stateName ? stateName.trim() : '';
        console.log('Looking up state/province:', stateName);
        
        const stateData = stateWeedData[stateName] || { count: 0, country: 'default' };
        const weedCount = stateData.count || 0;
        const country = stateData.country;
        
        if (weedCount === 0) {
            console.log(`No match found for "${stateName}" in weed count data`);
        }

        // Track this country for legend creation
        if (country) {
            countriesInData.add(country);
        }

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
    // Set initial map height
    setMapHeight();
    window.addEventListener('resize', setMapHeight);

    // Initialize map
    const map = L.map('map', {
        dragging: !L.Browser.mobile,
        tap: !L.Browser.mobile
    }).setView(mapConfig.center, mapConfig.zoom);

    // Add tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    /******************************
     * DATA LOADING & PROCESSING
     ******************************/
    // Fetch state weed counts
    fetch('/api/state-weed-counts')
        .then(response => response.json())
        .then(data => {
            // Store the data globally for reference
            stateWeedData = data;
            console.log('State weed data received:', stateWeedData);
            
            // Extract list of all countries represented in the data
            Object.values(stateWeedData).forEach(stateData => {
                if (stateData.country) {
                    countriesInData.add(stateData.country);
                }
            });
            console.log('Countries in data:', [...countriesInData]);

            // Load all available GeoJSON files
            // This assumes you have a standard naming convention for GeoJSON files
            // Or you could create an endpoint that returns a list of available GeoJSON files
            const geoJsonPromises = [];
            
            // Add core GeoJSON files - in a more advanced implementation, you might
            // fetch a list of available files from the server
            geoJsonPromises.push(fetch('/static/data/us-states.geojson').then(response => response.json()));
            geoJsonPromises.push(fetch('/static/data/canada-provinces.geojson').then(response => response.json()));
            
            // You could extend this with additional files as your application grows
            // geoJsonPromises.push(fetch('/static/data/mexico-states.geojson').then(response => response.json()));
            
            Promise.all(geoJsonPromises)
            .then((results) => {
                // Combine all features from all GeoJSON files
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
                 * MAP LAYER CREATION
                 ******************************/
                let previouslyClickedLayer = null;
                let geojsonLayer = L.geoJson(combinedGeoJSON, {
                    style: styleFeature,
                    onEachFeature: function(feature, layer) {
                        let stateName = feature.properties.name || feature.properties.NAME;
                        stateName = stateName ? stateName.trim() : '';
                        
                        /******************************
                         * EVENT HANDLERS
                         ******************************/
                        // Click event
                        layer.on('click', function(e) {
                            // Reset style of previously clicked state
                            if (previouslyClickedLayer) {
                                geojsonLayer.resetStyle(previouslyClickedLayer);
                            }

                            // Store current layer as previously clicked
                            previouslyClickedLayer = layer;

                            fetch(`/api/state/${encodeURIComponent(stateName)}`)
                                .then(response => response.json())
                                .then(weeds => {
                                    // Get the country for this state/province
                                    const stateData = stateWeedData[stateName] || {};
                                    const country = stateData.country || '';
                                    
                                    // Update title with both state and country
                                    document.getElementById('state-title').textContent = 
                                        `Regulated Weeds in ${stateName}${country ? `, ${country}` : ''}`;
                                    
                                    // Clear the table first
                                    const table = document.getElementById('species-table');
                                    
                                    // Destroy existing DataTable if it exists
                                    if ($.fn.DataTable.isDataTable(table)) {
                                        $(table).DataTable().destroy();
                                        // Clear the table contents after destroying
                                        $(table).empty();
                                        // Re-add the header structure
                                        $(table).html('<thead><tr><th>Scientific Name</th><th>Family</th></tr></thead>');
                                    }
                        
                                    // Initialize new DataTable
                                    $(table).DataTable({
                                        stripe: false,
                                        hover: true,
                                        stripeClasses: [],
                                        rowClass: '',
                                        data: weeds,
                                        columns: [
                                            { 
                                                data: 'canonical_name',
                                                title: 'Scientific Name',
                                                width: '50%',
                                                render: function(data, type, row) {
                                                    if (type === 'display' && data) {
                                                        // Pass the canonical name as a parameter
                                                        return `<a href="/species?name=${encodeURIComponent(data)}" class="species-link" target="_blank">${data || 'Unknown'}</a>`;
                                                    }
                                                    return data || 'Unknown';
                                                }
                                            },
                                            { 
                                                data: 'family_name',
                                                title: 'Family',
                                                width: '50%',
                                                render: function(data, type, row) {
                                                    return data || 'Unknown';
                                                }
                                            }
                                        ],
                                        pageLength: 10,
                                        order: [[0, 'asc']],
                                        autoWidth: false,
                                        width: '100%',
                                        language: {
                                            search: 'Search:',
                                            lengthMenu: 'Show _MENU_ entries',
                                            info: 'Showing _START_ to _END_ of _TOTAL_ entries',
                                            paginate: {
                                                first: '«',
                                                previous: '‹',
                                                next: '›',
                                                last: '»'
                                            }
                                        },
                                        initComplete: function() {
                                            document.getElementById('state-species').classList.remove('d-none');
                                            highlightResults();
                                            if (L.Browser.mobile) {
                                                document.getElementById('state-species')
                                                    .scrollIntoView({ 
                                                        behavior: 'smooth',
                                                        block: 'start'
                                                    });
                                            }
                                        }
                                    });
                                });
                        });

                        // Hover effects
                        layer.on('mouseover', function(e) {
                            layer.setStyle({
                                weight: 2,
                                fillOpacity: 0.9
                            });
                        });

                        layer.on('mouseout', function(e) {
                            geojsonLayer.resetStyle(layer);
                            if (layer === previouslyClickedLayer) {
                                layer.setStyle({
                                    weight: 2,
                                    fillOpacity: 0.9
                                });
                            }
                        });
                    }
                }).addTo(map);

                /******************************
                 * LEGEND CREATION
                 ******************************/
                let legend = L.control({ position: 'bottomright' });
                legend.onAdd = function() {
                    let div = L.DomUtil.create('div', 'legend');
                    
                    // Create legend entries for each country in the data
                    // Sort them alphabetically for consistent display
                    [...countriesInData].sort().forEach(country => {
                        // Get the color scheme for this country
                        const colorConfig = mapConfig.countryColors[country] || mapConfig.countryColors['default'];
                        
                        // Add a header for this country
                        div.innerHTML += `<div style="margin-bottom:5px;"><strong>${country}</strong></div>`;
                        
                        // Add legend entries for each threshold
                        for (let i = 0; i < colorConfig.thresholds.length; i++) {
                            const threshold = colorConfig.thresholds[i];
                            const nextThreshold = colorConfig.thresholds[i+1];
                            
                            div.innerHTML +=
                                '<div><i style="background:' + getColor(threshold + 1, country) + '"></i> ' +
                                threshold + (nextThreshold ? '&ndash;' + nextThreshold : '+') + '</div>';
                        }
                        
                        // Add some spacing between countries
                        if (country !== [...countriesInData].sort().pop()) {
                            div.innerHTML += '<div style="margin:8px 0 5px 0;"></div>';
                        }
                    });

                    return div;
                };
                legend.addTo(map);
            })
            .catch(error => {
                console.error("Error loading GeoJSON files:", error);
            });
        });
});