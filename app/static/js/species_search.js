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
                    results: data.map(weed => ({
                        id: weed.usage_key,  // Changed to usage_key for better data handling
                        // Format the text to show both names
                        text: weed.common_name ? 
                              `${weed.common_name} (${weed.canonical_name})` : 
                              weed.canonical_name,
                        common_name: weed.common_name || weed.canonical_name,
                        canonical_name: weed.canonical_name,
                        family_name: weed.family_name,
                        usage_key: weed.usage_key
                    }))
                };
            },
            cache: true
        },
        // Customize the dropdown appearance
        templateResult: function(weed) {
            if (!weed.id) return weed.text; // Return unchanged if it's the placeholder
            
            // Handle cases where common_name might be missing
            const commonName = weed.common_name || '';
            const canonicalName = weed.canonical_name || '';
            
            return $(`
                <div>
                    ${commonName ? `<div class="common-name">${commonName}</div>` : ''}
                    <div class="canonical-name ${commonName ? 'text-muted small' : ''}">${canonicalName}</div>
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
        document.getElementById('weedTitle').textContent = selectedWeed.common_name;
        document.getElementById('weedCanonicalName').textContent = selectedWeed.canonical_name;
        document.getElementById('weedFamily').textContent = selectedWeed.family_name || 'Not available';
        
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
            .then(states => {
                const statesList = document.getElementById('statesList');
                statesList.innerHTML = '';
                
                if (states.length === 0) {
                    statesList.innerHTML = `
                        <div class="list-group-item">
                            <p class="mb-1">No regulations found for this species.</p>
                        </div>
                    `;
                } else {
                    states.forEach(state => {
                        statesList.innerHTML += `
                            <div class="list-group-item">
                                <h5 class="mb-1">${state}</h5>
                            </div>
                        `;
                    });
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
                    const formattedData = {
                        id: weedData.usage_key,
                        text: weedData.common_name ? 
                              `${weedData.common_name} (${weedData.canonical_name})` : 
                              weedData.canonical_name,
                        common_name: weedData.common_name || weedData.canonical_name,
                        canonical_name: weedData.canonical_name,
                        family_name: weedData.family_name,
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