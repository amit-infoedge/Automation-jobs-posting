"""
SQL to API Mapping Usage Examples
Shows how to use sql_api_mapping.py in your job posting workflow
"""

from sql_api_mapping import PayloadBuilder, MappingValidator, SQLToAPIMapping
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# EXAMPLE 1: Basic Job Posting
# ============================================================================
def example_basic_posting():
    """Example: Post a basic job with minimal fields"""
    logger.info("EXAMPLE 1: Basic Job Posting")

    # Sample SQL row from database
    sql_row = {
        'file': '202401010001',
        'Company id': '27117',
        'Job_Type': 'h',  # 'h' for normal, 's' for simple, 'c' for corporate
        'title': 'Senior Python Developer',
        'description': 'We are looking for an experienced Python developer...',
        'minExp': '3',
        'maxExp': '8',
        'Keywords': 'Python,Django*,PostgreSQL,REST API',
        'Location_Str': 'Bangalore,Delhi',
        'Industry': '1',
        'Farea': '2',
        'Role': '3',
        'UG': '#9502:',  # Any UG
        'Responses': 'email',
        'email': 'hr@company.com',
        'companyName': 'Tech Company Ltd',
        'Source': 'Web',
    }

    # Build payload
    builder = PayloadBuilder()
    payload = builder.build(sql_row, job_type='h', action='SAVE')

    logger.info(f"Built payload: {payload}")
    return payload


# ============================================================================
# EXAMPLE 2: Validate Before Posting
# ============================================================================
def example_validate_before_posting():
    """Example: Validate job data before posting"""
    logger.info("\nEXAMPLE 2: Validate Before Posting")

    sql_row = {
        'file': '202401010002',
        'Company id': '27117',
        'Job_Type': 'h',
        'title': 'Data Scientist',
        # Missing Location_Str - this should fail validation
    }

    # Validate
    validator = MappingValidator()
    is_valid, errors = validator.validate_job_data(sql_row, job_type='h')

    if not is_valid:
        logger.error(f"Validation failed with {len(errors)} error(s):")
        for error in errors:
            logger.error(f"  - {error}")
    else:
        logger.info("Validation passed!")

    return is_valid, errors


# ============================================================================
# EXAMPLE 3: Corporate Job (C-Type) with Full Details
# ============================================================================
def example_corporate_job():
    """Example: Post a corporate-type job with roles, candidate profile, perks"""
    logger.info("\nEXAMPLE 3: Corporate Job (C-Type)")

    sql_row = {
        'file': '202401010003',
        'Company id': '16987',
        'Job_Type': 'c',  # Corporate type
        'title': 'Engineering Manager',
        'rnr': '<h4>Roles & Responsibilities:</h4><ul><li>Lead team</li><li>Manage projects</li></ul>',
        'dcp': '<h4>Desired Candidate:</h4><ul><li>5+ years experience</li><li>Leadership skills</li></ul>',
        'jpb': '<h4>Perks:</h4><ul><li>Competitive salary</li><li>Health insurance</li></ul>',
        'minExp': '5',
        'maxExp': '10',
        'Keywords': 'Leadership,Project Management*,Python,Agile',
        'Location_Str': 'Bangalore',
        'Industry': '2',
        'Farea': '3',
        'Role': '4',
        'UG': '#9502:',
        'PG': '#9511:',  # Also has PG
        'CTC_Str': '15-25 LPA',  # Salary in LPA format
        'Responses': 'email',
        'email': 'careers@company.com',
        'companyName': 'Enterprise Corp',
        'Process': 'Premium',
    }

    builder = PayloadBuilder()
    payload = builder.build(sql_row, job_type='c', action='SAVE')

    logger.info(f"Built corporate job payload (keys): {payload.get('job', {}).keys()}")
    return payload


# ============================================================================
# EXAMPLE 4: Check Required vs Optional Columns
# ============================================================================
def example_column_info():
    """Example: Check which columns are required"""
    logger.info("\nEXAMPLE 4: Column Information")

    required = SQLToAPIMapping.get_required_columns()
    optional = SQLToAPIMapping.get_optional_columns()

    logger.info(f"Required columns ({len(required)}):")
    for col in required:
        logger.info(f"  - {col}")

    logger.info(f"\nOptional columns ({len(optional)}):")
    for col in optional[:5]:  # Show first 5
        logger.info(f"  - {col}")
    logger.info(f"  ... and {len(optional)-5} more")


