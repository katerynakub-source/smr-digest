// Turns the exported web build into an installable "Add to Home Screen" app:
// adds a web manifest, iOS home-screen tags and an SPA fallback for GitHub Pages.
// Usage: node scripts/pwa.mjs <dist-dir> <base-url, e.g. /smr-digest>
import { copyFileSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const [dist = 'dist', base = ''] = process.argv.slice(2);
const b = base.replace(/\/+$/, '');

copyFileSync(new URL('../assets/icon.png', import.meta.url), join(dist, 'icon.png'));

writeFileSync(join(dist, 'manifest.json'), JSON.stringify({
  name: 'SMR Digest',
  short_name: 'SMR Digest',
  description: 'Nuclear energy and small modular reactor news',
  start_url: `${b}/`,
  scope: `${b}/`,
  display: 'standalone',
  background_color: '#FBFAF7',
  theme_color: '#FBFAF7',
  icons: [{ src: `${b}/icon.png`, sizes: '1024x1024', type: 'image/png', purpose: 'any' }],
}, null, 2));

const tags = `
    <link rel="manifest" href="${b}/manifest.json" />
    <link rel="apple-touch-icon" href="${b}/icon.png" />
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-title" content="SMR Digest" />
    <meta name="apple-mobile-web-app-status-bar-style" content="default" />
    <meta name="theme-color" content="#FBFAF7" />
`;
const indexPath = join(dist, 'index.html');
const html = readFileSync(indexPath, 'utf8').replace('</head>', `${tags}</head>`);
writeFileSync(indexPath, html);
// GitHub Pages serves 404.html for unknown paths → lets deep links like /article/12 open the app
writeFileSync(join(dist, '404.html'), html);
console.log('PWA files written to', dist);
