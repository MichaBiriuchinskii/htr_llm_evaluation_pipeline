```python

json_structure_file = {
  "header": {
    "title": null
  },
  "organisation": {
    "nom": null,
    "addresse_info": null
  }
}

contexte = "You are an expert in document processing and HTR-based structured data extraction. You're working with French legal documents. [ADJUST IF NEEDED]"

prompt = f"""
Context:
{contexte}

Objective:
Extract relevant text fields, checkbox selections, and structured data from the given document image. Ignore occasional extra stamps, handwritten notes, or artifacts that are not part of the predefined fields.

Style & Tone:
No modification of style and tone of original text should be done.

Task:
Extract text and checkbox values according to the schema provided. Preserve the document's structure and use the correct variable names.

The default value for some fields is null. If field is empty, leave it null. If a field is unclear, leave it blank null.

Provide a confidence score (0-1) in the metadata field based on extraction accuracy, and your commentary if the score is low.

Action: Return a structured JSON following this schema:

{json_structure_file}

Result Format:
Output must be in structured valid JSON format. Do not add any explanations or formatting beyond the required JSON.

Key Considerations:
Text may be misrecognized; apply OCR post-processing when needed. If not sure — leave it as it is. (Ex. "21 b8 Sévén MICHEL 7505 PARI$" --> "51 bd St Michel 75005 PARIS" ; "5 rue des CHAMPS PIKAREUX 9209 NAUTERRE" --> "55 avenue des CHAMPS PIERREUX 92083 NANTERRE")

Checkbox selections should be correctly detected. To help you do it, I provided options via [SELECT ONE: ...]. Select 'oui/True' if the checkbox appears filled (■,✓,×), 'non/False' if empty (□), 'null' if unclear. Look for checkboxes next to 'oui' and 'non' text labels.

At the end, populate the 'metadata' field with a 'confidence_score', estimating how reliably the document was transcribed and add a 'confidence_explanation' comment. 
"""

```