# ============================================================================
# EXAMPLE 5: Mapping Individual Column
# ============================================================================
def example_single_column_mapping():
    """Example: Check mapping for a specific column"""
    logger.info("\nEXAMPLE 5: Single Column Mapping")

    # Check where 'title' column maps to
    title_mapping = SQLToAPIMapping.get_mapping('title')
    logger.info(f"Column 'title' maps to: {title_mapping.api_path}")
    logger.info(f"  Type: {title_mapping.col_type}")
    logger.info(f"  Required: {title_mapping.required}")

    # Check where 'Keywords' column maps to
    keywords_mapping = SQLToAPIMapping.get_mapping('Keywords')
    logger.info(f"\nColumn 'Keywords' maps to: {keywords_mapping.api_path}")
    logger.info(f"  Type: {keywords_mapping.col_type}")
    logger.info(f"  Note: Parsed from CSV to dict with 'preferred' flags")


# ============================================================================
# EXAMPLE 6: Using in Actual Job Posting Loop
# ============================================================================
def example_in_posting_loop():
    """Example: How to use in actual job posting workflow"""
    logger.info("\nEXAMPLE 6: Using in Posting Loop")

    # Simulated SQL rows
    jobs = [
        {
            'file': '202401010004',
            'Company id': '27117',
            'Job_Type': 'h',
            'title': 'Frontend Developer',
            'description': 'React/Vue expertise required',
            'minExp': '2',
            'maxExp': '5',
            'Keywords': 'React*,JavaScript,CSS',
            'Location_Str': 'Mumbai',
            'Industry': '1',
            'Farea': '2',
            'Role': '3',
            'UG': '#9502:',
        },
        {
            'file': '202401010005',
            'Company id': '27117',
            'Job_Type': 'h',
            'title': 'Backend Engineer',
            'description': 'Node.js/Python required',
            'minExp': '3',
            'maxExp': '7',
            'Keywords': 'Node.js*,Python,PostgreSQL',
            'Location_Str': 'Bangalore',
            'Industry': '1',
            'Farea': '2',
            'Role': '3',
            'UG': '#9502:',
        }
    ]

    builder = PayloadBuilder()
    validator = MappingValidator()
    results = []

    for idx, job_row in enumerate(jobs):
        logger.info(f"\nProcessing job {idx+1}: {job_row.get('title')}")

        # Validate first
        is_valid, errors = validator.validate_job_data(job_row, job_type=job_row.get('Job_Type', 'h'))

        if not is_valid:
            logger.error(f"  Validation failed: {errors}")
            results.append({
                'job_id': job_row.get('file'),
                'status': 'FAILED',
                'reason': '; '.join(errors)
            })
            continue

        # Build payload
        payload = builder.build(job_row, job_type=job_row.get('Job_Type', 'h'), action='SAVE')

        # Check for errors in payload
        if 'error' in payload:
            logger.error(f"  Payload build failed: {payload['error']}")
            results.append({
                'job_id': job_row.get('file'),
                'status': 'FAILED',
                'reason': str(payload['error'])
            })
            continue

        # Would send to API here
        logger.info(f"  ✓ Payload ready for posting")
        logger.info(f"    Job title: {payload.get('job', {}).get('title')}")
        logger.info(f"    Location: {job_row.get('Location_Str')}")
        logger.info(f"    Experience: {job_row.get('minExp')}-{job_row.get('maxExp')} years")

        results.append({
            'job_id': job_row.get('file'),
            'status': 'READY',
            'reason': 'Passed validation and mapping'
        })

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"Summary:")
    logger.info(f"  Total: {len(results)}")
    logger.info(f"  Ready: {sum(1 for r in results if r['status'] == 'READY')}")
    logger.info(f"  Failed: {sum(1 for r in results if r['status'] == 'FAILED')}")
    logger.info(f"{'='*60}")

    return results


# ============================================================================
# EXAMPLE 7: Custom Transform Example
# ============================================================================
def example_custom_transforms():
    """Example: Shows how transforms work"""
    logger.info("\nEXAMPLE 7: Custom Transforms")

    test_values = {
        'file': '202401010006.0',  # Will remove .0
        'Company id': '27117.0',   # Will convert to int
        'minExp': '3.5',           # Will convert to string int
        'Keywords': 'Python,Django*,PostgreSQL',  # Will parse to dict
        'CTC_Str': '10-15 LPA',    # Will parse to salary range
        'Exp_Str': '3-8 years',    # Will parse to min/max
    }

    mapping = SQLToAPIMapping()
    logger.info("Transform Examples:")

    for col, value in test_values.items():
        col_mapping = mapping.get_mapping(col)
        if col_mapping:
            transformed = col_mapping.transform(value)
            logger.info(f"  {col}: '{value}' → {transformed}")


# ============================================================================
# Main
# ============================================================================
if __name__ == "__main__":
    logger.info("SQL to API Mapping - Usage Examples\n")
    logger.info("="*60)

    # Run examples
    example_basic_posting()
    example_validate_before_posting()
    example_corporate_job()
    example_column_info()
    example_single_column_mapping()
    example_in_posting_loop()
    example_custom_transforms()

    logger.info("\n" + "="*60)
    logger.info("Examples completed!")
