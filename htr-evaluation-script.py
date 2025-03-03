import json
import os
import argparse
import re
from typing import Dict, Tuple, Any
import subprocess

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
    
    Handles:
    - None values
    - String representation of None like "null", "None", "-"
    - Whitespace
    """
    if value is None:
        return ""
    
    value_str = str(value).strip().lower()
    
    if value_str in ["null", "none", "-", "nan"]:
        return ""
    
    return value_str

def is_null_value(value: Any) -> bool:
    """
    Check if a value should be considered as null/none.
    """
    if value is None:
        return True
    
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in ["null", "none", "-", "nan", ""]


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
    """Categorize the error type and assign a score"""
    
    # Special handling for null values
    gold_is_null = is_null_value(gold_value)
    pred_is_null = is_null_value(pred_value)
    if gold_is_null and pred_is_null:
        return "perfect", 1.0
    if gold_is_null != pred_is_null:
        return "critical", 0.0
    
    # For normal fields using string similarity
    gold_norm = normalize_field(field, gold_value)
    pred_norm = normalize_field(field, pred_value)
    if gold_norm == pred_norm:
        return "perfect", 1.0
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
    
    normalized_flat_pred = {}
    for key, value in flat_pred.items():
        normalized_key = key.replace(' ', '_')
        normalized_flat_pred[normalized_key] = value

    flat_pred = normalized_flat_pred
    
    filtered_gold = {k: v for k, v in flat_gold.items() if not k.startswith('metadata')}
    filtered_pred = {k: v for k, v in flat_pred.items() if not k.startswith('metadata')}

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
    
    for field in filtered_gold:
        if field not in filtered_pred:
            if not is_null_value(filtered_gold[field]):
                results["missing_fields"].append(field)
                results["error_categories"]["critical"] += 1
                results["detailed_errors"].append({
                    "field": field,
                    "gold": filtered_gold[field],
                    "pred": None,
                    "type": "critical",
                    "score": 0.0
                })
    
    for field in filtered_pred:
        if field not in filtered_gold:
            if not is_null_value(filtered_pred[field]):
                results["extra_fields"].append(field)
    
    for field in filtered_gold:
        if field in filtered_pred:
            gold_value = filtered_gold[field]
            pred_value = filtered_pred[field]
            
            if is_null_value(gold_value) and is_null_value(pred_value):
                results["error_categories"]["perfect"] += 1
                results["field_scores"][field] = {
                    "gold": gold_value,
                    "pred": pred_value,
                    "score": 1.0,
                    "error_type": "perfect",
                    "weight": 1.0  # minimal weight for null-null matches
                }
                continue
            
            weight = get_field_weight(field)
            results["total_weight"] += weight
            
            error_type, score = categorize_error(gold_value, pred_value, field)
            
            results["field_scores"][field] = {
                "gold": gold_value,
                "pred": pred_value,
                "score": score,
                "error_type": error_type,
                "weight": weight
            }
            
            results["error_categories"][error_type] += 1
            results["total_score"] += weight * score
            
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

def launch_dashboard(dashboard_dir: str, results_path: str) -> None:
    """
    Launch the dashboard by calling the Node.js script
    """
    try:
        # Run the Node.js dashboard script
        print(f"\nLaunching dashboard for {results_path}...")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dashboard_script = os.path.join(script_dir, "dashboard_generator.js")
        
        cmd = ["node", dashboard_script, results_path, dashboard_dir]
        subprocess.run(cmd, check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"Error launching dashboard: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")



def main():
    """Main function to run the evaluation script."""
    parser = argparse.ArgumentParser(description='Evaluate HTR document against gold standard.')
    parser.add_argument('gold_path', help='Path to the gold standard JSON file')
    parser.add_argument('pred_path', help='Path to the predicted JSON file')
    parser.add_argument('--output_dir', help='Directory to save the evaluation results', default='./output/')
    
    args = parser.parse_args()
    
    pred_filename = os.path.splitext(os.path.basename(args.pred_path))[0]
    output_json = os.path.join(args.output_dir, f"{pred_filename}_evaluation_results.json")
    dashboard_dir = os.path.join(args.output_dir, f"{pred_filename}_dashboard")
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    results = evaluate_documents(args.gold_path, args.pred_path)
    print_summary(results)
    export_results_to_json(results, output_json)
    
    launch_dashboard(dashboard_dir, output_json)
    
    print(f"\nEvaluation results saved to: {output_json}")
    print(f"Dashboard saved to: {dashboard_dir}")

if __name__ == "__main__":
    main()
