#!/usr/bin/env bash
# build.sh — run this during deployment to prepare the app
# Order matters: frontend must build before collectstatic
set -e

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Building frontend..."
cd frontend
npm install
npm run build
cd ..

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running migrations..."
python manage.py migrate

echo "Running tests..."
python manage.py test --no-input

echo "Build complete."
