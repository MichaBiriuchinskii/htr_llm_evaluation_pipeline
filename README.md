# HTR Evaluation System - Setup and Usage Guide

This system evaluates and visualizes the accuracy of HTR (Handwritten Text Recognition) JSON outputs compared to gold standard documents. It includes a Python evaluation script and a React dashboard for visualizing results.

## System Requirements

- Python 3.6+
- Node.js and npm (for the dashboard)
- Required Python packages: `json`, `difflib`, `numpy`, `pandas`

## Installation

1. Save the Python script to a file named `htr_evaluation.py`

2. Install required Python packages:
```bash
pip install numpy pandas
```

3. For the dashboard visualization, you'll need Node.js and npm:
- Download and install from [nodejs.org](https://nodejs.org/)

## Usage

### Basic Evaluation

Run the evaluation script with your gold standard and predicted JSON files:

```bash
python htr_evaluation.py path/to/gold_standard.json path/to/predicted.json
```

This will:
1. Evaluate the predicted document against the gold standard
2. Print a summary of the evaluation results
3. Save detailed results to `evaluation_results.json`
4. Generate dashboard files in a `dashboard` directory

### Command Line Options

```
python htr_evaluation.py gold_file.json predicted_file.json [options]

Options:
  --output OUTPUT    Path to save evaluation results (default: evaluation_results.json)
  --dashboard DIR    Directory to save dashboard files (default: dashboard)
  --serve            Start a simple HTTP server to view the dashboard
```

### Viewing the Dashboard

#### Option 1: Using the built-in server

Run with the `--serve` option to automatically launch a simple HTTP server:

```bash
python htr_evaluation.py gold_file.json predicted_file.json --serve
```

This will:
1. Generate the dashboard files
2. Start a local HTTP server on port 8000
3. Open your default browser to view the dashboard

#### Option 2: Manual setup (for customization)

1. Generate the dashboard files:
```bash
python htr_evaluation.py gold_file.json predicted_file.json
```

2. Navigate to the dashboard directory:
```bash
cd dashboard
```

3. Install dependencies:
```bash
npm install
```

4. Start the development server:
```bash
npm start
```

5. Open your browser to view the dashboard (typically at http://localhost:1234)

## Dashboard Features

The dashboard provides:

- Overall evaluation score
- Field coverage percentage
- Error distribution visualization
- Detailed examples of errors categorized by type:
  - Critical errors (completely incorrect)
  - Semantic differences (different wording, same meaning)
  - Minor errors (small formatting differences)
  - Perfect matches

## Evaluation Methodology

The system uses a weighted scoring approach that:

1. Flattens nested JSON structures for comparison
2. Applies field-specific normalization (phone numbers, dates, etc.)
3. Computes string similarity using Levenshtein distance
4. Categorizes errors based on similarity thresholds
5. Weights fields by importance (names, IDs, etc. have higher weights)
6. Calculates final score as weighted average

### Error Categories

- **Critical Error (0%)**: Completely incorrect or missing values
- **Semantic Difference (50%)**: Different representation but similar meaning
- **Minor Error (80%)**: Small formatting differences
- **Perfect Match (100%)**: Exact match after normalization

## Example

Evaluating `gold_CFDT.json` against `Claude_CFDT.json`:

```bash
python htr_evaluation.py gold_CFDT.json Claude_CFDT.json --serve
```

The dashboard will show metrics like:
- Overall accuracy score
- Field coverage
- Distribution of error types
- Examples of the most significant errors

## Customization

You can modify the script to:
- Adjust similarity thresholds in `categorize_error()`
- Change field weights in `get_field_weight()`
- Add custom normalization rules in `normalize_field()`
- Modify the dashboard design in the `Dashboard.js` file

## Troubleshooting

**Problem**: Dashboard doesn't render properly
**Solution**: Make sure you have all dependencies installed with `npm install`

**Problem**: Script fails to parse JSON files
**Solution**: Verify that your JSON files are properly formatted

**Problem**: Error running the HTTP server
**Solution**: Make sure port 8000 is available, or modify the `PORT` variable in the script
