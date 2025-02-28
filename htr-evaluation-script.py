import json
import os
import argparse
import re
from typing import Dict, Tuple, Any, List, Optional
import webbrowser
import shutil
import subprocess
import time
from datetime import datetime

def flatten_json(obj: Dict, prefix: str = '') -> Dict:
    """
    Flatten a nested JSON object into a single-level dictionary.
    # nested_json = {"person": {"name": "John", "address": {"city": "Paris"}}}
    # flattened = flatten_json(nested_json)
    # Result: {"person.name": "John", "person.address.city": "Paris"}
    """
    result = {}
    for key, value in obj.items():
        new_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(flatten_json(value, new_key))
        else:
            result[new_key] = value
    return result

def normalize_value(value: Any) -> str:
    """
    Normalize values for comparison.
    # Input: " John Doe  " or 123 or None
    # Output: "John Doe" or "123" or ""
    """
    if value is None:
        return ""
    return str(value).strip()

def compute_string_similarity(str1: str, str2: str) -> float:
    """
    Compute string similarity using Levenshtein distance.
    
    This is particularly well-suited for HTR evaluation because it:
    1. Directly measures edit operations that correspond to recognition errors
    2. Handles different string lengths naturally
    3. Is more intuitive for text recognition metrics
    
    Returns a similarity ratio from 0.0 (completely different) to 1.0 (identical)
    """
    if not str1 and not str2:
        return 1.0 # perfect match
    if not str1 or not str2:
        return 0.0  #  no match
    
    str1 = normalize_value(str1)
    str2 = normalize_value(str2)
    
    # Calculate Levenshtein distance
    def levenshtein_distance(s1, s2):
        if len(s1) < len(s2):
            return levenshtein_distance(s2, s1)
        
        # len(s1) >= len(s2)
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    #converting to similarity ratio
    distance = levenshtein_distance(str1, str2)
    max_len = max(len(str1), len(str2))
    if max_len == 0:
        return 1.0
    similarity = 1.0 - (distance / max_len)
    return similarity

def normalize_phone(phone_str: str) -> str:
    """Normalize phone numbers by removing non-numeric characters."""
    if not phone_str:
        return ""
    return re.sub(r'\D', '', phone_str)

def normalize_field(field: str, value: Any) -> str:
    """
    Apply field-specific normalization rules.
    # normalize_field("nbre_de_salariés", "2,125")
    # returns: "2125" (extracts only numbers)
    """
    value_str = normalize_value(value)
    # Phone number
    if any(phone_term in field.lower() for phone_term in ['tel', 'téléphone', 'phone']): # I included more types in case we'll use this doc in other document formats
        return normalize_phone(value_str)
    # Numeric field
    if any(num_term in field.lower() for num_term in ['nombre', 'nbre', 'count', 'montant', 'amount']):
        # Extract numbers from the string
        nums = re.findall(r'\d+', value_str)
        return ''.join(nums) if nums else value_str
    if 'date' in field.lower():
        # Simple date normalization - extract numbers
        return re.sub(r'\D', '', value_str)
    return value_str

def categorize_error(gold_value: Any, pred_value: Any, field: str) -> Tuple[str, float]:
    """Categorize the error type and assign a scores"""
    gold_norm = normalize_field(field, gold_value)
    pred_norm = normalize_field(field, pred_value)
    if gold_norm == pred_norm:
        return "perfect", 1.0
    # For normal fields using string similarity
    similarity = compute_string_similarity(str(gold_value), str(pred_value))
    if similarity >= 0.9:
        return "minor", 0.8
    elif similarity >= 0.5:
        return "semantic", 0.5
    else:
        return "critical", 0.0

def get_field_weight(field: str) -> float:
    """
    Assign importance weights to different fields.

    To discuss with clients to determine the most important fields.
    """
    if any(name_term in field.lower() for name_term in ['nom', 'name', 'id', 'matricule']):
        return 2.0
    if any(contact_term in field.lower() for contact_term in ['addresse', 'address', 'tel', 'email']):
        return 1.5
    if any(num_term in field.lower() for num_term in ['nombre', 'nbre', 'count', 'montant', 'amount']):
        return 1.5
    # Default weight
    return 1.0

