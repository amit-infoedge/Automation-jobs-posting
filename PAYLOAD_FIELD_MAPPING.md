# Job Payload Field Mapping - C# to Python

## Source: ORE.cs lines 665-1028

This document maps every field in the job payload object from C# code to Python implementation.

### Job Object Fields (lines 665-1028)

| Field | C# Code | Logic | Python Implementation |
|-------|---------|-------|------------------------|
| `assignedSubUsers` | Line 667 | If jobs.SubUser != null && Count > 0, set as array | Only if assigned_sub_users list is not empty |
| `createdDate` | Line 669 | DateHelper.DateTimeToUnixTimestamp(DateTime.Now) | int(datetime.now().timestamp() * 1000) |
| `jobState` | Line 670 | "SAVE" (hardcoded) | action parameter (SAVE, UPDATE, REFRESH, REPOST) |
| `jobId` | Line 671 | null | None or null |
| `editBoard` | Line 672 | null | None or null |
| `mode` | Line 673 | "jp" (hardcoded) | "jp" |
| `draftId` | Line 674 | null initially, set after draft save | None (set after draft save response) |
| `boardProprietaryJobType` | Line 675 | null | None or null |
| `source` | Line 676 | jobs.Source (from database: "online" or "offline") | "offline" |
| `jobType` | Line 677 | "fulltime" (hardcoded) | "fulltime" |
| `internshipStartDate` | Line 678 | "" (empty string) | "" |
| `internshipDuration` | Line 679 | "" (empty string) | "" |
| `internshipDeadline` | Line 680 | "" (empty string) | "" |
| `internshipPpo` | Line 681 | false | false |
| `companyType` | Line 682 | "established" (hardcoded) | "established" |
| `title` | Line 683 | jobs.Position | job.position |
| `wfhType` | Line 684-687 | If jobs.WFH != null, use it; else not set | Should check if provided, default to "wfo" |
| `requirementName` | Line 690 | jobs.Responses.Contains("RMSENTER") ? jobs.Req_Name : "" | Set only if specific response mode, else empty |
| `description` | Line 698 | jobs.JD | job.description |
| `dcp` | Line 701-710 | If PostingType=="c": jobs.Candidate_Profile, else: "" | job.desired_candidate_profile if c-type, else "" |
| `jpb` | Line 701-710 | If PostingType=="c": "", else: "" (always empty) | "" |
| `rnr` | Line 701-710 | If PostingType=="c": jobs.JD, else: "." | job.description if c-type, else "." |
| `keySkillsGid` | Line 712-735 | Split by comma, all marked preferred="false", then add MandKeywords with preferred="true" | Similar logic: mark first 3 as preferred if none marked |
| `minimumExperience` | Line 736 | jobs.MinExp | job.min_experience |
| `maximumExperience` | Line 737 | jobs.MaxExp | job.max_experience |
| `minimumExperienceLabel` | Line 738 | jobs.MinExp (same as above) | str(job.min_experience) |
| `maximumExperienceLabel` | Line 739 | jobs.MaxExp (same as above) | str(job.max_experience) |
| `diversityTag` | Line 740-746 | If jobs.hireWomen: {"type": ["1"], "exclusive": false} | If job.hire_women: set diversity tag |
| `nationalLocationsGid` | Line 754-761 | Loop through jobs.NationalLocations: {code: {id, label}} | {loc_id: {id, label, isCustomGroup}} |
| `internationalLocationsGid` | Line 765-772 | Loop through jobs.InternationalLocations: {code: {id, label}} | {loc_id: {id, label, isCustomGroup: false}} |
| `otherNationalLocations` | Line 775 | jobs.OtherNationalLocations == null ? [] : array | job.other_national_locations or [] |
| `otherInternationalLocations` | Line 776 | jobs.OtherInternationalLocatons == null ? [] : array | job.other_international_locations or [] |
| `baseLocation` | Line 778-787 | If WFH=="2" AND locationCount<2: set with locations | If wfh=="2" and single location, set baseLocation |
| `isRmj` | Line 791 | false | false |
| `localities` | Line 924 | {} (empty object) | {} |
| `localitiesGid` | Line 927 | {} (empty object) | {} |
| `otherLocalities` | Line 928 | [] (empty array) | [] |
| `companyId` | Line 929 | jobs.CompanyId | company_id |
| `nonMetroLocations` | Line 932-941 | Specific structure with 9 fields all empty arrays/labels | Exact structure as in C# |
| `microsites` | Line 943-946 | If microsites.HasValues: use it; else: [] | [] (hardcoded for now) |
| `companyDetail` | Line 947 | From earlier section (lines 645-663) | name, details, address, etc. |
| `category` | Line 948 | jobs.PostingType | job.job_type ("h", "c", "s") |
| `referenceCode` | Line 950 | jobs.RefCode | job.reference_code |
| `vacancy` | Line 951 | jobs.Vacancy or "" | job.vacancy |
| `employmentType` | Line 952 | "Full Time, Permanent" (hardcoded) | "Full Time, Permanent" |
| `industryGid` | Line 953 | jobs.Industry_Id.Split('-')[0].Trim() | Extract before dash |
| `subIndustryGid` | Line 954-959 | If Industry_Id contains "-": take [1], else: "" | Extract after dash or empty |
| `functionalArea` | Line 963 | jobs.Farea | job.functional_area_gid |
| `functionalAreaGid` | Line 964 | jobs.Farea (same as above) | job.functional_area_gid |
| `roleCategoryGid` | Line 967 | jobs.Role.Split(',')[1] | Extract from role field position [1] |
| `jobRole` | Line 968 | jobs.Role.Split(',')[2] | Extract from role field position [2] |
| `jobRoleGid` | Line 969 | jobs.Role.Split(',')[2] (same as jobRole) | Extract from role field position [2] |
| `education` | Line 973-982 | {ugGid, pgGid, ppgGid, degreeCombination} | From education object |
| `walkIn` | Line 985 | "false" (hardcoded) | "false" |
| `walkInDetail` | Line 987-1000 | Full structure with 11 fields (all defaults) | Full walkInDetail structure |
| `recruiterProfile` | Line 1003 | null | null |
| `showRecruiterDetail` | Line 1004 | false | false |
| `allowSendQuery` | Line 1005 | null | null |
| `salaryDetail` | Line 1007-1015 | {minimumSalary, maximumSalary, currency, hideSalary, variablePercentage} | From salary_detail |
| `questionnaireId` | Line 1016 | null | null |
| `responseManager` | Line 1018 | jobs.ResponseMode (conditional: "rms", "companyUrl", "ATS") | Conditional based on input |
| `responseManagerSettings` | Line 1020 | Conditional object based on ResponseMode | Conditional based on URL/emails |
| `requirementId` | Line 1022 | "" (empty string) | "" |
| `registrationType` | Line 1024 | company_type == "y" ? "consultant" : "company" | Fetch company type from API |
| `selectedBoards` | Line 1025 | [1] | [1] |
| `initialSelectedLocationCount` | Line 1026 | null | null |
| `shareJobLegacyFlag` | Line 1027 | false | false |
| `appliedFilters` | Line 1028 | _paf (complex PAF object) | appliedFilters object |
| `sourcePlatform` | Line 1082 | "offline_excel" | "offline_script" |

