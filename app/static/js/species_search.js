document.addEventListener('DOMContentLoaded', function() {
    // Initialize Select2
    $('#weedSearch').select2({
        placeholder: 'Start typing a weed name...',
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
                        id: weed.weed_name,
                        text: weed.weed_name,
                        category: weed.category
                    }))
                };
            },
            cache: true
        }
    });

    // Handle selection
    $('#weedSearch').on('select2:select', function(e) {
        const selectedWeed = e.params.data;
        
        // Update the results section
        document.getElementById('weedTitle').textContent = selectedWeed.text;
        document.getElementById('weedCategory').textContent = selectedWeed.category;
        
        // Fetch states where this weed is regulated
        fetch(`/species/api/weed-states/${encodeURIComponent(selectedWeed.text)}`)
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
                
                // Show results
                document.getElementById('results').classList.remove('d-none');
            });
    });
});