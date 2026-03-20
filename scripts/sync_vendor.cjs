const fs = require('node:fs');
const path = require('node:path');

const rootDir = path.resolve(__dirname, '..');
const vendorDir = path.join(rootDir, 'vendor');

const files = [
  ['chart.js/dist/chart.umd.js', 'chart.umd.js'],
  ['chart.js/dist/chart.umd.js.map', 'chart.umd.js.map'],
  ['chartjs-plugin-datalabels/dist/chartjs-plugin-datalabels.min.js', 'chartjs-plugin-datalabels.min.js'],
  ['leaflet/dist/leaflet.css', 'leaflet.css'],
  ['leaflet/dist/leaflet.js', 'leaflet.js'],
  ['leaflet/dist/leaflet.js.map', 'leaflet.js.map'],
];

fs.mkdirSync(vendorDir, { recursive: true });

for (const [source, target] of files) {
  const sourcePath = path.join(rootDir, 'node_modules', source);
  const targetPath = path.join(vendorDir, target);
  fs.copyFileSync(sourcePath, targetPath);
  console.log(`copied ${source} -> vendor/${target}`);
}
