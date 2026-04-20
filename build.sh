#!/usr/bin/env bash
# build.sh — run this during deployment to prepare the app
# Order matters: frontend must build before collectstatic
set -e

echo "Building frontend..."
cd frontend
npm install
npm run build
cd ..

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running migrations..."
python manage.py migrate

echo "Build complete."
