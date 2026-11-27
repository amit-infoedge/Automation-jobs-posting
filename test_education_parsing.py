"""Test education parsing logic"""
import json

def parse_education_value(edu_input):
    """
    Parse education value (string or list) into API format
    Input: "#9502:" or ["#9502:"] or "#9502:spec1,spec2"
    Output: [{"course": "9502", "spec": [...]}, ...]
    """
    if not edu_input:
        return []

    # Convert to string if it's a list
    if isinstance(edu_input, list):
        if not edu_input or not edu_input[0]:
            return []
        edu_str = str(edu_input[0])
    else:
        edu_str = str(edu_input)

    edu_array = []
    # Split by pipe if multiple educations
    for edu_item in edu_str.replace("#", "").split("|"):
        if not edu_item.strip():
            continue
        parts = edu_item.split(":")
        edu_obj = {'course': parts[0].strip()}
        # Add spec if provided
        if len(parts) > 1 and parts[1].strip():
            edu_obj['spec'] = [s.strip() for s in parts[1].split(",")]
        else:
            edu_obj['spec'] = []
        edu_array.append(edu_obj)
    return edu_array


# Test cases
test_cases = [
    ("#9502:", "Single course no spec (list)"),
    (["#9502:"], "Single course no spec (wrapped in list)"),
    ("#9502:Spec1,Spec2", "Single course with specs (list)"),
    (["#9502:Spec1,Spec2"], "Single course with specs (wrapped)"),
    ("#9502:|#9503:", "Multiple courses no specs"),
    (["#9502:"], "Database format - wrapped"),
    (None, "None value"),
    ([], "Empty list"),
]

print("=" * 80)
print("EDUCATION PARSING TEST")
print("=" * 80)

for test_input, description in test_cases:
    print(f"\nTest: {description}")
    print(f"Input: {test_input!r}")
    result = parse_education_value(test_input)
    print(f"Output: {json.dumps(result, indent=2)}")
    print(f"Length: {len(result)}")

print("\n" + "=" * 80)
print("EXPECTED OUTPUT FOR '#9502:':")
print(json.dumps([{"course": "9502", "spec": []}], indent=2))
