document.addEventListener('DOMContentLoaded', function() {
    /******************************
     * CONFIGURATION & CONSTANTS
     ******************************/
    const mapConfig = {
        center: [45, -95],
        zoom: 3,
        colors: {
            us: {
                thresholds: [0, 110, 150, 190, 230, 270],  // Adjusted for maximum of ~290
                scheme: ['#FFEDA0', '#FEB24C', '#FD8D3C', '#FC4E2A', '#E31A1C', '#BD0026', '#800026']
            },
            canada: {
                thresholds: [0, 110, 150, 190, 230, 270],  // Same thresholds as US
                scheme: ['#f2f0f7', '#d8daeb', '#bcbddc', '#9e9ac8', '#807dba', '#6a51a3', '#4a1486']
            }
        }
    };

    // List of Canadian provinces for country detection
    const canadianProvinces = [
        'Alberta', 'British Columbia', 'Manitoba', 'New Brunswick', 
        'Newfoundland & Labrador', 'Newfoundland  & Labrador', 'Nova Scotia', 
        'Northwest Territories', 'Nunavut', 'Ontario', 'Prince Edward Island', 
        'Quebec', 'Saskatchewan', 'Yukon Territory'
    ];

    /******************************
     * UTILITY FUNCTIONS
     ******************************/
    // Get color based on data value and country
    function getColor(d, isCanada = false) {
        const config = isCanada ? mapConfig.colors.canada : mapConfig.colors.us;
        const { thresholds, scheme } = config;
        
        if (d > thresholds[5]) return scheme[6];
        if (d > thresholds[4]) return scheme[5];
        if (d > thresholds[3]) return scheme[4];
        if (d > thresholds[2]) return scheme[3];
        if (d > thresholds[1]) return scheme[2];
        if (d > thresholds[0]) return scheme[1];
        return scheme[0];
    }

    // Determine if a region is in Canada
    function isCanadianProvince(name) {
        return canadianProvinces.includes(name);
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
    function styleFeature(feature, stateWeedCount) {
        let stateName = feature.properties.name || feature.properties.NAME;
        stateName = stateName ? stateName.trim() : '';
        console.log('Looking up state/province:', stateName);
        let weedCount = stateWeedCount[stateName] || 0;
        
        if (weedCount === 0) {
            console.log(`No match found for "${stateName}" in weed count data`);
        }

        // Determine if this is a Canadian province
        const isCanada = isCanadianProvince(stateName);

        return {
            fillColor: getColor(weedCount, isCanada),
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
        .then(stateWeedCount => {
            console.log('State weed counts received:', stateWeedCount);
            console.log('Available states in API data:', Object.keys(stateWeedCount).sort());

            // Load both US states and Canadian provinces
            Promise.all([
                fetch('/static/data/us-states.geojson').then(response => response.json()),
                fetch('/static/data/canada-provinces.geojson').then(response => response.json())
            ])
            .then(([usData, canadaData]) => {
                // Log state/province names for debugging
                console.log('US state names in GeoJSON:');
                usData.features.forEach(feature => {
                    console.log(feature.properties.name || feature.properties.NAME);
                });
                
                console.log('Canadian province names in GeoJSON:');
                canadaData.features.forEach(feature => {
                    console.log(feature.properties.name || feature.properties.NAME);
                });

                // Combine the features from both datasets
                const combinedGeoJSON = {
                    type: 'FeatureCollection',
                    features: [...usData.features, ...canadaData.features]
                };
                
                /******************************
                 * MAP LAYER CREATION
                 ******************************/
                let previouslyClickedLayer = null;
                let geojsonLayer = L.geoJson(combinedGeoJSON, {
                    style: feature => styleFeature(feature, stateWeedCount),
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
                                    document.getElementById('state-title').textContent = `Regulated Weeds in ${stateName}`;
                                    
                                    // Clear the table first
                                    const table = document.getElementById('species-table');
                                    
                                    // Destroy existing DataTable if it exists
                                    if ($.fn.DataTable.isDataTable(table)) {
                                        $(table).DataTable().destroy();
                                        // Clear the table contents after destroying
                                        $(table).empty();
                                        // Re-add the header structure
                                        $(table).html('<thead><tr><th>Common Name</th><th>Family</th></tr></thead>');
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
                                                data: 'common_name',
                                                title: 'Common Name',
                                                width: '50%',
                                                render: function(data, type, row) {
                                                    if (type === 'display' && row.usage_key) {
                                                        return `<a href="https://www.gbif.org/species/${row.usage_key}" target="_blank">${data || 'Unknown'}</a>`;
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
                    
                    // US Legend
                    div.innerHTML = '<div style="margin-bottom:5px;"><strong>United States</strong></div>';
                    for (let i = 0; i < mapConfig.colors.us.thresholds.length; i++) {
                        const threshold = mapConfig.colors.us.thresholds[i];
                        const nextThreshold = mapConfig.colors.us.thresholds[i+1];
                        
                        div.innerHTML +=
                            '<div><i style="background:' + getColor(threshold + 1, false) + '"></i> ' +
                            threshold + (nextThreshold ? '&ndash;' + nextThreshold : '+') + '</div>';
                    }
                    
                    // Canadian Legend
                    div.innerHTML += '<div style="margin:8px 0 5px 0;"><strong>Canada</strong></div>';
                    for (let i = 0; i < mapConfig.colors.canada.thresholds.length; i++) {
                        const threshold = mapConfig.colors.canada.thresholds[i];
                        const nextThreshold = mapConfig.colors.canada.thresholds[i+1];
                        
                        div.innerHTML +=
                            '<div><i style="background:' + getColor(threshold + 1, true) + '"></i> ' +
                            threshold + (nextThreshold ? '&ndash;' + nextThreshold : '+') + '</div>';
                    }

                    return div;
                };
                legend.addTo(map);
            })
            .catch(error => {
                console.error("Error loading GeoJSON files:", error);
            });
        });
});