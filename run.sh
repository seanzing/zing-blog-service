#!/bin/bash

# Zing Blog Generation Service - Quick Start Script

echo "🚀 Starting Zing Blog Generation Service..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo ""
    echo "❗ IMPORTANT: Please edit .env and add your API keys before running the service!"
    echo ""
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
    echo ""
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Run the service
echo "🌐 Starting FastAPI service..."
echo "   Web UI: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
python -m app.main
