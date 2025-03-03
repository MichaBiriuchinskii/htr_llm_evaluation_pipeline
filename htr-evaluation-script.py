import json
import os
import argparse
import re
from typing import Dict, Tuple, Any
import webbrowser

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

def evaluate_documents(gold_path: str, pred_path: str) -> Dict:
    """
    Returns a dictionary with evaluation metrics.
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
        "detailed_errors": []
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
            
            # Categorize error and get score
            error_type, score = categorize_error(gold_value, pred_value, field)
            
            # Update results
            results["field_scores"][field] = {
                "gold": gold_value,
                "pred": pred_value,
                "score": score,
                "error_type": error_type,
                "weight": weight
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
    Generate the React dashboard based on evaluation results.
    Returns the path to the HTML file.
    """

    os.makedirs(output_dir, exist_ok=True)
    
    # Create necessary files for the React app
    # 1. Create package.json
    package_json = {
        "name": "htr-evaluation-dashboard",
        "version": "1.0.0",
        "description": "Dashboard for HTR evaluation results",
        "main": "index.js",
        "scripts": {
            "start": "parcel index.html",
            "build": "parcel build index.html"
        },
        "dependencies": {
            "react": "^17.0.2",
            "react-dom": "^17.0.2"
        },
        "devDependencies": {
            "parcel": "^2.0.1"
        }
    }
    
    with open(os.path.join(output_dir, "package.json"), "w") as f:
        json.dump(package_json, f, indent=2)
    
    # 2. Create index.html
    index_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HTR Evaluation Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
</head>
<body>
    <div id="root"></div>
    <script type="module" src="./index.js"></script>
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
    import shutil
    shutil.copy(results_path, os.path.join(output_dir, "results.json"))
    
    # 6. Create Dashboard.js component
    dashboard_js = """import React from 'react';

const Dashboard = ({ results }) => {
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
      default: return '';
    }
  };

  return (
    <div className="p-4 max-w-5xl mx-auto bg-white rounded-lg shadow">
      <h1 className="text-2xl font-bold mb-6">HTR Evaluation Dashboard</h1>
      
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
      
      {/* Top Errors Table */}
      <div>
        <h2 className="text-xl font-semibold mb-3">All Errors ({results.detailed_errors.length})</h2>
        <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
            <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Field</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Gold Standard</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">HTR Output</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Error Type</th>
            </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
            {results.detailed_errors.map((error, index) => (
                <tr key={index}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{error.field}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{String(error.gold)}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{String(error.pred || '-')}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getErrorTypeColor(error.type)}`}>
                      {error.type.charAt(0).toUpperCase() + error.type.slice(1)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
"""
    
    with open(os.path.join(output_dir, "Dashboard.js"), "w") as f:
        f.write(dashboard_js)
    
    # Path to the HTML file
    html_path = os.path.join(output_dir, "index.html")
    
    print(f"\nDashboard files created in {output_dir}")
    print("To view the dashboard, run the following commands:")
    print(f"cd {output_dir}")
    print("npm install")
    print("npm start")
    
    return html_path

def open_dashboard_with_simple_server(output_dir: str) -> None:
    """Open the dashboard using a simple HTTP server."""
    import http.server
    import socketserver
    import threading
    
    PORT = 8000
    
    # Change directory to the output directory
    os.chdir(output_dir)
    
    Handler = http.server.SimpleHTTPRequestHandler
    
    # Create server
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"\nStarting simple HTTP server at http://localhost:{PORT}")
        print("Press Ctrl+C to stop the server.")
        
        # Open the browser
        webbrowser.open(f"http://localhost:{PORT}")
        
        # Start the server
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")

def main():
    """Main function to run the evaluation script."""
    parser = argparse.ArgumentParser(description='Evaluate HTR document against gold standard.')
    parser.add_argument('gold_path', help='Path to the gold standard JSON file')
    parser.add_argument('pred_path', help='Path to the predicted JSON file')
    parser.add_argument('--output_dir', help='Directory to save the evaluation results', default='./output/')
    parser.add_argument('--serve', action='store_true', help='Serve the dashboard using a simple HTTP server')
    
    args = parser.parse_args()
    
    # Extract base name from the predicted file (without extension)
    pred_filename = os.path.splitext(os.path.basename(args.pred_path))[0]
    
    # Define dynamic output paths
    output_json = os.path.join(args.output_dir, f"{pred_filename}_evaluation_results.json")
    dashboard_dir = os.path.join(args.output_dir, f"{pred_filename}_dashboard")
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Evaluate the documents
    results = evaluate_documents(args.gold_path, args.pred_path)
    
    # Print summary
    print_summary(results)
    
    # Export results to JSON
    export_results_to_json(results, output_json)
    
    # Generate dashboard
    dashboard_path = generate_dashboard(output_json, dashboard_dir)
    
    # Serve the dashboard if requested
    if args.serve:
        open_dashboard_with_simple_server(dashboard_dir)
    
    print(f"Evaluation results saved to: {output_json}")
    print(f"Dashboard saved to: {dashboard_dir}")

if __name__ == "__main__":
    main()