#!/bin/bash
# One-command evaluation runner script for MediFlow

echo "=================================================="
# Set environment to dev/test database
export DB_ENV="test"

# Run report.py which resets database and runs all 20 scenarios
./backend/.venv/Scripts/python eval/report.py

echo "=================================================="
echo "Evaluation run complete."
