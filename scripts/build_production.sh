#!/bin/bash

set -e

echo "🚀 Building Frontend for Production"
echo "===================================="

# Navigate to frontend directory
cd "$(dirname "$0")/../frontend"

echo "📦 Installing dependencies..."
npm ci --production=false

echo "🔍 Running TypeScript checks..."
npx astro check

echo "🏗️  Building Astro project..."
npm run build

echo "📊 Build statistics..."
if [ -d "dist" ]; then
    echo "Output directory: dist/"
    du -sh dist/
    echo ""
    echo "Files created:"
    find dist -type f | wc -l
    echo ""
    echo "Largest files:"
    find dist -type f -exec du -h {} + | sort -rh | head -10
fi

echo ""
echo "✅ Production build complete!"
echo ""
echo "To serve the production build:"
echo "  cd frontend && npm run preview"
echo ""
echo "Or deploy the dist/ directory to your hosting provider"