def evaluate_documents(gold_path: str, pred_path: str, validations_path: Optional[str] = None) -> Dict:
    """
    Returns a dictionary with evaluation metrics.
    Optionally applies validations from a previous run if validations_path is provided.
    """
    with open(gold_path, 'r', encoding='utf-8') as f:
        gold_json = json.load(f)
    with open(pred_path, 'r', encoding='utf-8') as f:
        pred_json = json.load(f)

    flat_gold = flatten_json(gold_json)
    flat_pred = flatten_json(pred_json)
    
    # Filter out metadata fields
    filtered_gold = {k: v for k, v in flat_gold.items() if not k.startswith('metadata')}
    filtered_pred = {k: v for k, v in flat_pred.items() if not k.startswith('metadata')}

    # Load validations if provided
    validations = []
    if validations_path and os.path.exists(validations_path):
        try:
            with open(validations_path, 'r', encoding='utf-8') as f:
                validation_data = json.load(f)
                if 'validated_errors' in validation_data:
                    validations = validation_data['validated_errors']
                    print(f"Loaded {len(validations)} validations from {validations_path}")
        except Exception as e:
            print(f"Warning: Failed to load validations from {validations_path}: {e}")

    # Prepare results structure
    results = {
        "total_score": 0.0,
        "total_weight": 0.0,
        "field_scores": {},
        "missing_fields": [],
        "extra_fields": [],
        "error_categories": {
            "critical": 0,
            "semantic": 0,
            "minor": 0,
            "perfect": 0
        },
        "detailed_errors": [],
        "applied_validations": []
    }
    
    # Check for missing fields
    for field in filtered_gold:
        if field not in filtered_pred:
            results["missing_fields"].append(field)
            results["error_categories"]["critical"] += 1
            results["detailed_errors"].append({
                "field": field,
                "gold": filtered_gold[field],
                "pred": None,
                "type": "critical",
                "score": 0.0
            })
    
    # Check for extra fields
    for field in filtered_pred:
        if field not in filtered_gold:
            results["extra_fields"].append(field)
    
    # Compare common fields
    for field in filtered_gold:
        if field in filtered_pred:
            gold_value = filtered_gold[field]
            pred_value = filtered_pred[field]
            
            # Get field weight
            weight = get_field_weight(field)
            results["total_weight"] += weight
            
            # Check if this field is in the validations list
            is_validated = any(v['field'] == field for v in validations)
            
            if is_validated:
                # If validated, consider it perfect
                error_type, score = "perfect", 1.0
                results["applied_validations"].append({
                    "field": field,
                    "gold": gold_value,
                    "pred": pred_value
                })
            else:
                # Otherwise, categorize error and get score
                error_type, score = categorize_error(gold_value, pred_value, field)
            
            # Update results
            results["field_scores"][field] = {
                "gold": gold_value,
                "pred": pred_value,
                "score": score,
                "error_type": error_type,
                "weight": weight,
                "validated": is_validated
            }
            
            results["error_categories"][error_type] += 1
            results["total_score"] += weight * score
            
            # Add to detailed errors if not perfect
            if error_type != "perfect":
                results["detailed_errors"].append({
                    "field": field,
                    "gold": gold_value,
                    "pred": pred_value,
                    "type": error_type,
                    "score": score
                })
    
    # Calculate final score
    if results["total_weight"] > 0:
        results["final_score"] = results["total_score"] / results["total_weight"] * 100
    else:
        results["final_score"] = 0
    
    # Calculate error distribution percentages
    total_fields = sum(results["error_categories"].values())
    if total_fields > 0:
        for category in results["error_categories"]:
            results["error_categories"][category] = round(
                (results["error_categories"][category] / total_fields) * 100, 1
            )
    
    # Calculate field coverage
    if len(filtered_gold) > 0:
        results["field_coverage"] = round(
            (len(filtered_gold) - len(results["missing_fields"])) / len(filtered_gold) * 100, 1
        )
    else:
        results["field_coverage"] = 0
    
    # Sort detailed errors by score (ascending)
    results["detailed_errors"] = sorted(
        results["detailed_errors"], 
        key=lambda x: (x["score"], x["field"])
    )
    
    return results

