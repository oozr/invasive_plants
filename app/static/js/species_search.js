document.addEventListener('DOMContentLoaded', function() {
    // Function to get URL parameters
    function getUrlParameter(name) {
        name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
        var regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
        var results = regex.exec(location.search);
        return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
    }
    
    // Initialize Select2
    $('#weedSearch').select2({
        placeholder: 'Start typing a common or scientific name...',
        minimumInputLength: 2,
        ajax: {
            url: '/species/api/search',
            dataType: 'json',
            delay: 250,
            data: function(params) {
                return {
                    q: params.term
                };
            },
            processResults: function(data) {
                return {
                    results: data.map(weed => {
                        // Handle "No English common names available" message
                        let displayCommonName = weed.common_name;
                        if (!displayCommonName || displayCommonName.includes('No English common names available')) {
                            displayCommonName = null;
                        }
                        
                        return {
                            id: weed.usage_key,
                            // Format the text to show both names
                            text: displayCommonName ? 
                                  `${displayCommonName} (${weed.canonical_name})` : 
                                  `(${weed.canonical_name})`,
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
        // Customize the dropdown appearance
        templateResult: function(weed) {
            if (!weed.id) return weed.text; // Return unchanged if it's the placeholder
            
            // Handle cases where common_name might be missing or has the long message
            let commonName = weed.common_name || '';
            if (commonName.includes('No English common names available')) {
                commonName = '';
            }
            const canonicalName = weed.canonical_name || '';
            
            return $(`
                <div>
                    ${commonName ? `<div class="common-name">${commonName}</div>` : ''}
                    <div class="canonical-name ${commonName ? 'text-muted small' : ''}">${commonName ? canonicalName : `(${canonicalName})`}</div>
                </div>
            `);
        }
    });

    // Handle selection in dropdown
    $('#weedSearch').on('select2:select', function(e) {
        const selectedWeed = e.params.data;
        displayWeedDetails(selectedWeed);
    });
    
    // Function to display weed details and fetch states
    function displayWeedDetails(selectedWeed) {
        // Display common name - truncate if needed, or show "Not available" if empty
        const commonName = selectedWeed.common_name || '';
        const commonNameParts = commonName.split(',');
        const truncatedCommonName = commonNameParts.length > 3 
            ? commonNameParts.slice(0, 3).join(', ')
            : commonName;
        
        // Handle the specific "No English common names available" message
        let displayName = truncatedCommonName;
        if (!displayName || displayName.includes('No English common names available')) {
            displayName = `(${selectedWeed.canonical_name || 'Unknown'})`;
        }
        document.getElementById('weedTitle').textContent = displayName;
        document.getElementById('weedCanonicalName').textContent = selectedWeed.canonical_name;
        document.getElementById('weedFamily').textContent = selectedWeed.family_name || 'Not available';
        
        // Handle synonyms display - limit to first 3
        const synonymsSection = document.getElementById('synonymsSection');
        const weedSynonyms = document.getElementById('weedSynonyms');
        
        if (selectedWeed.synonyms && selectedWeed.synonyms.trim() !== '') {
            // Split by commas, take first 3, join with commas
            const allSynonyms = selectedWeed.synonyms.split(',');
            const truncatedSynonyms = allSynonyms.length > 3 
                ? allSynonyms.slice(0, 3).join(', ') 
                : selectedWeed.synonyms;
                
            weedSynonyms.textContent = truncatedSynonyms;
            synonymsSection.classList.remove('d-none');
        } else {
            synonymsSection.classList.add('d-none');
        }
        
        const gbifLink = document.getElementById('gbifLink');
        gbifLink.href = `https://www.gbif.org/species/${selectedWeed.usage_key}`;
        
        // Use the usage_key instead of common_name for more accurate results
        fetch(`/species/api/weed-states/by-key/${selectedWeed.usage_key}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(regulationsByCountry => {
                const statesList = document.getElementById('statesList');
                statesList.innerHTML = '';
                
                if (Object.keys(regulationsByCountry).length === 0) {
                    statesList.innerHTML = `
                        <div class="list-group-item">
                            <p class="mb-1">No regulations found for this species.</p>
                        </div>
                    `;
                } else {
                    // For each country, display the regulations
                    for (const [country, states] of Object.entries(regulationsByCountry)) {
                        // Create a card for each country
                        let countryElement = document.createElement('div');
                        countryElement.className = 'list-group-item';
                        
                        // Create country header
                        let countryHeader = document.createElement('h5');
                        countryHeader.className = 'mb-2';
                        countryHeader.textContent = country;
                        countryElement.appendChild(countryHeader);
                        
                        // Add states info
                        if (states.length === 1 && states[0] === "Federal Level") {
                            // If federally regulated, display a special message
                            let federalInfo = document.createElement('p');
                            federalInfo.className = 'mb-0 text-primary';
                            federalInfo.textContent = 'Regulated at the Federal Level';
                            countryElement.appendChild(federalInfo);
                        } else {
                            // Create a paragraph to hold all states as a row
                            let statesRow = document.createElement('p');
                            statesRow.className = 'mb-0';
                            statesRow.textContent = states.join(', ');
                            countryElement.appendChild(statesRow);
                        }
                        
                        statesList.appendChild(countryElement);
                    }
                }
                
                document.getElementById('results').classList.remove('d-none');
            })
            .catch(error => {
                console.error('Error fetching weed states:', error);
                const statesList = document.getElementById('statesList');
                statesList.innerHTML = `
                    <div class="list-group-item text-danger">
                        <p class="mb-1">Error loading data. Please try again.</p>
                    </div>
                `;
                document.getElementById('results').classList.remove('d-none');
            });
    }
    
    // Clear results when dropdown is cleared
    $('#weedSearch').on('select2:clear', function() {
        document.getElementById('results').classList.add('d-none');
    });
    
    // Check if we have a plant name in the URL parameter
    const plantName = getUrlParameter('name');
    if (plantName) {
        // Fetch the plant data by name to get all required details
        fetch(`/species/api/search?q=${encodeURIComponent(plantName)}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(results => {
                // Find the exact match or the first close match
                const exactMatch = results.find(weed => 
                    weed.canonical_name.toLowerCase() === plantName.toLowerCase()
                );
                
                const weedData = exactMatch || results[0];
                
                if (weedData) {
                    // Format the data as needed for Select2
                    let displayCommonName = weedData.common_name;
                    if (!displayCommonName || displayCommonName.includes('No English common names available')) {
                        displayCommonName = null;
                    }
                    
                    const formattedData = {
                        id: weedData.usage_key,
                        text: displayCommonName ? 
                              `${displayCommonName} (${weedData.canonical_name})` : 
                              `(${weedData.canonical_name})`,
                        common_name: displayCommonName || weedData.canonical_name,
                        canonical_name: weedData.canonical_name,
                        family_name: weedData.family_name,
                        synonyms: weedData.synonyms,
                        usage_key: weedData.usage_key
                    };
                    
                    // Create the option and add it to Select2
                    const newOption = new Option(formattedData.text, formattedData.id, true, true);
                    $('#weedSearch').append(newOption).trigger('change');
                    
                    // Display the weed details
                    displayWeedDetails(formattedData);
                }
            })
            .catch(error => {
                console.error('Error fetching plant data:', error);
            });
    }
});