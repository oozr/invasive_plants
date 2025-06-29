document.addEventListener('DOMContentLoaded', function() {
    /******************************
     * CONFIGURATION
     ******************************/
    const mapConfig = {
        center: [30, 0],
        zoom: 2,
        countryColors: {
            'US': {
                thresholds: [0, 100, 150, 200, 250, 300],
                scheme: ['#FFEDA0', '#FEB24C', '#FD8D3C', '#FC4E2A', '#E31A1C', '#BD0026', '#800026']
            },
            'Canada': {
                thresholds: [0, 100, 150, 200, 250, 300],
                scheme: ['#f2f0f7', '#d8daeb', '#bcbddc', '#9e9ac8', '#807dba', '#6a51a3', '#4a1486']
            },
            'Australia': {
                thresholds: [0, 100, 150, 200, 250, 300],
                scheme: ['#edf8e9', '#c7e9c0', '#a1d99b', '#74c476', '#41ab5d', '#238b45', '#005a32']
            },
            'default': {
                thresholds: [0, 100, 150, 200, 250, 300],
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

    // Initialize map with options to prevent wrapping around the world
    const map = L.map('map', {
        dragging: !L.Browser.mobile,
        tap: !L.Browser.mobile,
        worldCopyJump: false,
        maxBoundsViscosity: 1.0, // Makes the bounds "hard" - can't drag outside them
        attributionControl: true,
        zoomControl: true
    });

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
            const geojsonPath = '/static/data/geographic/';
            const knownFiles = [
                'us.geojson', 
                'canada.geojson', 
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
                                        `Regulated Plants in ${stateName}${country ? `, ${country}` : ''}`;
                                    
                                    const table = document.getElementById('species-table');
                                    
                                    if ($.fn.DataTable.isDataTable(table)) {
                                        $(table).DataTable().destroy();
                                        $(table).empty();
                                        $(table).html('<thead><tr><th>Scientific Name</th><th>Common Name</th><th>Family</th><th>Federal</th></tr></thead>');
                                    }
                        
                                    $(table).DataTable({
                                        data: weeds,
                                        columns: [
                                            { 
                                                data: 'canonical_name',
                                                title: 'Scientific Name',
                                                width: '25%',
                                                render: function(data, type, row) {
                                                    if (type === 'display' && data) {
                                                        return `<a href="/species?name=${encodeURIComponent(data)}" class="species-link" target="_blank"><em>${data || 'Unknown'}</em></a>`;
                                                    }
                                                    return data || 'Unknown';
                                                }
                                            },
                                            { 
                                                data: 'common_name',
                                                title: 'Common Name',
                                                width: '45%',
                                                render: function(data, type, row) {
                                                    // Handle "No English common names available" message
                                                    if (!data || data.includes('No English common names available')) {
                                                        return `(${row.canonical_name || 'Unknown'})`;
                                                    }
                                                    return data;
                                                }
                                            },
                                            { 
                                                data: 'family_name',
                                                title: 'Family',
                                                width: '20%',
                                                render: function(data) {
                                                    return data || 'Unknown';
                                                }
                                            },
                                            { 
                                                data: 'has_federal_regulation',
                                                title: 'Federal Reg.',
                                                width: '10%',
                                                className: 'text-center',
                                                render: function(data, type, row) {
                                                    if (type === 'display') {
                                                        return data ? '<span style="color: #28a745; font-size: 1.1em;">✓</span>' : '<span style="color: #dc3545; font-size: 1.1em;">✗</span>';
                                                    }
                                                    return data ? 'Yes' : 'No';
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
                                            
                                            // Add PDF download button
                                            addPDFDownloadButton(stateName, country, weeds);
                                            
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
                                Regulated Plants: ${weedCount}
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
                
                // Use a specific bounds that focuses just on the three countries we care about
                const northAmericaAndAustraliaBounds = [
                    [-45, -170],  // Southwest corner - includes Australia and North America
                    [70, 155]     // Northeast corner - includes Australia and North America
                ];
                
                // Set the view to our specific bounds
                map.fitBounds(northAmericaAndAustraliaBounds, {
                    padding: [20, 20],
                    maxZoom: 3
                });
                
                // Restrict the map to show our target areas only once (no wrapping)
                map.setMaxBounds([
                    [-90, -190],  // Southwest corner - slightly beyond our data
                    [90, 190]     // Northeast corner - slightly beyond our data
                ]);
                
                // Turn off world wrapping to prevent duplicate continents
                map.options.worldCopyJump = false;
                
                // Center the view slightly to better frame the continents
                setTimeout(() => {
                    console.log("Adjusting map view...");
                    
                    // Check device width to provide better mobile experience
                    const isMobile = window.innerWidth < 768;
                    const isTablet = window.innerWidth >= 768 && window.innerWidth < 1024;
                    
                    if (isMobile) {
                        // For mobile, focus on the Americas while keeping a reasonable zoom level
                        console.log("Mobile device detected - using Americas-centered view");
                        
                        // Center on the Americas
                        map.setView([30, -100], 1);
                        
                    } else if (isTablet) {
                        // Tablet-specific view
                        console.log("Tablet device detected - using tablet-specific view");
                        map.setView([20, 0], 2);
                    } else {
                        // Desktop - adjust view to show both continents
                        console.log("Desktop detected - adjusting desktop view");
                        map.setView([20, -60], 2.2); // Specific zoom level that works well for this data
                    }
                }, 200);
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

    /******************************
     * PDF DOWNLOAD FUNCTIONALITY
     ******************************/
    function addPDFDownloadButton(stateName, country, weedsData) {
        // Remove existing PDF button if present
        const existingButton = document.getElementById('pdf-download-btn');
        if (existingButton) {
            existingButton.remove();
        }

        // Create PDF download button
        const pdfButton = document.createElement('button');
        pdfButton.id = 'pdf-download-btn';
        pdfButton.className = 'btn btn-primary btn-sm';
        pdfButton.innerHTML = '<i class="fas fa-download"></i> Download PDF';
        pdfButton.style.height = 'fit-content';
        pdfButton.style.alignSelf = 'center';
        
        pdfButton.onclick = function() {
            generatePDF(stateName, country, weedsData);
        };

        // Place button under the table pagination, right-aligned (no card)
        const tableContainer = document.querySelector('.table-responsive');
        if (tableContainer) {
            // Create a simple container for the download button, aligned with pagination
            const buttonContainer = document.createElement('div');
            buttonContainer.className = 'd-flex justify-content-end mt-2';
            buttonContainer.appendChild(pdfButton);
            
            // Insert button container after the table container
            tableContainer.parentNode.insertBefore(buttonContainer, tableContainer.nextSibling);
        }
    }

    function generatePDF(stateName, country, weedsData) {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        
        // Document title
        const title = `Regulated Plants in ${stateName}${country ? `, ${country}` : ''}`;
        
        // Load and add logos
        Promise.all([
            loadImageAsBase64('/static/img/UCD-plant-science-logo.png'),
            loadImageAsBase64('/static/img/UNU-INWEH_LOGO_NV.svg')
        ]).then(([ucdLogo, unuLogo]) => {
            // Add UC Davis logo (left side, above title) - wider but shorter
            if (ucdLogo) {
                // UC Davis logo: 80 width but much shorter height
                const ucdWidth = 80;
                const ucdHeight = 12;
                doc.addImage(ucdLogo, 'PNG', 20, 15, ucdWidth, ucdHeight);
            }
            
            // Add UNU logo (right side, above title) - make shorter and less wide 
            if (unuLogo) {
                // UNU logo: make narrower and shorter
                const unuHeight = 12;
                const unuWidth = 35;
                doc.addImage(unuLogo, 'SVG', 155, 15, unuWidth, unuHeight);
            }
            
            // Add title below logos - aligned with table left margin
            doc.setFontSize(16);
            doc.setFont(undefined, 'bold');
            doc.text(title, 20, 35);
            
            // Prepare table data with common name fallback
            const tableData = weedsData.map(row => {
                let commonName = row.common_name;
                // Handle "No English common names available" message
                if (!commonName || commonName.includes('No English common names available')) {
                    commonName = `(${row.canonical_name || 'Unknown'})`;
                }
                return [
                    row.canonical_name || 'Unknown',
                    commonName,
                    row.family_name || 'Unknown',
                    row.has_federal_regulation ? 'Yes' : 'No'
                ];
            });
            
            // Add table with clean styling - narrower to align with logos
            doc.autoTable({
                startY: 40,
                margin: { left: 20, right: 20 }, // Align with logo positions
                head: [['Scientific Name', 'Common Name', 'Family', 'Federal']],
                body: tableData,
                styles: {
                    fontSize: 9,
                    cellPadding: 3,
                    lineColor: [200, 200, 200],
                    lineWidth: 0.1
                },
                headStyles: {
                    fillColor: [255, 255, 255],
                    textColor: [0, 0, 0],
                    fontStyle: 'bold',
                    lineColor: [200, 200, 200],
                    lineWidth: 0.5
                },
                bodyStyles: {
                    fillColor: [255, 255, 255],
                    textColor: [0, 0, 0]
                },
                columnStyles: {
                    0: { fontStyle: 'italic' }, // Scientific names in italics
                    3: { halign: 'center' }     // Center federal column
                },
                alternateRowStyles: {
                    fillColor: [255, 255, 255] // Remove alternating row colors
                }
            });
            
            // Add footer with date and attribution
            const currentDate = new Date().toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
            
            const footerY = doc.internal.pageSize.height - 20;
            doc.setFontSize(10);
            doc.setFont(undefined, 'normal');
            doc.text(`Provided by Regulated Plants Database, data is correct as of ${currentDate}`, 20, footerY);
            
            // Download the PDF
            const filename = `Regulated_Plants_${stateName.replace(/[^a-z0-9]/gi, '_')}_${new Date().toISOString().split('T')[0]}.pdf`;
            doc.save(filename);
            
        }).catch(error => {
            console.error('Error loading logos:', error);
            
            // Generate PDF without logos if loading fails
            const tableData = weedsData.map(row => {
                let commonName = row.common_name;
                // Handle "No English common names available" message
                if (!commonName || commonName.includes('No English common names available')) {
                    commonName = `(${row.canonical_name || 'Unknown'})`;
                }
                return [
                    row.canonical_name || 'Unknown',
                    commonName,
                    row.family_name || 'Unknown',
                    row.has_federal_regulation ? 'Yes' : 'No'
                ];
            });
            
            doc.autoTable({
                startY: 50,
                head: [['Scientific Name', 'Common Name', 'Family', 'Federal']],
                body: tableData,
                styles: {
                    fontSize: 9,
                    cellPadding: 3,
                    lineColor: [200, 200, 200],
                    lineWidth: 0.1
                },
                headStyles: {
                    fillColor: [255, 255, 255],
                    textColor: [0, 0, 0],
                    fontStyle: 'bold',
                    lineColor: [200, 200, 200],
                    lineWidth: 0.5
                },
                bodyStyles: {
                    fillColor: [255, 255, 255],
                    textColor: [0, 0, 0]
                },
                columnStyles: {
                    0: { fontStyle: 'italic' },
                    3: { halign: 'center' }
                },
                alternateRowStyles: {
                    fillColor: [255, 255, 255] // Remove alternating row colors
                }
            });
            
            const currentDate = new Date().toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
            
            const footerY = doc.internal.pageSize.height - 20;
            doc.setFontSize(10);
            doc.text(`Provided by Regulated Plants Database, data is correct as of ${currentDate}`, 20, footerY);
            
            const filename = `Regulated_Plants_${stateName.replace(/[^a-z0-9]/gi, '_')}_${new Date().toISOString().split('T')[0]}.pdf`;
            doc.save(filename);
        });
    }

    function loadImageAsBase64(url) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            img.onload = function() {
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                canvas.width = img.width;
                canvas.height = img.height;
                ctx.drawImage(img, 0, 0);
                
                try {
                    const dataURL = canvas.toDataURL('image/png');
                    resolve(dataURL);
                } catch (error) {
                    console.error('Error converting image to base64:', error);
                    resolve(null);
                }
            };
            img.onerror = function() {
                console.error('Error loading image:', url);
                resolve(null);
            };
            img.src = url;
        });
    }
});