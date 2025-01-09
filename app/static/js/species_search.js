document.addEventListener('DOMContentLoaded', function() {
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
                        id: weed.common_name,  // Keeping common_name as ID for compatibility
                        // Format the text to show both names
                        text: `${weed.common_name} (${weed.canonical_name})`,
                        common_name: weed.common_name,
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
            
            return $(`
                <div>
                    <div class="common-name">${weed.common_name}</div>
                    <div class="canonical-name text-muted small">${weed.canonical_name}</div>
                </div>
            `);
        }
    });

    $('#weedSearch').on('select2:select', function(e) {
        const selectedWeed = e.params.data;
        
        document.getElementById('weedTitle').textContent = selectedWeed.common_name;
        document.getElementById('weedCanonicalName').textContent = selectedWeed.canonical_name;
        document.getElementById('weedFamily').textContent = selectedWeed.family_name;
        
        const gbifLink = document.getElementById('gbifLink');
        gbifLink.href = `https://www.gbif.org/species/${selectedWeed.usage_key}`;
        
        fetch(`/species/api/weed-states/${encodeURIComponent(selectedWeed.common_name)}`)
            .then(response => response.json())
            .then(states => {
                const statesList = document.getElementById('statesList');
                statesList.innerHTML = '';
                
                states.forEach(state => {
                    statesList.innerHTML += `
                        <div class="list-group-item">
                            <h5 class="mb-1">${state}</h5>
                        </div>
                    `;
                });
                
                document.getElementById('results').classList.remove('d-none');
            });
    });
});