def export_results_to_json(results: Dict, output_path: str) -> None:
    """Export evaluation results to JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Results exported to {output_path}")

def print_summary(results: Dict) -> None:
    """Print a summary of the evaluation results."""
    print("\n" + "="*50)
    print(f"HTR EVALUATION SUMMARY")
    print("="*50)
    print(f"Overall Score: {results['final_score']:.1f}%")
    print(f"Field Coverage: {results['field_coverage']:.1f}%")
    print("\nError Distribution:")
    print(f"- Perfect Matches: {results['error_categories']['perfect']}%")
    print(f"- Minor Errors: {results['error_categories']['minor']}%")
    print(f"- Semantic Differences: {results['error_categories']['semantic']}%")
    print(f"- Critical Errors: {results['error_categories']['critical']}%")
    
    print("\nMissing Fields: {len(results['missing_fields'])}")
    print("\nExtra Fields: {len(results['extra_fields'])}")
    
    # Print top 10 errors
    if results["detailed_errors"]:
        print("\nTop 10 Errors:")
        for i, error in enumerate(results["detailed_errors"][:10]):
            print(f"{i+1}. Field: {error['field']}")
            print(f"   Gold: {error['gold']}")
            print(f"   Pred: {error['pred']}")
            print(f"   Type: {error['type']}")
            print()
    
    print("="*50)

def generate_dashboard(results_path: str, output_dir: str) -> str:
    """
    Generate the enhanced React dashboard based on evaluation results.
    Returns the path to the HTML file.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Create necessary files for the React app
    # 1. Create package.json
    package_json = {
  "name": "htr-evaluation-dashboard",
  "version": "1.0.0",
  "description": "Dashboard for HTR evaluation results with validation",
  "main": "index.js",
  "scripts": {
    "server": "node server.js"
  },
  "dependencies": {
    "react": "^17.0.2",
    "react-dom": "^17.0.2",
    "express": "^4.17.1",
    "body-parser": "^1.19.0"
  }
}
    
    with open(os.path.join(output_dir, "package.json"), "w") as f:
        json.dump(package_json, f, indent=2)
    
    # 2. Create index.html
    index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HTR Evaluation Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <script src="https://unpkg.com/react@17/umd/react.development.js" crossorigin></script>
    <script src="https://unpkg.com/react-dom@17/umd/react-dom.development.js" crossorigin></script>
    <script src="https://unpkg.com/babel-standalone@6/babel.min.js"></script>
</head>
<body>
    <div id="root"></div>
    
    <!-- Include Dashboard component -->
    <script type="text/babel" src="Dashboard.js"></script>
    
    <!-- Main script to load data and render app -->
    <script type="text/babel">
        fetch('./results.json')
            .then(response => response.json())
            .then(results => {
                ReactDOM.render(
                    <Dashboard results={results} />,
                    document.getElementById('root')
                );
            })
            .catch(error => {
                console.error('Error loading results:', error);
                document.getElementById('root').innerHTML = 
                    '<div class="p-4 bg-red-100 text-red-700 rounded">' + 
                    '<h2 class="text-xl font-bold">Error Loading Data</h2>' + 
                    '<p>Failed to load results. Check the console for details.</p>' + 
                    '</div>';
            });
    </script>
</body>
</html>
"""
    
    with open(os.path.join(output_dir, "index.html"), "w") as f:
        f.write(index_html)
    
    # 3. Create index.js
    index_js = """import React from 'react';
import ReactDOM from 'react-dom';
import App from './App';

ReactDOM.render(<App />, document.getElementById('root'));
"""
    
    with open(os.path.join(output_dir, "index.js"), "w") as f:
        f.write(index_js)
    
    # 4. Create App.js with the dashboard component
    app_js = """import React from 'react';
import Dashboard from './Dashboard';
import results from './results.json';

const App = () => {
    return <Dashboard results={results} />;
};

