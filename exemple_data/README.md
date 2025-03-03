# Example Documents for HTR Evaluation

This directory contains mock documents to demonstrate the HTR evaluation process. These examples reflect typical patterns and errors found in real-world HTR tasks, but do not contain any private or sensitive information.

## Files Included

### `mock_gold.json`
The gold-standard reference document, representing the ground truth for a fictional grant application form.

### `mock_claude.json`
A simulated HTR output from Claude, containing several typical recognition errors:

1. **Spelling errors**:
   - "Metiers" instead of "Métiers" (missing accent)
   - "Marie DUPORT" instead of "Marie DUPONT" (common confusion of N/R)

2. **Numeric errors**:
   - "01-42-88-63-32" instead of "01-42-88-65-32" (digit confusion)

3. **Type conversion issues**:
   - Numbers represented as strings with quotes
   - Boolean "true" represented as string "oui"

4. **Grammar and plurality errors**:
   - "traditionnelles" instead of "traditionnels" (gender agreement error)

5. **Additional metadata**:
   - Added confidence scores and explanations that aren't in the gold standard

## Using These Examples

Run the evaluation script with these examples to see how the system handles different types of errors:

```bash
python ../htr-evaluation-script.py mock_gold.json mock_claude.json 
```

This will generate a detailed report showing:
- The overall accuracy score
- Field coverage
- Error categorization
- Side-by-side comparisons of discrepancies

## Creating Your Own Test Files

When creating your own test files, use these examples as templates. Make sure to include a variety of field types:
- Text fields (names, descriptions)
- Numeric fields (amounts, counts)
- Phone numbers
- Dates
- Boolean values
- Nested structures

Introducing realistic errors will help assess how well your evaluation metrics perform in real-world scenarios.
