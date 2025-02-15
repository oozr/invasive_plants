document.addEventListener('DOMContentLoaded', function() {
    // Set dynamic map height based on screen size
    function setMapHeight() {
        const mapElement = document.getElementById('map');
        if (window.innerWidth <= 768) {
            mapElement.style.height = '300px';
        } else {
            mapElement.style.height = '500px';
        }
    }

    setMapHeight();
    window.addEventListener('resize', setMapHeight);

    // Initialize map
    const map = L.map('map', {
        dragging: !L.Browser.mobile,
        tap: !L.Browser.mobile
    }).setView([37.8, -96], 4);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    function highlightResults() {
        const element = document.getElementById('state-species');
        element.classList.add('updated');
        setTimeout(() => {
            element.classList.remove('updated');
        }, 1000);
    }

    // Fetch state weed counts
    fetch('/api/state-weed-counts')
        .then(response => response.json())
        .then(stateWeedCount => {
            fetch('/static/data/us-states.geojson')
                .then(response => response.json())
                .then(geojsonData => {
                    function getColor(d) {
                        return d > 100 ? '#800026' :
                               d > 50  ? '#BD0026' :
                               d > 20  ? '#E31A1C' :
                               d > 10  ? '#FC4E2A' :
                               d > 5   ? '#FD8D3C' :
                               d > 0   ? '#FEB24C' :
                                        '#FFEDA0';
                    }

                    function style(feature) {
                        let stateName = feature.properties.name.trim();
                        let weedCount = stateWeedCount[stateName] || 0;
                        return {
                            fillColor: getColor(weedCount),
                            weight: 1,
                            opacity: 1,
                            color: 'white',
                            fillOpacity: 0.7
                        };
                    }

                    let previouslyClickedLayer = null;
                    let geojsonLayer = L.geoJson(geojsonData, {
                        style: style,
                        onEachFeature: function(feature, layer) {
                            let stateName = feature.properties.name.trim();
                            
                            layer.on('click', function(e) {
                                // Reset style of previously clicked state
                                if (previouslyClickedLayer) {
                                    geojsonLayer.resetStyle(previouslyClickedLayer);
                                }

                                // Store current layer as previously clicked
                                previouslyClickedLayer = layer;

                                fetch(`/api/state/${stateName}`)
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
                                                        if (type === 'display') {
                                                            return `<a href="https://www.gbif.org/species/${row.usage_key}" target="_blank">${data}</a>`;
                                                        }
                                                        return data;
                                                    }
                                                },
                                                { 
                                                    data: 'family_name',
                                                    title: 'Family',
                                                    width: '50%'
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

                    // Add legend
                    let legend = L.control({ position: 'bottomright' });
                    legend.onAdd = function() {
                        let div = L.DomUtil.create('div', 'legend');
                        let grades = [0, 5, 10, 20, 50, 100];
                        
                        for (let i = 0; i < grades.length; i++) {
                            div.innerHTML +=
                                '<div><i style="background:' + getColor(grades[i] + 1) + '"></i> ' +
                                grades[i] + (grades[i + 1] ? '&ndash;' + grades[i + 1] : '+') + '</div>';
                        }

                        return div;
                    };
                    legend.addTo(map);
                });
        });
});