export default App;
"""
    
    with open(os.path.join(output_dir, "App.js"), "w") as f:
        f.write(app_js)
    
    # 5. Copy results.json to the output directory
    shutil.copy(results_path, os.path.join(output_dir, "results.json"))
    
    # 6. Create the enhanced Dashboard.js component with validation features
    dashboard_js = """import React, { useState, useEffect } from 'react';

const Dashboard = ({ results: initialResults }) => {
  // State to manage results and validated errors
  const [results, setResults] = React.useState(initialResults);
  const [validatedErrors, setValidatedErrors] = React.useState({});
  const [showSaveButton, setShowSaveButton] = React.useState(false);
  const [saveStatus, setSaveStatus] = React.useState('');

  // Color coding for scores
  const getScoreColor = (score) => {
    if (score >= 90) return 'bg-green-500 text-white';
    if (score >= 75) return 'bg-yellow-500 text-white';
    if (score >= 60) return 'bg-orange-500 text-white';
    return 'bg-red-500 text-white';
  };

  // Color coding for error types
  const getErrorTypeColor = (type) => {
    switch(type) {
      case 'critical': return 'bg-red-100 text-red-800';
      case 'semantic': return 'bg-yellow-100 text-yellow-800';
      case 'minor': return 'bg-blue-100 text-blue-800';
      case 'perfect': return 'bg-green-100 text-green-800';
      case 'validated': return 'bg-purple-100 text-purple-800';
      default: return '';
    }
  };

  // Function to validate an error
  const validateError = (errorIndex) => {
    // Update the validated errors
    setValidatedErrors(prev => ({
      ...prev,
      [errorIndex]: !prev[errorIndex]
    }));
    
    // Show save button when validation changes
    setShowSaveButton(true);
  };

  // Apply validations and recalculate scores
  const applyValidations = () => {
    // Clone the results
    const newResults = JSON.parse(JSON.stringify(results));
    
    // Get indices of validated errors
    const validatedIndices = Object.entries(validatedErrors)
      .filter(([_, isValidated]) => isValidated)
      .map(([index]) => parseInt(index, 10))
      .sort((a, b) => b - a); // Sort in reverse order to avoid index shifts
    
    // Store validated errors before removing them
    const validatedErrorsList = validatedIndices.map(index => ({
      ...newResults.detailed_errors[index],
      original_index: index
    }));
    
    // Process each validated error
    for (const index of validatedIndices) {
      if (index < 0 || index >= newResults.detailed_errors.length) continue;
      
      const error = newResults.detailed_errors[index];
      const field = error.field;
      
      // Decrement the error category counter
      newResults.error_categories[error.type] = 
        Math.max(0, (newResults.error_categories[error.type] || 0) - 1);
      
      // Increment the perfect category counter
      newResults.error_categories.perfect = 
        (newResults.error_categories.perfect || 0) + 1;
      
      // Update the field score if it exists
      if (newResults.field_scores[field]) {
        const weight = newResults.field_scores[field].weight;
        // Remove old score contribution
        newResults.total_score -= (weight * newResults.field_scores[field].score);
        // Set to perfect score
        newResults.field_scores[field].score = 1.0;
        newResults.field_scores[field].error_type = "perfect";
        // Add new score contribution
        newResults.total_score += weight;
      }
      
      // Remove from detailed errors array
      newResults.detailed_errors.splice(index, 1);
    }
    
    // Recalculate final score
    if (newResults.total_weight > 0) {
      newResults.final_score = (newResults.total_score / newResults.total_weight) * 100;
    }
    
    // Recalculate error distribution percentages
    const total_fields = Object.values(newResults.error_categories).reduce((sum, count) => sum + count, 0);
    if (total_fields > 0) {
      for (const category in newResults.error_categories) {
        newResults.error_categories[category] = Math.round((newResults.error_categories[category] / total_fields) * 1000) / 10;
      }
    }

    // Add validations to the results object
    if (!newResults.applied_validations) {
      newResults.applied_validations = [];
    }
    newResults.applied_validations = [
      ...newResults.applied_validations,
      ...validatedErrorsList
    ];
    
    // Update results state
    setResults(newResults);
    
    // Clear validations as they've been applied
    setValidatedErrors({});
    setShowSaveButton(false);
    
    // Save results to the server
    fetch('/api/save-results', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(newResults),
    })
    .then(response => response.json())
    .then(data => {
      setSaveStatus('Changes saved!');
      setTimeout(() => setSaveStatus(''), 3000);
    })
    .catch(error => {
      console.error('Error saving results:', error);
      setSaveStatus('Error saving changes');
      setTimeout(() => setSaveStatus(''), 3000);
    });
  };

  return (
    <div className="p-4 max-w-5xl mx-auto bg-white rounded-lg shadow">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">HTR Evaluation Dashboard</h1>
        
        {/* Validation Controls */}
        <div className="flex items-center space-x-2">
          {saveStatus && (
            <span className="text-sm text-green-600">{saveStatus}</span>
          )}
          {showSaveButton && (
            <button 
              onClick={applyValidations}
              className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 transition-colors"
            >
              Apply Validations
            </button>
          )}
        </div>
      </div>
      
      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-gray-100 p-4 rounded-lg text-center">
          <p className="text-gray-500 text-sm">Overall Score</p>
          <div className={`text-2xl font-bold my-2 py-2 rounded ${getScoreColor(results.final_score)}`}>
            {results.final_score.toFixed(1)}%
          </div>
        </div>
        
        <div className="bg-gray-100 p-4 rounded-lg text-center">
          <p className="text-gray-500 text-sm">Field Coverage</p>
          <div className={`text-2xl font-bold my-2 py-2 rounded ${getScoreColor(results.field_coverage)}`}>
            {results.field_coverage.toFixed(1)}%
          </div>
        </div>
        
        <div className="bg-gray-100 p-4 rounded-lg text-center">
          <p className="text-gray-500 text-sm">Critical Errors</p>
          <div className="text-2xl font-bold my-2 py-2 rounded bg-red-100 text-red-800">
            {results.error_categories.critical}%
          </div>
        </div>
        
        <div className="bg-gray-100 p-4 rounded-lg text-center">
          <p className="text-gray-500 text-sm">Perfect Matches</p>
          <div className="text-2xl font-bold my-2 py-2 rounded bg-green-100 text-green-800">
            {results.error_categories.perfect}%
          </div>
        </div>
      </div>
      
      {/* Error Distribution */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold mb-3">Error Distribution</h2>
        <div className="h-8 w-full rounded-lg overflow-hidden flex">
          <div 
            className="bg-red-500 h-full" 
            style={{width: `${results.error_categories.critical}%`}}
            title={`Critical: ${results.error_categories.critical}%`}
          ></div>
          <div 
            className="bg-yellow-500 h-full" 
            style={{width: `${results.error_categories.semantic}%`}}
            title={`Semantic: ${results.error_categories.semantic}%`}
          ></div>
          <div 
            className="bg-blue-400 h-full" 
            style={{width: `${results.error_categories.minor}%`}}
            title={`Minor: ${results.error_categories.minor}%`}
          ></div>
          <div 
            className="bg-green-500 h-full" 
            style={{width: `${results.error_categories.perfect}%`}}
            title={`Perfect: ${results.error_categories.perfect}%`}
          ></div>
        </div>
        <div className="flex text-xs mt-1 text-gray-600 justify-between">
          <span>Critical ({results.error_categories.critical}%)</span>
          <span>Semantic ({results.error_categories.semantic}%)</span>
          <span>Minor ({results.error_categories.minor}%)</span>
          <span>Perfect ({results.error_categories.perfect}%)</span>
        </div>
      </div>
      
      {/* Instructions for validation */}
      <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
        <p className="text-sm text-blue-800">
          <strong>Manual Validation:</strong> Check the "Validate" box for errors you consider acceptable or want to ignore. 
          Click "Apply Validations" to update the scores and remove these errors from the list.
        </p>
      </div>
      
      {/* Errors Table with Validation */}
      <div>
        <h2 className="text-xl font-semibold mb-3">
          All Errors ({results.detailed_errors.length})
        </h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Field</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Gold Standard</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">HTR Output</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Error Type</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Validate</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {results.detailed_errors.map((error, index) => (
                <tr key={index} className={validatedErrors[index] ? "bg-purple-50" : ""}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{error.field}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{String(error.gold)}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{String(error.pred || '-')}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getErrorTypeColor(validatedErrors[index] ? 'validated' : error.type)}`}>
                      {validatedErrors[index] 
                        ? 'Validated' 
                        : error.type.charAt(0).toUpperCase() + error.type.slice(1)}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <label className="inline-flex items-center">
                      <input
                        type="checkbox"
                        className="form-checkbox h-5 w-5 text-purple-600"
                        checked={validatedErrors[index] || false}
                        onChange={() => validateError(index)}
                      />
                    </label>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* File Save Section */}
      <div className="mt-8 border-t pt-4">
        <h2 className="text-xl font-semibold mb-3">Export Options</h2>
        <div className="flex space-x-4">
          <button 
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
            onClick={() => {
              const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(results, null, 2));
              const downloadAnchorNode = document.createElement('a');
              downloadAnchorNode.setAttribute("href", dataStr);
              downloadAnchorNode.setAttribute("download", "updated_results.json");
              document.body.appendChild(downloadAnchorNode);
              downloadAnchorNode.click();
              downloadAnchorNode.remove();
            }}
          >
            Export Results
          </button>
          
          <button 
            className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
            onClick={() => {
              // Generate a report of validated errors
              const validatedErrorsList = Object.entries(validatedErrors)
                .filter(([_, isValidated]) => isValidated)
                .map(([index]) => parseInt(index, 10));
              
              if (validatedErrorsList.length === 0) {
                alert("No validations to export");
                return;
              }
                
              const validationData = {
                timestamp: new Date().toISOString(),
                validated_errors: validatedErrorsList.map(index => ({
                  ...initialResults.detailed_errors[index],
                  original_index: index
                }))
              };
                
              const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(validationData, null, 2));
              const downloadAnchorNode = document.createElement('a');
              downloadAnchorNode.setAttribute("href", dataStr);
              downloadAnchorNode.setAttribute("download", "validations.json");
              document.body.appendChild(downloadAnchorNode);
              downloadAnchorNode.click();
              downloadAnchorNode.remove();
            }}
          >
            Export Validations
          </button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
"""
    
    with open(os.path.join(output_dir, "Dashboard.js"), "w") as f:
        f.write(dashboard_js)
        
    # 7. Create server.js for the backend
    server_js = """const express = require('express');
const fs = require('fs');
const path = require('path');
const bodyParser = require('body-parser');

const app = express();
const PORT = process.env.PORT || 8000;

// Serve static files from the dashboard directory
app.use(express.static(path.join(__dirname)));

// Parse JSON bodies
app.use(bodyParser.json({ limit: '10mb' }));

// API endpoint to save updated results
app.post('/api/save-results', (req, res) => {
  try {
    const results = req.body;
    
    // Validate the data
    if (!results || typeof results !== 'object') {
      return res.status(400).json({ error: 'Invalid data format' });
    }
    
    // Write to results.json
    fs.writeFileSync(
      path.join(__dirname, 'results.json'), 
      JSON.stringify(results, null, 2), 
      'utf8'
    );
    
    // Also save a backup with timestamp
    const timestamp = new Date().toISOString().replace(/:/g, '-');
    fs.writeFileSync(
      path.join(__dirname, `results_backup_${timestamp}.json`), 
      JSON.stringify(results, null, 2), 
      'utf8'
    );
    
    res.json({ success: true, message: 'Results saved successfully' });
  } catch (error) {
    console.error('Error saving results:', error);
    res.status(500).json({ error: 'Failed to save results', details: error.message });
  }
});

// API endpoint to save validation data
app.post('/api/save-validations', (req, res) => {
  try {
    const validations = req.body;
    
    // Validate the data
    if (!validations || typeof validations !== 'object') {
      return res.status(400).json({ error: 'Invalid data format' });
    }
    
    // Create validations directory if it doesn't exist
    const validationsDir = path.join(__dirname, 'validations');
    if (!fs.existsSync(validationsDir)) {
      fs.mkdirSync(validationsDir);
    }
    
    // Generate filename with timestamp
    const timestamp = new Date().toISOString().replace(/:/g, '-');
    const filename = `validations_${timestamp}.json`;
    
    // Write validations to file
    fs.writeFileSync(
      path.join(validationsDir, filename),
      JSON.stringify(validations, null, 2),
      'utf8'
    );
    
    res.json({ 
      success: true, 
      message: 'Validations saved successfully',
      filename
    });
  } catch (error) {
    console.error('Error saving validations:', error);
    res.status(500).json({ error: 'Failed to save validations', details: error.message });
  }
});

// Start the server
app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
  console.log(`Dashboard available at http://localhost:${PORT}/index.html`);
});
"""
    
    with open(os.path.join(output_dir, "server.js"), "w") as f:
        f.write(server_js)
    
    # Create validations directory
    validations_dir = os.path.join(output_dir, "validations")
    os.makedirs(validations_dir, exist_ok=True)
    
    # Path to the HTML file
    html_path = os.path.join(output_dir, "index.html")
    
    print(f"\nDashboard files created in {output_dir}")
    print("To view the dashboard, run the following commands:")
    print(f"cd {output_dir}")
    print("npm install")
    print("npm run server")
    
    return html_path

def open_dashboard_with_node_server(output_dir: str) -> None:
    """Open the dashboard using the Node.js Express server."""
    # Change directory to the output directory
    os.chdir(output_dir)
    
    # Install dependencies if needed
    print("\nChecking and installing Node.js dependencies...")
    try:
        # Check if node_modules exists
        if not os.path.exists(os.path.join(output_dir, "node_modules")):
            print("Installing dependencies (this may take a moment)...")
            subprocess.run(["npm", "install"], check=True)
        
        # Start the server in a new process
        print("\nStarting Node.js server...")
        server_process = subprocess.Popen(["node", "server.js"])
        
        # Give the server a moment to start
        time.sleep(2)
        
        # Open the browser
        webbrowser.open("http://localhost:8000")
        
        print("\nDashboard is now running at http://localhost:8000")
        print("Press Ctrl+C to stop the server.")
        
        # Keep the server running until keyboard interrupt
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping server...")
            server_process.terminate()
            print("Server stopped.")
    
    except subprocess.CalledProcessError:
        print("\nError: Failed to install Node.js dependencies.")
        print("Please make sure Node.js and npm are installed on your system.")
        print("You can install them manually and then run:")
        print(f"cd {output_dir}")
        print("npm install")
        print("node server.js")
    
    except Exception as e:
        print(f"\nError: {e}")
        print("To manually start the server, run:")
        print(f"cd {output_dir}")
        print("npm install (if not already done)")
        print("node server.js")

def main():
    """Main function to run the evaluation script."""
    parser = argparse.ArgumentParser(description='Evaluate HTR document against gold standard.')
    parser.add_argument('gold_path', help='Path to the gold standard JSON file')
    parser.add_argument('pred_path', help='Path to the predicted JSON file')
    parser.add_argument('--output', help='Path to save the evaluation results', default='output/evaluation_results.json')
    parser.add_argument('--dashboard', help='Path to save the dashboard files', default='output/dashboard')
    parser.add_argument('--serve', action='store_true', help='Serve the dashboard using a simple HTTP server')
    parser.add_argument('--validations', help='Path to a validations JSON file to apply')

    
    args = parser.parse_args()
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # Evaluate the documents
    results = evaluate_documents(args.gold_path, args.pred_path)
    
    # Print summary
    print_summary(results)
    
    # Export results to JSON
    export_results_to_json(results, args.output)
    
    # Generate dashboard
    dashboard_path = generate_dashboard(args.output, args.dashboard)
    
    # Serve the dashboard if requested
    if args.serve:
        open_dashboard_with_node_server(args.dashboard)

if __name__ == "__main__":
    main()