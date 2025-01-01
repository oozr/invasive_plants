document.addEventListener('DOMContentLoaded', function() {
    // Initialize the map
    const map = L.map('map').setView([37.8, -96], 4);

    // Add tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Fetch state weed counts from Flask endpoint
    fetch('/api/state-weed-counts')
        .then(response => response.json())
        .then(stateWeedCount => {
            // Load GeoJSON data
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
                            weight: 2,
                            opacity: 1,
                            color: 'white',
                            dashArray: '3',
                            fillOpacity: 0.7
                        };
                    }

                    L.geoJson(geojsonData, {
                        style: style,
                        onEachFeature: function(feature, layer) {
                            let stateName = feature.properties.name.trim();
                            layer.bindPopup(`${stateName}: ${stateWeedCount[stateName] || 0} weeds`);
                            layer.on('click', function() {
                                fetch(`/api/state/${stateName}`)
                                    .then(response => response.json())
                                    .then(weeds => {
                                        document.getElementById('state-title').textContent = `Regulated Weeds in ${stateName}`;
                                        
                                        // Destroy existing DataTable if it exists
                                        if ($.fn.DataTable.isDataTable('#species-table')) {
                                            $('#species-table').DataTable().destroy();
                                        }
                            
                                        // Initialize DataTable with width settings
                                        $('#species-table').DataTable({
                                            data: weeds,
                                            columns: [
                                                { 
                                                    data: 'weed_name', 
                                                    title: 'Weed Name',
                                                    width: '50%'  // Set column width
                                                },
                                                { 
                                                    data: 'category', 
                                                    title: 'Category',
                                                    width: '50%'  // Set column width
                                                }
                                            ],
                                            pageLength: 10,
                                            order: [[0, 'asc']],
                                            autoWidth: false,  // Disable auto width calculation
                                            width: '100%'      // Set table width
                                        });
                            
                                        document.getElementById('state-species').classList.remove('d-none');
                                    });
                            });
                        }
                    }).addTo(map);

                    // Add legend
                    let legend = L.control({ position: 'bottomright' });
                    legend.onAdd = function() {
                        let div = L.DomUtil.create('div', 'legend'),
                            grades = [0, 5, 10, 20, 50, 100];

                        div.innerHTML = '<style>.legend i { display: inline-block; width: 18px; height: 18px; margin-right: 8px; } .legend div { margin-bottom: 5px; }</style>';
                        
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