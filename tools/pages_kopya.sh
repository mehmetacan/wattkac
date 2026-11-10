#!/usr/bin/env bash
# GitHub Pages yedek kopyasını (docs/kampanyalar/) site/ ile eşitler.
# Elle çalıştırmaya gerek yok: .github/workflows/pages-kopya.yml her site/veri değişikliğinde çalıştırır.
# Panel (panel.html) /api gerektirdiği için kopyalanmaz; SEO sayfaları yalnızca Cloudflare yayınında üretilir.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf docs/kampanyalar
mkdir -p docs/kampanyalar
cp -r site/. docs/kampanyalar/
( cd docs/kampanyalar && rm -rf panel.html README.md .assetsignore kampanyalar sarj-agi sitemap.xml robots.txt )
cp data/kampanyalar.json docs/kampanyalar/kampanyalar.json
