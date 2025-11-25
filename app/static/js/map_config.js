// static/js/map_config.js
window.MAP_CONFIG = window.MAP_CONFIG || {};

MAP_CONFIG.geojsonPath = "/static/data/geographic/";

// Global thresholds (used for every country)
MAP_CONFIG.defaultThresholds = [0, 100, 150, 200, 250, 300];

// Choropleth ramps for countries that DO have regulations
// (all ocean-safe: no strong blues)
MAP_CONFIG.defaultColorRamps = [
  // 0 = Reds
  ["#fff5f0","#fee0d2","#fcbba1","#fc9272","#fb6a4a","#de2d26","#a50f15"],
  // 1 = Greens
  ["#f7fcf5","#e5f5e0","#c7e9c0","#a1d99b","#74c476","#41ab5d","#005a32"],
  // 2 = Purples
  ["#fcfbfd","#efedf5","#dadaeb","#bcbddc","#9e9ac8","#756bb1","#54278f"],
  // 3 = Oranges
  ["#fff5eb","#fee6ce","#fdd0a2","#fdae6b","#fd8d3c","#f16913","#d94801"]
];

// Dark grey for regions with NO regulation at all (count === 0)
MAP_CONFIG.noDataColor = "#555555";

// Optional: force specific ramps for visually important neighbours
MAP_CONFIG.countryRampOverrides = {
  "United States": 0,  // Reds
  "Canada": 2,         // Purples
  "Australia": 1,      // Greens
  "New Zealand": 3     // Oranges
};
