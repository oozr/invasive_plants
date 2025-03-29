document.addEventListener('DOMContentLoaded', function() {
    /******************************
     * CONFIGURATION
     ******************************/
    const mapConfig = {
        center: [30, 0],
        zoom: 2,
        countryColors: {
            'US': {
                thresholds: [0, 100, 135, 170, 205, 240],
                scheme: ['#FFEDA0', '#FEB24C', '#FD8D3C', '#FC4E2A', '#E31A1C', '#BD0026', '#800026']
            },
            'Canada': {
                thresholds: [0, 100, 135, 170, 205, 240],
                scheme: ['#f2f0f7', '#d8daeb', '#bcbddc', '#9e9ac8', '#807dba', '#6a51a3', '#4a1486']
            },
            'Australia': {
                thresholds: [0, 100, 135, 170, 205, 240],
                scheme: ['#edf8e9', '#c7e9c0', '#a1d99b', '#74c476', '#41ab5d', '#238b45', '#005a32']
            },
            'default': {
                thresholds: [0, 100, 135, 170, 205, 240],
                scheme: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5']
            }
        }
    };

    // Store state data globally
    let stateWeedData = {};
    
    /******************************
     * UTILITY FUNCTIONS
     ******************************/
    // Get color based on data value and country
    function getColor(d, country) {
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

    // Set map height based on screen size
    function setMapHeight() {
        const mapElement = document.getElementById('map');
        mapElement.style.height = window.innerWidth <= 768 ? '300px' : '500px';
    }

    // Style function for GeoJSON features
    function styleFeature(feature) {
        // Try different property names for state names
        const possibleNameProps = ['name', 'NAME', 'STATE_NAME', 'state', 'STATE'];
        let stateName = null;
        
        for (const prop of possibleNameProps) {
            if (feature.properties[prop]) {
                stateName = feature.properties[prop].trim();
                break;
            }
        }
        
        if (!stateName) return { fillColor: '#cccccc', weight: 1, opacity: 1, color: 'white', fillOpacity: 0.5 };
        
        const stateData = stateWeedData[stateName] || { count: 0, country: 'default' };
        const weedCount = stateData.count || 0;
        const country = stateData.country || 'default';

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
    setMapHeight();
    window.addEventListener('resize', setMapHeight);

    const map = L.map('map', {
        dragging: !L.Browser.mobile,
        tap: !L.Browser.mobile,
        worldCopyJump: true
    }).setView(mapConfig.center, mapConfig.zoom);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    /******************************
     * DATA LOADING
     ******************************/
    fetch('/api/state-weed-counts')
        .then(response => response.json())
        .then(data => {
            stateWeedData = data;
            
            // Get list of geojson files
            const geojsonPath = '/static/data/';
            const knownFiles = [
                'us-states.geojson', 
                'canada-provinces.geojson', 
                'australia.geojson'
                // Add new files here as needed
            ];
            
            const geoJsonPromises = knownFiles.map(filename => 
                fetch(geojsonPath + filename)
                    .then(response => response.ok ? response.json() : Promise.reject(`Failed to load ${filename}`))
                    .catch(error => {
                        console.error(`Error loading ${filename}:`, error);
                        return { type: 'FeatureCollection', features: [] };
                    })
            );
            
            Promise.all(geoJsonPromises)
            .then((results) => {
                // Combine features from all geojson files
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
                let geojsonLayer = L.geoJson(combinedGeoJSON, {
                    style: styleFeature,
                    onEachFeature: function(feature, layer) {
                        // Get state name from properties
                        const possibleNameProps = ['name', 'NAME', 'STATE_NAME', 'state', 'STATE'];
                        let stateName = null;
                        
                        for (const prop of possibleNameProps) {
                            if (feature.properties[prop]) {
                                stateName = feature.properties[prop].trim();
                                break;
                            }
                        }
                        
                        if (!stateName) return;
                        
                        // Click event
                        layer.on('click', function(e) {
                            if (previouslyClickedLayer) {
                                geojsonLayer.resetStyle(previouslyClickedLayer);
                            }
                            previouslyClickedLayer = layer;
                            
                            fetch(`/api/state/${encodeURIComponent(stateName)}`)
                                .then(response => response.json())
                                .then(weeds => {
                                    const stateData = stateWeedData[stateName] || {};
                                    const country = stateData.country || '';
                                    
                                    document.getElementById('state-title').textContent = 
                                        `Regulated Weeds in ${stateName}${country ? `, ${country}` : ''}`;
                                    
                                    const table = document.getElementById('species-table');
                                    
                                    if ($.fn.DataTable.isDataTable(table)) {
                                        $(table).DataTable().destroy();
                                        $(table).empty();
                                        $(table).html('<thead><tr><th>Scientific Name</th><th>Family</th></tr></thead>');
                                    }
                        
                                    $(table).DataTable({
                                        data: weeds,
                                        columns: [
                                            { 
                                                data: 'canonical_name',
                                                title: 'Scientific Name',
                                                width: '50%',
                                                render: function(data, type, row) {
                                                    if (type === 'display' && data) {
                                                        return `<a href="/species?name=${encodeURIComponent(data)}" class="species-link" target="_blank">${data || 'Unknown'}</a>`;
                                                    }
                                                    return data || 'Unknown';
                                                }
                                            },
                                            { 
                                                data: 'family_name',
                                                title: 'Family',
                                                width: '50%',
                                                render: function(data) {
                                                    return data || 'Unknown';
                                                }
                                            }
                                        ],
                                        pageLength: 10,
                                        order: [[0, 'asc']],
                                        autoWidth: false,
                                        width: '100%',
                                        initComplete: function() {
                                            const element = document.getElementById('state-species');
                                            element.classList.remove('d-none');
                                            element.classList.add('updated');
                                            setTimeout(() => element.classList.remove('updated'), 1000);
                                            
                                            if (L.Browser.mobile) {
                                                element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                            }
                                        }
                                    });
                                })
                                .catch(error => {
                                    console.error("Error fetching state data:", error);
                                    document.getElementById('state-title').textContent = 
                                        `Error loading data for ${stateName}`;
                                });
                        });

                        // Hover effects
                        layer.on('mouseover', function() {
                            layer.setStyle({ weight: 2, fillOpacity: 0.9 });
                            
                            // Get weed count data for tooltip
                            const stateData = stateWeedData[stateName] || {};
                            const weedCount = stateData.count || 0;
                            const country = stateData.country || '';
                            
                            // Create tooltip content
                            const tooltipContent = `
                                <strong>${stateName}${country ? `, ${country}` : ''}</strong><br>
                                Regulated Weeds: ${weedCount}
                            `;
                            
                            // Add or update tooltip
                            layer.bindTooltip(tooltipContent, {
                                sticky: true,
                                direction: 'top',
                                opacity: 0.9
                            }).openTooltip();
                        });

                        layer.on('mouseout', function() {
                            geojsonLayer.resetStyle(layer);
                            if (layer === previouslyClickedLayer) {
                                layer.setStyle({ weight: 2, fillOpacity: 0.9 });
                            }
                        });
                    }
                }).addTo(map);
                
                try {
                    map.fitBounds(geojsonLayer.getBounds(), {
                        padding: [20, 20],
                        maxZoom: 3 // Limit max zoom level
                    });
                    
                    setTimeout(() => {
                        const currentZoom = map.getZoom();
                        map.setZoom(currentZoom + 1.5);
                        
                        const center = map.getCenter();
                        map.panTo([center.lat, center.lng - 30]);
                    }, 100);
                } catch (e) {
                    console.error('Error fitting map to bounds:', e);
                    map.setView([30, -30], 3);
                }
            })
            .catch(error => {
                console.error("Error processing GeoJSON:", error);
                const mapElement = document.getElementById('map');
                const errorDiv = document.createElement('div');
                errorDiv.className = 'map-error-message';
                errorDiv.innerHTML = '<strong>Error:</strong> Failed to load map data.';
                mapElement.appendChild(errorDiv);
            });
        })
        .catch(error => {
            console.error("Error fetching state data:", error);
            const mapElement = document.getElementById('map');
            const errorDiv = document.createElement('div');
            errorDiv.className = 'map-error-message';
            errorDiv.innerHTML = '<strong>Error:</strong> Failed to load weed count data.';
            mapElement.appendChild(errorDiv);
        });
});