### Board Object Fields (lines 624-638)

| Field | C# Code | Logic | Location |
|-------|---------|-------|----------|
| `boardProprietaryJobType` | Line 625 | null | boards["1"] |
| `branding` | Line 626-627 | If brandingReq: set branding object | boards["1"] |
| `responseManager` | Line 628 | jobs.ResponseMode | boards["1"] |
| `responseManagerSettings` | Line 629 | responseManagerSettings object | boards["1"] |
| `description` | Line 635 | jobs.JD (for c-type only) | boards["1"] |
| `dcp` | Line 636 | jobs.Candidate_Profile (for c-type only) | boards["1"] |
| `jpb` | Line 637 | "" (for c-type only) | boards["1"] |
| `rnr` | Line 638 | jobs.JD (for c-type only) | boards["1"] |

### Company Detail Object (lines 645-663)

| Field | C# Code | Logic |
|-------|---------|-------|
| `name` | Line 646 | jobs.CompanyName |
| `websiteUrl` | Line 647 | Tool.GetJson(resource_json["companyDetail"],"website") |
| `details` | Line 648 | jobs.Comp_Profile |
| `address` | Line 649 | jobs.Address |
| `media` | Line 651-653 | {video: [], photos: [], ppt: []} |
| `size` | Line 657 | "1-10" |
| `workAreas` | Line 658 | "" |
| `fundingStage` | Line 659 | "" |
| `investorDetails` | Line 660 | "" |
| `hiringFor` | Line 661-663 | If company_type=="y": jobs.HiringFor, else: "" |

### PAF (PostingAppliedFilters) Object (lines 793-920)

| Field | Condition | Value |
|-------|-----------|-------|
| `experience` | If PAF_str.Contains("exp") | {minimumExperience, maximumExperience} |
| `location` | If PAF_str.Contains("loc") or relocate | {nationalLocations, internationalLocations, otherNationalLocations, otherInternationalLocations, willingToRelocateFlag: true} |
| `salary` | If PAF_str.Contains("sal") or "ctc" | {minimumSalary, maximumSalary, salaryCurrency: "INR", salaryZeroFlag: true} |
| `industry` | If PAF_str.Contains("ind") | {industryGIds: [], industryOtherLabels: null, industryOtherFlag: true} |
| `education` | If PAF_str.Contains("edu") or Premium | {anyEducationFlag: false, ugEducationGId, pgEducationGId, ppgEducationGId, degreeCombination} |
| `relevanceRating` | Always | "medium" (default) |

## Implementation Notes

1. **WFH Field**: In C#, jobs.WFH can be null, "2" (work from home), etc. Need to handle accordingly.
2. **Role Parsing**: Role field is comma-separated with specific positions: [0]=category, [1]=roleCategoryGid, [2]=jobRoleGid
3. **Industry Parsing**: Industry field can contain sub-industry separated by dash: "Industry-SubIndustry"
4. **Response Manager**: Must check condition tree: URL > Email > CSM/RMS > ATS > default RMS
5. **Company Type**: Determine from API resource call (company_type == "y" means "consultant")
6. **PAF Object**: Only populated if PremiumChk contains "1" OR PAF_str has length > 2
7. **Location Conditions**: baseLocation only set if WFH=="2" AND locationCount<2
8. **Degree Combination**: String.Join with separator (needs verification - looks like empty string join)

## Status

- ✓ Main job fields mapped
- ✓ Board fields mapped  
- ✓ Company detail fields mapped
- ✓ PAF fields mapped
- ⚠️ Still needs: Company type fetching, PAF calculation logic, keySkill preferred flag logic, WFH handling
