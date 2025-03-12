# HTR Evaluation System

A system for evaluating and visualizing the accuracy of HTR (Handwritten Text Recognition) JSON outputs compared to gold standard legal documents. It was developed specifically for cases when legal documents can be categorized according to types that follow the same structure, which can be defined and extracted using vision-enhanced LLMs.

## System Requirements

- Python 3.6+
- Node.js 14+ and npm 6+ (for dashboard visualization)
- Internet connection (for npm package installation)

## Installation

### 1. Set Up Python Environment

First, make sure Python 3.6+ is installed:
```bash
python --version
# or
python3 --version
```

Clone this repository (or download and extract the ZIP file):
```bash
git clone https://github.com/username/htr-evaluation-system.git
cd htr-evaluation-system
```

Create and activate a virtual environment:

**Linux/macOS**:
```bash
python -m venv htr_llm_env
source htr_llm_env/bin/activate
```

**Windows**:
```bash
python -m venv htr_llm_env
htr_llm_env\Scripts\activate
```

### 2. Install Required Python Packages

```bash
# Core requirements
pip install -U pip
pip install json re argparse typing
```

### 3. Install Node.js and npm

The dashboard requires Node.js and npm. Install them if you don't have them already:

**Option 1**: Download and install from [nodejs.org](https://nodejs.org/)

**Option 2**: Using package managers:

**Linux** (Ubuntu/Debian):
```bash
sudo apt update
sudo apt install nodejs npm
```

**macOS** (with Homebrew):
```bash
brew install node
```

Verify the installation:
```bash
node --version
npm --version
```

### 4. Test the Installation

Run a simple test to ensure everything is set up correctly:
```bash
python -c "import json, re, argparse, os; print('All required packages are installed!')"
```

## Usage

### Basic Usage

```bash
python htr_evaluation.py exemple_data/mock-gold-json.json exemple_data/mock-llm-json.json
```

This will:
1. Evaluate the predicted JSON against the gold standard
2. Generate a dashboard in the default output directory (`./output/`)
3. Launch the dashboard viewer automatically

### Options

```bash
python htr_evaluation.py exemple_data/mock-gold-json.json exemple_data/mock-llm-json.json --output_dir /custom/path
```

- `--output_dir`: Custom directory to save evaluation results (default: ./output/)

## Features

### Evaluation Process

The system:
1. Flattens nested JSON structures for comparison
2. Normalizes field names by replacing spaces with underscores
3. Applies field-specific normalization:
   - Phone numbers: Removes non-digit characters
   - Numeric fields: Extracts digits
   - Dates: Extracts numeric components
4. Computes string similarity using Levenshtein distance
5. Weights fields based on importance (adjustable for each specific evaluation campaign)
6. Categorizes errors into four types

### Error Categories

- **Critical Error (0%)**: Completely incorrect or missing values
- **Semantic Difference (50%)**: Similar meaning but significant differences
- **Minor Error (80%)**: Small differences
- **Perfect Match (100%)**: Exact match after normalization

### Dashboard Features

- Overall evaluation score
- Field coverage percentage
- Error distribution visualization
- Detailed table of all errors

## How It Works

After running the evaluation, the script will:
1. Generate the dashboard files
2. Install npm dependencies
3. Start the Parcel development server
4. Display access instructions

Open your browser and navigate to http://localhost:1234 to view the dashboard.

## Customization

You can modify:
- Similarity thresholds in `categorize_error()`
- Field weights in `get_field_weight()`
- Field normalization in `normalize_field()`

## Troubleshooting

### Common Issues

**Problem**: `ModuleNotFoundError: No module named 'xyz'`  
**Solution**: Install the missing package: `pip install xyz`

**Problem**: Dashboard doesn't launch  
**Solution**: 
1. Make sure Node.js and npm are installed correctly
2. Manually navigate to the dashboard directory and run:
```bash
cd output/[file_name]_dashboard
npm install
npm start
```
3. Open your browser to http://localhost:1234

## Legal

This code is distributed under the CC BY-NC-SA 4.0 license, developed by Mikhail Biriuchinskii, NLP Engineer at [ObTIC](https://obtic.sorbonne-universite.fr/), Sorbonne University.
