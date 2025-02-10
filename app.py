from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from forms import BuildInitForm, TierStructureForm, RateStructuresForm
from flask_wtf.csrf import CSRFProtect, generate_csrf
from supabase import create_client, Client
from dotenv import load_dotenv
from itertools import product
from collections import defaultdict
import os
import re 
import uuid 
import json

#Flask Setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'key'  # Set a secret key for CSRF protection

#CSRF Protection
csrf = CSRFProtect(app)

load_dotenv()

# Supabase setup
supabase_url = "https://ugdaizvybkwetnxwydxs.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVnZGFpenZ5Ymt3ZXRueHd5ZHhzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcyODQzMTg4MCwiZXhwIjoyMDQ0MDA3ODgwfQ.NoImb7hSN1IfHU6bRwH1HRJUcA2vuFblOLn73Ln4GVA"

# Create Supabase client
supabase=create_client(supabase_url, supabase_key)

# Home route
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/clients')
def client_list():
    # Query the Client table
    response = supabase.table('Client').select('ClientName, ClientId').execute()
    clients = response.data  # Extract data from the response
    return render_template('client_list.html', clients=clients)

@app.route('/client/<int:client_id>/dashboard')
def client_dashboard(client_id):
    # Query the Plan table for the given client
    plan_response = supabase.table('Plan').select('*').eq('ClientId', client_id).execute()
    
    
    plans = plan_response.data
        # Categorize plans by LOC
    categorized_plans = {
        "Medical": [plan for plan in plans if plan['LOC'] == 'Medical'],
        "Dental": [plan for plan in plans if plan['LOC'] == 'Dental'],
        "Vision": [plan for plan in plans if plan['LOC'] == 'Vision']
        }
    
   
    
    # Filter active plans (only those with Status = Active)
    active_plans ={"Active": [plan for plan in plans if plan['Status'] == 'Active']}
    
    active_plan_names = [
        {
            'PlanId': plan['PlanId'],
            'PlanName': plan['PlanName'],
            'StartDate': None,
            'EndDate': None
        }
        for plan in active_plans['Active']
    ]

    session['active_plan_names']=active_plan_names

    # Render dashboard with categorized plans
    return render_template('client_dashboard.html', client_id=client_id, plans=categorized_plans,active_plan_names=active_plan_names)

@app.route('/client/<int:client_id>/build', methods=['GET', 'POST'])
def build_init(client_id):
    # Create an instance of the form
    form = BuildInitForm()

    # Retrieve active plans passed from the session
    active_plans = session.get('active_plan_names', [])
    if isinstance(active_plans, str):
        import json
        active_plans = json.loads(active_plans)

    # Initialize form data to avoid 'NoneType' errors
    if not form.active_plans.data:
        form.active_plans.data = []
    
    # Dynamically populate the active plan choices
    form.active_plans.choices = [(plan['PlanId'], plan['PlanName']) for plan in active_plans]

    # Handle form submission
    if form.validate_on_submit():
        
        # Retrieve the start and end dates
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        
        # Retrieve selected active plans
        selected_active_plan_ids = form.active_plans.data  # List of selected plan IDs
        


        # Filter active plans to only include those selected by the user
        selected_active_plans = [
            {
                'PlanId': plan['PlanId'],
                'PlanName': plan['PlanName'],
                'StartDate': str(start_date),  # Convert to string if necessary
                'EndDate': str(end_date)       # Convert to string if necessary
            }
            for plan in active_plans
            if plan['PlanId'] in selected_active_plan_ids
        ]
        
        
        # Retrieve the number of new plans entered
        new_plans = {
            'Self-Funded': {
                'Medical': form.self_funded_medical.data,
                'Dental': form.self_funded_dental.data,
                'Vision': form.self_funded_vision.data,
            },
            'Fully-Insured': {
                'Medical': form.fully_insured_medical.data,
                'Dental': form.fully_insured_dental.data,
                'Vision': form.fully_insured_vision.data,
            },
            'Level-Funded': {
                'Medical': form.level_funded_medical.data,
                'Dental': form.level_funded_dental.data,
                'Vision': form.level_funded_vision.data,
            },
            'Minimum-Premium': {
                'Medical': form.min_prem_medical.data,
                'Dental': form.min_prem_dental.data,
                'Vision': form.min_prem_vision.data,
            }
        }
        
        generated_plans = [
            {
                'name': f"{coverage}_{funding_type}_{i}",
                'funding_type': funding_type,
                'coverage': coverage,
                'start_date': start_date,
                'end_date':end_date
            }
            for funding_type, coverages in new_plans.items()
            for coverage, count in coverages.items()
            if count and count > 0
            for i in range(1, count + 1)
        ]

        # Debug: Print the generated plans
        print("Generated Plans:", generated_plans)

        # Store generated plans in the session
        session['generated_plans'] = generated_plans

        
        # Combine selected active plans and generated plans
        available_plans = selected_active_plans
        
        # Update available_plans to include generated plans in the desired format
        for plan in generated_plans:
            available_plans.append({
            'PlanId': None,  # Placeholder for new plans
            'PlanName': plan['name'],
            'StartDate': plan['start_date'],
            'EndDate': plan['end_date']
        })

        

        # Store data in session for the next page
        session['available_plans'] = available_plans

        print(available_plans)
        
        # Redirect to the next page (tier_structure)
        return redirect(url_for('tier_structure', client_id=client_id))
    
    # Render the template with the form
    
    
    return render_template('build_init.html', client_id=client_id, form=form)


@app.route('/client/<int:client_id>/tier', methods=['GET', 'POST'])
def tier_structure(client_id):
    form = TierStructureForm()

    # Retrieve available plans from the session
    available_plans = session.get('available_plans', [])
    print("Available Plans in Tier Structure:", available_plans)

    if request.method == 'POST':
        from collections import defaultdict

        # Store tier data
        plan_tier_data = defaultdict(lambda: {"tier_count": None, "tiers": {}, "plans": []})

        # Normalize form keys
        normalized_form = {}
        for key, value in request.form.items():
            if key == "number_of_tiers":
                normalized_form["tier_count_1"] = value
            else:
                normalized_form[key] = value

        # Dynamically process tier structures
        for key, value in normalized_form.items():
            if key.startswith("tier_count_"):
                structure_id = int(key.split("_")[2])
                plan_tier_data[structure_id]["tier_count"] = int(value)

            elif key.startswith("choose_tier_"):  # Process Tier Names
                structure_id, tier_index = map(int, key.split("_")[2:])
                tier_key = f"Tier {tier_index}"
                if tier_key not in plan_tier_data[structure_id]["tiers"]:
                    plan_tier_data[structure_id]["tiers"][tier_key] = {"tier_name": None, "single_family": None}
                plan_tier_data[structure_id]["tiers"][tier_key]["tier_name"] = value

            elif key.startswith("single_family_"):  # Process Single/Family Designation
                structure_id, tier_index = map(int, key.split("_")[2:])
                tier_key = f"Tier {tier_index}"
                if tier_key not in plan_tier_data[structure_id]["tiers"]:
                    plan_tier_data[structure_id]["tiers"][tier_key] = {"tier_name": None, "single_family": None}
                plan_tier_data[structure_id]["tiers"][tier_key]["single_family"] = value

            elif key.startswith("selected_plans_"):  # Process Selected Plans
                structure_id = int(key.split("_")[2])
                plan_tier_data[structure_id]["plans"] = request.form.getlist(key)

        # Save the tier data to the session
        session['tier_data'] = dict(plan_tier_data)
        print("Processed Tier Data:", plan_tier_data)  # Debug print statement

        return redirect(url_for('rate_structure', client_id=client_id))

    return render_template('tier_init.html', form=form, client_id=client_id, available_plans=available_plans)



@app.route('/client/<int:client_id>/rate', methods=['GET', 'POST'])
def rate_structure(client_id):
    # Retrieve available plans from the session
    available_plans = session.get('available_plans', [])
    print("Available Plans in Rate Structure:", available_plans)

    # Initialize the form
    form = RateStructuresForm()

    # Dynamically populate choices for `selected_plans`
    plan_choices = [
    (str(plan['PlanId']) if plan['PlanId'] else plan['PlanName'], plan['PlanName'])
    for plan in available_plans
    ]
    for rate_form in form.rate_structures.entries:
        rate_form.selected_plans.choices = plan_choices


    if request.method == 'POST':
        from collections import defaultdict

        # Store rate data
        rate_data = defaultdict(lambda: {"rate_name": None, "options": [], "plans": []})

    

        # Process form fields
        for key, value in request.form.items():
            if key.startswith("rate_structures-"):
                # Split the key into parts
                parts = key.split("-")
                print(f"Processing Key: {key}, Parts: {parts}")  # Debugging

                # Ensure the key has at least three parts
                if len(parts) >= 3:
                    index = int(parts[1])  # Rate structure index
                    field_name = parts[2]  # Field name (e.g., rate_name, summary_options, plans)
                    print(f"Index: {index}, Field Name: {field_name}")

                    # Initialize the structure in rate_data if not already present
                    if index not in rate_data:
                        rate_data[index] = {"rate_name": None, "options": [], "plans": []}

                    # Process rate_name
                    if field_name == "rate_name":
                        rate_name = value.strip()
                        if rate_name:  # Only add rate structures with a valid name
                            rate_data[index]["rate_name"] = rate_name
                            print(f"Set rate_name for index {index}: {rate_name}")

                    # Process summary_options
                    elif "summary_options" in field_name:
                        if value.strip():
                            rate_data[index]["options"].append(value.strip())
                            print(f"Added summary_option for index {index}: {value.strip()}")

                    # Process plans
                    elif field_name == "plans":
                        selected_plans = request.form.getlist(key)  # Capture all selected plans
                        print(f"Selected Plans for {key}: {selected_plans}")  # Debugging

                        for selected_plan in selected_plans:
                            # Match selected_plan with available_plans
                            linked_plan = None
                            for plan in available_plans:
                                if str(plan['PlanId']) == selected_plan:
                                    linked_plan = plan['PlanId']
                                    break
                                elif plan['PlanName'] == selected_plan:
                                    linked_plan = plan['PlanName']
                                    break

                            if linked_plan is not None:
                                rate_data[index]["plans"].append(linked_plan)
                                print(f"Linked Plan for index {index}: {linked_plan}")


        
        # Save the rate data to the session or database
        session['rate_data'] = rate_data
        print(rate_data)

        # Redirect to the next page or overview
        return redirect(url_for('plan_overview', client_id=client_id))

    # Render the form with the current CSRF token
    return render_template(
        'rate_structure.html',
        client_id=client_id,
        form=form,
        available_plans=available_plans,
        csrf_token=generate_csrf()
    )




from itertools import product
from collections import defaultdict

@app.route('/client/<int:client_id>/plan_overview', methods=['GET'])
def plan_overview(client_id):
    csrf_token = generate_csrf()

    # Fetch carrier data
    carriers_query = supabase.table('Carrier').select('*').execute()
    carriers_data = carriers_query.data if carriers_query.data else []

    # Organize carriers by line of coverage
    carriers_by_loc = {
        'Medical': [c['CarrierName'] for c in carriers_data if c.get('Medical') == 1],
        'Dental': [c['CarrierName'] for c in carriers_data if c.get('Dental') == 1],
        'Vision': [c['CarrierName'] for c in carriers_data if c.get('Vision') == 1],
        'Stop Loss': [c['CarrierName'] for c in carriers_data if c.get('StopLoss') == 1],
        'Rx Carve Out': [c['CarrierName'] for c in carriers_data if c.get('RxCarveOut') == 1],
    }

    # Initialize plan_data
    plan_data = defaultdict(dict)
    

    # Retrieve data from session
    active_plans = session.get('available_plans', [])
    rate_data = session.get('rate_data', {})
    tier_data = session.get('tier_data', {})
    generated_plans = session.get('generated_plans', [])

    # Combine active plans and generated plans into one loop
    for plan in active_plans:
        plan_id = plan['PlanId']
        plan_name = plan['PlanName']
        start_date = plan.get('StartDate')
        end_date = plan.get('EndDate')

        if plan_id is not None:
            # Fetch details for existing plans from the database
            plan_query = supabase.table('Plan').select('PlanName', 'FundingType', 'PlanType', 'LOC', 'PrimaryCarrierName').eq('PlanId', plan_id).execute()
            if plan_query.data:
                plan_data[plan_id] = {
                    'name': plan_query.data[0]['PlanName'],
                    'funding_type': plan_query.data[0]['FundingType'],
                    'plan_type': plan_query.data[0]['PlanType'],
                    'loc': plan_query.data[0]['LOC'],
                    'carrier': plan_query.data[0]['PrimaryCarrierName'],
                    'start_date': start_date,
                    'end_date': end_date
                }
        else:
            # For new plans, fetch details from generated_plans
            matching_generated_plan = next((p for p in generated_plans if p['name'] == plan_name), None)
            if matching_generated_plan:
                plan_data[plan_name] = {
                    'name': matching_generated_plan['name'],
                    'funding_type': matching_generated_plan['funding_type'],
                    'loc': matching_generated_plan['coverage'],
                    'start_date': start_date,
                    'end_date': end_date
                }

    # Map tier data to plans
    for structure_id, structure_info in tier_data.items():
        for plan_id in structure_info["plans"]:
            plan_id = int(plan_id) if isinstance(plan_id, str) and plan_id.isdigit() else plan_id
            if plan_id in plan_data:
                plan_data[plan_id]["tiers"] = structure_info["tiers"]

    # Generate rate combinations for all plans
    for plan_id, plan_info in plan_data.items():
        rate_names = [
            rate_data[key]["options"]
            for key in rate_data
            if plan_id in rate_data[key].get("plans", []) or plan_info["name"] in rate_data[key].get("plans", [])
        ]
        plan_info["rate_combinations"] = [
            "/".join(combo) for combo in product(*rate_names)
        ]

    print(plan_data)  # Debugging: Print final plan_data for verification
    
    # Render the template
    return render_template(
        'plan_overview.html',
        client_id=client_id,
        plan_data=plan_data,
        tier_data=tier_data,
        plan_rate_data=rate_data,
        carriers_by_loc=carriers_by_loc,
        csrf_token=csrf_token
    )

@app.route('/client/<int:client_id>/save_plans', methods=['POST'])
def save_plan_overview(client_id):
    from collections import defaultdict
    import json

    try:
        # Parse form data
        submitted_data = request.form.to_dict(flat=False)
        print(f"Request form data: {json.dumps(submitted_data, indent=2)}")

        # Retrieve tier data from session
        tier_data = session.get('tier_data', {})
        print(f"Retrieved Tier Data from Session: {json.dumps(tier_data, indent=2)}")

        # Parse plans from the submitted data
        plans_data = defaultdict(dict)
        
        tier_name_mapping = defaultdict(dict)
        hsa_data = {}
        
        
        for tier_set in tier_data.values():
            plans = tier_set.get("plans", [])
            tiers = tier_set.get("tiers", {})
            for plan in plans:
                for tier_name, tier_info in tiers.items():
                    if tier_info.get("tier_name"):
                        tier_name_mapping[plan][tier_name] = tier_info["tier_name"]

        for key, value in submitted_data.items():
            if key.startswith("plans["):
                plan_key = key.split("[")[1].split("]")[0].rsplit("_", 1)[0]
                attribute_key = key.split("][")[1].replace("]", "")
                plans_data[plan_key][attribute_key] = value[0]
            elif key.startswith("hsa_"):
                hsa_key_parts = key.split("_", 1)[1]
                hsa_data[hsa_key_parts] = float(value[0]) if value and value[0] else None
                
        
        # Structure plans for the Plan table
        structured_plans = []
        for plan_key, attributes in plans_data.items():
            structured_plans.append({
                "PlanName": attributes.get("plan_name"),
                "ClientId": client_id,
                "LOC": attributes.get("loc"),
                "PrimaryCarrierName": attributes.get("primary_carrier"),
                "AltCarrierName": attributes.get("alternate_carrier"),
                "FundingType": attributes.get("funding_type"),
                "PlanType": attributes.get("plan_type").strip(),
                "EffDate": attributes.get("start_date"),
                "CloseDate": None,
                "Status": "Active",
            })

        # Fetch existing plans
        existing_plans_query = supabase.table("Plan").select("PlanName, LOC, ClientId").eq("ClientId", client_id).execute()
        existing_plans = {(plan["PlanName"], plan["LOC"], plan["ClientId"]) for plan in existing_plans_query.data}

        # Identify new plans to insert
        new_plans = []
        for plan in structured_plans:
            if (plan["PlanName"], plan["LOC"], plan["ClientId"]) not in existing_plans:
                new_plans.append(plan)

        # Insert new plans
        if new_plans:
            response = supabase.table("Plan").insert(new_plans).execute()

        # Refresh all_plans after inserting new plans
        all_plans_query = supabase.table("Plan").select("PlanId, PlanName").eq("ClientId", client_id).execute()
        all_plans = {plan["PlanName"]: plan["PlanId"] for plan in all_plans_query.data}

        # Fetch existing premium data
        existing_premiums_query = supabase.table("Premium").select("*").eq("ClientId", client_id).execute()
        existing_premiums = {
            f"{row['PlanId']}_{row['ClientId']}_{row['StartDate']}_{row['SystemTierTrans']}_{row['TierName']}_{row['RateDescription']}": row
            for row in existing_premiums_query.data
        }

        # Process premiums and contributions
        premium_rows_to_insert = []
        premium_rows_to_update = []

        # Process all premium rows
        for key, values in submitted_data.items():
            if key.startswith("premium_"):
                key_parts = key.split("_")
                tier_number = f"{key_parts[1]} {key_parts[2]}"
                plan_identifier = "_".join(key_parts[3:-2])
                rate_description = key_parts[-1]

                if plan_identifier in plans_data:
                    plan_name = plans_data[plan_identifier]["plan_name"]
                    plan_type = plans_data[plan_identifier].get("plan_type", "").strip().upper()
                    plan_id = all_plans.get(plan_name)

                    if not plan_id:
                        continue

                    system_tier_trans = tier_number
                    prem_amt = float(values[0]) if values else None
                    hsa_amt_annual = hsa_data.get(key.split("_", 1)[1], None) if plan_type == "HDHP - HSA" else None

                    premium_key = f"{plan_id}_{client_id}_{plans_data[plan_identifier].get('start_date')}_{system_tier_trans}_{tier_number}_{rate_description}"

                    # Check if this premium already exists in the database
                    if premium_key in existing_premiums:
                        premium_rows_to_update.append({
                            "PremiumId": existing_premiums[premium_key]["PremiumId"],
                            "PremAmt": prem_amt,
                            "HSA_Amt_Annual": hsa_amt_annual,
                        })
                    else:
                        premium_rows_to_insert.append({
                            "PlanId": plan_id,
                            "ClientId": client_id,
                            "StartDate": plans_data[plan_identifier].get("start_date"),
                            "EndDate": plans_data[plan_identifier].get("end_date"),
                            "SystemTierTrans": system_tier_trans,
                            "TierName": tier_name_mapping.get(plan_identifier, {}).get(system_tier_trans, "Unknown"),
                            "RateDescription": rate_description,
                            "PremAmt": prem_amt,
                            "PremFreq": "Monthly",
                            "PremAmt_Annual": prem_amt * 12 if prem_amt else None,
                            "Ctr_Amt": None,  # Placeholder for contribution, to be updated later
                            "Ctr_Amt_Annual": None,  # Placeholder for contribution, to be updated later
                            "HSA_Elig": "Yes" if plan_type == "HDHP - HSA" else "No",
                            "HSA_Freq_Pref": "Annual" if plan_type == "HDHP - HSA" else None,
                            "HSA_Amt_Annual": hsa_amt_annual,
                        })

        # Now, process all contribution rows and match them to premiums
        for key, values in submitted_data.items():
            if key.startswith("contribution_"):
                key_parts = key.split("_")
                tier_number = f"{key_parts[1]} {key_parts[2]}"
                plan_identifier = "_".join(key_parts[3:-2])
                rate_description = key_parts[-1]

                if plan_identifier in plans_data:
                    plan_name = plans_data[plan_identifier]["plan_name"]
                    plan_id = all_plans.get(plan_name)

                    if not plan_id:
                        continue

                    system_tier_trans = tier_number
                    contribution_value = float(values[0]) if values else None

                    # Find the matching premium key
                    premium_key = f"{plan_id}_{client_id}_{plans_data[plan_identifier].get('start_date')}_{system_tier_trans}_{tier_number}_{rate_description}"

                    # If we find a matching premium row, update it with the contribution value
                    if premium_key in existing_premiums:
                        premium_rows_to_update.append({
                            "PremiumId": existing_premiums[premium_key]["PremiumId"],
                            "Ctr_Amt": contribution_value,
                            "Ctr_Amt_Annual": contribution_value * 12 if contribution_value else None,
                        })

                    # If no existing premium, add it to the premium rows with the contribution value
                    else:
                        # Find the corresponding premium row in the ones we are inserting
                        for prem_row in premium_rows_to_insert:
                            if prem_row["PlanId"] == plan_id and prem_row["SystemTierTrans"] == system_tier_trans and prem_row["RateDescription"] == rate_description:
                                prem_row["Ctr_Amt"] = contribution_value
                                prem_row["Ctr_Amt_Annual"] = contribution_value * 12 if contribution_value else None
                                break

        

        # Insert new rows into Premium table
        if premium_rows_to_insert:
            supabase.table("Premium").insert(premium_rows_to_insert).execute()

        # Update existing rows in Premium table
        for update_row in premium_rows_to_update:
            supabase.table("Premium").update(update_row).eq("PremiumId", update_row["PremiumId"]).execute()

        
        # Step 1: Extract plan identifier from isl_carrier and prepare data structure
        isl_plan_identifiers = {}
        isl_data_to_insert = []

        # Iterate through all ISL fields in the submitted data
        for key, values in submitted_data.items():
            if key.startswith("isl_"):
                # Step 1: Extract the plan identifier from the 'isl_carrier' key
                if key.startswith("isl_carrier_"):
                    key_parts = key.split("_")
                    plan_identifier = "_".join(key_parts[2:-1])  # Extract everything except 'isl_carrier' and the last number

                    # Extract the field value for 'carrier'
                    field_value = values[0] if values else None

                    # Step 2: Get the plan name and fetch the PlanId from the database
                    plan_name = plans_data.get(plan_identifier, {}).get("plan_name")
                    if plan_name:
                        
                        plan_query = supabase.table("Plan").select("PlanId").eq("PlanName", plan_name).execute()
                        if plan_query.data:
                            plan_id = plan_query.data[0]["PlanId"]
                            isl_plan_identifiers[plan_identifier] = plan_id  # Store the PlanId for later use

                            # Create the ISL data row for the carrier field
                            isl_data = {
                                "PlanId": plan_id,
                                "ClientId": client_id,
                                "ISLStartDate": plans_data[plan_identifier].get("start_date"),
                                "ISLEndDate": plans_data[plan_identifier].get("end_date"),
                                "ISLCarrier": field_value  # Add carrier field value
                            }
                            # Add the row to the insert list for the carrier field
                            isl_data_to_insert.append(isl_data)

                # Step 3: Process other ISL fields based on the plan identifier and field name
                if plan_identifier in isl_plan_identifiers:
                    # Extract the field value (assuming the values list contains at least one value)
                    field_value = values[0] if values else None

                    # Step 4: Check for field names and update the corresponding ISL column
                    isl_data = next((item for item in isl_data_to_insert if item["PlanId"] == isl_plan_identifiers[plan_identifier]), None)

                    if isl_data:
                        # Field updates based on the key content
                        if 'contract' in key and plan_identifier in key:
                            isl_data["ISLContractType"] = field_value
                        elif 'isl_deductible' in key and plan_identifier in key:
                            isl_data["ISLDed"] = field_value
                        elif 'premium_ind__pepm' in key and plan_identifier in key:
                            isl_data["ISLPremSingle"] = field_value
                        elif 'premium_fam_pepm' in key and plan_identifier in key:
                            isl_data["ISLPremFamily"] = field_value
                        elif 'acc_policy' in key and plan_identifier in key:
                            isl_data["ISLAccumPolicy"] = field_value
                        elif 'isl_acc_deductible' in key and plan_identifier in key:
                            isl_data["ISLAccumDed"] = field_value if field_value else None
                        elif 'isl_max_deductible' in key and plan_identifier in key:
                            isl_data["ISLMaxReimb"] = field_value if field_value else None

                        
                    else:
                        # If the ISL data row doesn't exist, create a new one
                        isl_data = {
                            "PlanId": isl_plan_identifiers[plan_identifier],
                            "ClientId": client_id,
                            "ISLCarrier": None,  # Default value (could be updated if needed)
                            "ISLContractType": None,
                            "ISLDed": None,
                            "ISLPremSingle": None,
                            "ISLPremFamily": None,
                            "ISLAccumPolicy": None,
                            "ISLAccumDed": None,
                            "ISLMaxReimb": None
                        }

                        # Update the new ISL data row with the field value based on the key
                        if 'contract' in key:
                            isl_data["ISLContractType"] = field_value
                        elif 'isl_deductible' in key:
                            isl_data["ISLDed"] = field_value
                        elif 'premium_ind__pepm' in key:
                            isl_data["ISLPremSingle"] = field_value
                        elif 'premium_fam_pepm' in key:
                            isl_data["ISLPremFamily"] = field_value
                        elif 'acc_policy' in key:
                            isl_data["ISLAccumPolicy"] = field_value
                        elif 'acc_deductible' in key:
                            isl_data["ISLAccumDed"] = field_value if field_value else None
                        elif 'max_deductible' in key:
                            isl_data["ISLMaxReimb"] = field_value if field_value else None

                        # Add the new ISL data row to the insert list
                        isl_data_to_insert.append(isl_data)

                

        # Step 5: Insert all ISL data into the database
        if isl_data_to_insert:
            
            supabase.table("ISL Policy").insert(isl_data_to_insert).execute()


        # Step 1: Extract plan identifier from isl_carrier and prepare data structure
        asl_plan_identifiers = {}
        asl_data_to_insert = []
        
        asl_carrier_keys = [key for key in submitted_data if key.startswith("asl_carrier_")]
        
        asl_has_data = any(
            submitted_data[key] and any(value.strip() for value in submitted_data[key])  # Ensure non-empty string values
            for key in asl_carrier_keys
        )

        if asl_has_data:
            # Iterate through all ASL fields in the submitted data
            for key, values in submitted_data.items():
                if key.startswith("asl_"):
                    # Step 1: Extract the plan identifier from the 'asl_carrier' key
                    if key.startswith("asl_carrier_"):
                        key_parts = key.split("_")
                        plan_identifier = "_".join(key_parts[2:-1])  # Extract everything except 'asl_carrier' and the last number

                        # Extract the field value for 'carrier'
                        field_value = values[0] if values else None

                        # Step 2: Get the plan name and fetch the PlanId from the database
                        plan_name = plans_data.get(plan_identifier, {}).get("plan_name")
                        if plan_name:
                            
                            plan_query = supabase.table("Plan").select("PlanId").eq("PlanName", plan_name).execute()
                            if plan_query.data:
                                plan_id = plan_query.data[0]["PlanId"]
                                asl_plan_identifiers[plan_identifier] = plan_id  # Store the PlanId for later use

                                # Create the ASL data row for the carrier field
                                asl_data = {
                                    "PlanId": plan_id,
                                    "ClientId": client_id,
                                    "AggStartDate": plans_data[plan_identifier].get("start_date"),
                                    "AggEndDate": plans_data[plan_identifier].get("end_date"),
                                    "AggCarrier": field_value  # Add carrier field value
                                }
                                # Add the row to the insert list for the carrier field
                                asl_data_to_insert.append(asl_data)

                    # Step 3: Process other ASL fields based on the plan identifier and field name
                    if plan_identifier in asl_plan_identifiers:
                        # Extract the field value (assuming the values list contains at least one value)
                        field_value = values[0] if values else None

                        # Step 4: Check for field names and update the corresponding ISL column
                        asl_data = next((item for item in asl_data_to_insert if item["PlanId"] == asl_plan_identifiers[plan_identifier]), None)

                        if asl_data:
                            # Field updates based on the key content
                            if 'asl_expected_claim' in key and plan_identifier in key:
                                asl_data["AggExpClaims"] = field_value
                            elif 'asl_corridor' in key and plan_identifier in key:
                                asl_data["AggCorr"] = field_value
                            elif 'asl_premium_ind_pepm' in key and plan_identifier in key:
                                asl_data["AggPremSingle"] = field_value
                            elif 'asl_premium_fam_pepm' in key and plan_identifier in key:
                                asl_data["AggPremFamily"] = field_value
                            elif 'asl_max_reimbursement' in key and plan_identifier in key:
                                asl_data["AggMaxReimb"] = field_value
                            
                            
                        else:
                            # If the ISL data row doesn't exist, create a new one
                            asl_data = {
                                "PlanId": isl_plan_identifiers[plan_identifier],
                                "ClientId": client_id,
                                "ASLCarrier": None,  # Default value (could be updated if needed)
                                
                            }

                            # Update the new ISL data row with the field value based on the key
                            if 'expected_claim' in key and plan_identifier in key:
                                asl_data["AggExpClaims"] = field_value
                            elif 'corridor' in key and plan_identifier in key:
                                asl_data["AggCorr"] = field_value
                            elif 'premium_ind' in key and plan_identifier in key:
                                asl_data["AggPremSingle"] = field_value
                            elif 'premium_fam' in key and plan_identifier in key:
                                asl_data["AggPremFamily"] = field_value
                            elif 'max_reimbursement' in key and plan_identifier in key:
                                asl_data["AggMaxReimb"] = field_value
                            

                            # Add the new ISL data row to the insert list
                            asl_data_to_insert.append(asl_data)

                    

            # Step 5: Insert all ASL data into the database
            if asl_data_to_insert:
                
                supabase.table("ASL Policy").insert(asl_data_to_insert).execute()
        else:
            print("SKIP ASL")
            
        # Step 1: Extract plan identifier from fee and prepare data structure
        # Step 1: Extract plan identifier from fee and prepare data structure
        fee_plan_identifiers = {}
        fee_data_to_insert = {}

        # Iterate through all fee fields in the submitted data
        for key, values in submitted_data.items():
            if key.startswith("fees_"):
                key_parts = key.split("_")
                
                # Extract the plan identifier (everything except 'fees_category', 'fees_description', 'fees_pepm' and the fee index)
                plan_identifier = "_".join(key_parts[2:-2])  
                
                # Extract fee index (last part of the key, ensures multiple fees are processed separately)
                fee_index = key_parts[-1]  

                # Initialize a dictionary to store fee data per fee index
                if plan_identifier not in fee_data_to_insert:
                    fee_data_to_insert[plan_identifier] = {}

                if fee_index not in fee_data_to_insert[plan_identifier]:
                    fee_data_to_insert[plan_identifier][fee_index] = {
                        "PlanId": None,  # Will be filled later
                        "ClientId": client_id,
                        "StartDate": plans_data.get(plan_identifier, {}).get("start_date"),
                        "EndDate": plans_data.get(plan_identifier, {}).get("end_date"),
                        "Category": None,
                        "FeeDesc": None,
                        "FeeAmt": None,
                        "FeeAmt_Annual": None,
                    }

                # Extract and assign values correctly
                field_value = values[0] if values else None

                if key.startswith("fees_category_"):
                    fee_data_to_insert[plan_identifier][fee_index]["Category"] = field_value

                elif key.startswith("fees_description_"):
                    fee_data_to_insert[plan_identifier][fee_index]["FeeDesc"] = field_value

                elif key.startswith("fees_pepm_"):
                    fee_data_to_insert[plan_identifier][fee_index]["FeeAmt"] = field_value
                    if field_value:  # Convert PEPM to Annual Amount
                        fee_data_to_insert[plan_identifier][fee_index]["FeeAmt_Annual"] = float(field_value) * 12

        # Step 2: Fetch PlanId for each plan and update the data structure
        for plan_identifier in fee_data_to_insert:
            plan_name = plans_data.get(plan_identifier, {}).get("plan_name")
            
            if plan_name:
                plan_query = supabase.table("Plan").select("PlanId").eq("PlanName", plan_name).execute()
                
                if plan_query.data:
                    plan_id = plan_query.data[0]["PlanId"]
                    fee_plan_identifiers[plan_identifier] = plan_id  

                    # Assign PlanId to all corresponding fees
                    for fee_index in fee_data_to_insert[plan_identifier]:
                        fee_data_to_insert[plan_identifier][fee_index]["PlanId"] = plan_id

        # Step 3: Filter out invalid fees (those with "Select Fee Type" in Category)
        valid_fees = []
        for plan_identifier, fee_entries in fee_data_to_insert.items():
            for fee_index, fee_data in fee_entries.items():
                if fee_data["Category"] and fee_data["Category"] != "Select Fee Type":
                    valid_fees.append(fee_data)

        # Step 4: Insert all valid fee data into the database
        if valid_fees:
            print(f"Inserting Fee Data: {json.dumps(valid_fees, indent=2)}")
            supabase.table("Fee").insert(valid_fees).execute()

        # Fetch existing premium data
        existing_admin_query = supabase.table("LF Rate Detail").select("*").eq("ClientId", client_id).execute()
        existing_admin = {
            f"{row['RateId']}_{row['PlanId']}_{row['ClientId']}_{row['StartDate']}_{row['SystemTierTrans']}_{row['Component']}": row
            for row in existing_admin_query.data
        }
        
        LF_admin_rows_to_insert = []
        LF_admin_rows_to_update = []

        # Process all lf admin rows
        for key, values in submitted_data.items():
            if key.startswith("Admin_Fees_"):
                
                key_parts = key.split("_")
                system_tier_trans = f"{key_parts[2]} {key_parts[3]}"
                
                plan_identifier = "_".join(key_parts[4:-1])
                
                field_value=values[0]
                

                if plan_identifier in plans_data:
                    plan_name = plans_data[plan_identifier]["plan_name"]
                    plan_type = plans_data[plan_identifier].get("plan_type", "").strip().upper()
                    plan_id = all_plans.get(plan_name)

                    if not plan_id:
                        continue

                    
                    
                    

                    admin_key = f"{plan_id}_{client_id}_{plans_data[plan_identifier].get('start_date')}_{system_tier_trans}_'Admin Fee'"
                    
                    # Check if this premium already exists in the database
                    if admin_key in existing_admin:
                        LF_admin_rows_to_update.append({
                            "RateId": existing_premiums[admin_key]["RateId"],
                            "RateAmt": field_value,
                            "RateAmt_Annual": field_value * 12,
                        })
                    else:
                        LF_admin_rows_to_insert.append({
                            "PlanId": plan_id,
                            "ClientId": client_id,
                            "StartDate": plans_data[plan_identifier].get("start_date"),
                            "EndDate": plans_data[plan_identifier].get("end_date"),
                            "SystemTierTrans": system_tier_trans,
                            "Component": "Admin Fee",
                            "RateAmt": field_value,
                            
                            "RateFreq": "Monthly",
                            "RateAmt_Annual": float(field_value) * 12 ,
                            
                        })

        
    

        # Insert new rows into lf table
        if LF_admin_rows_to_insert:
            supabase.table("LF Rate Detail").insert(LF_admin_rows_to_insert).execute()

        # Update existing rows in lf table
        for update_row in LF_admin_rows_to_update:
            supabase.table("LF Rate Detail").update(update_row).eq("RateId", update_row["RateId"]).execute()


        # Fetch existingdata
        existing_lf_isl_query = supabase.table("LF Rate Detail").select("*").eq("ClientId", client_id).execute()
        existing_lf_isl = {
            f"{row['RateId']}_{row['PlanId']}_{row['ClientId']}_{row['StartDate']}_{row['SystemTierTrans']}_{row['Component']}": row
            for row in existing_lf_isl_query.data
        }

        LF_isl_rows_to_insert = []
        LF_isl_rows_to_update = []

        # Process all lf admin rows
        for key, values in submitted_data.items():
            if key.startswith("Individual_Stop_Loss_"):
                
                key_parts = key.split("_")
                system_tier_trans = f"{key_parts[3]} {key_parts[4]}"
                print(system_tier_trans)
                plan_identifier = "_".join(key_parts[5:-1])
                
                field_value=values[0]
                

                if plan_identifier in plans_data:
                    plan_name = plans_data[plan_identifier]["plan_name"]
                    plan_type = plans_data[plan_identifier].get("plan_type", "").strip().upper()
                    plan_id = all_plans.get(plan_name)

                    if not plan_id:
                        continue

                    
                    
                    

                    lf_isl_key = f"{plan_id}_{client_id}_{plans_data[plan_identifier].get('start_date')}_{system_tier_trans}_'Individual Stop Loss'"
                    
                    # Check if this premium already exists in the database
                    if lf_isl_key in existing_lf_isl:
                        LF_isl_rows_to_update.append({
                            "RateId": existing_lf_isl[lf_isl_key]["RateId"],
                            "RateAmt": field_value,
                            "RateAmt_Annual": field_value * 12,
                        })
                    else:
                        LF_isl_rows_to_insert.append({
                            "PlanId": plan_id,
                            "ClientId": client_id,
                            "StartDate": plans_data[plan_identifier].get("start_date"),
                            "EndDate": plans_data[plan_identifier].get("end_date"),
                            "SystemTierTrans": system_tier_trans,
                            "Component": "Individual Stop Loss",
                            "RateAmt": field_value,
                            
                            "RateFreq": "Monthly",
                            "RateAmt_Annual": float(field_value) * 12 ,
                            
                        })

        
        # Print debug information for inserted rows
        print(f"LF Rows to Insert: {json.dumps(LF_isl_rows_to_insert, indent=2)}")
        print(f"LF Rows to Update: {json.dumps(LF_isl_rows_to_update, indent=2)}")

        # Insert new rows into lf table
        if LF_isl_rows_to_insert:
            supabase.table("LF Rate Detail").insert(LF_isl_rows_to_insert).execute()

        # Update existing rows in lf t
        for update_row in LF_isl_rows_to_update:
            supabase.table("LF Rate Detail").update(update_row).eq("RateId", update_row["RateId"]).execute()

        # Fetch existingdata
        existing_lf_asl_query = supabase.table("LF Rate Detail").select("*").eq("ClientId", client_id).execute()
        existing_lf_asl = {
            f"{row['RateId']}_{row['PlanId']}_{row['ClientId']}_{row['StartDate']}_{row['SystemTierTrans']}_{row['Component']}": row
            for row in existing_lf_isl_query.data
        }

        LF_asl_rows_to_insert = []
        LF_asl_rows_to_update = []

        # Process all lf admin rows
        for key, values in submitted_data.items():
            if key.startswith("Aggregate_Stop_Loss_"):
                
                key_parts = key.split("_")
                system_tier_trans = f"{key_parts[3]} {key_parts[4]}"
                print(system_tier_trans)
                plan_identifier = "_".join(key_parts[5:-1])
                print(plan_identifier)
                field_value=values[0]
                

                if plan_identifier in plans_data:
                    plan_name = plans_data[plan_identifier]["plan_name"]
                    plan_type = plans_data[plan_identifier].get("plan_type", "").strip().upper()
                    plan_id = all_plans.get(plan_name)

                    if not plan_id:
                        continue

                    
                    
                    

                    lf_asl_key = f"{plan_id}_{client_id}_{plans_data[plan_identifier].get('start_date')}_{system_tier_trans}_'Aggregate Stop Loss'"
                    
                    # Check if this premium already exists in the database
                    if lf_asl_key in existing_lf_asl_query:
                        LF_asl_rows_to_update.append({
                            "RateId": existing_lf_asl[lf_asl_key]["RateId"],
                            "RateAmt": field_value,
                            "RateAmt_Annual": field_value * 12,
                        })
                    else:
                        LF_asl_rows_to_insert.append({
                            "PlanId": plan_id,
                            "ClientId": client_id,
                            "StartDate": plans_data[plan_identifier].get("start_date"),
                            "EndDate": plans_data[plan_identifier].get("end_date"),
                            "SystemTierTrans": system_tier_trans,
                            "Component": "Aggregate Stop Loss",
                            "RateAmt": field_value,
                            
                            "RateFreq": "Monthly",
                            "RateAmt_Annual": float(field_value) * 12 ,
                            
                        })

        
        # Print debug information for inserted rows
        print(f"LF Rows to Insert: {json.dumps(LF_asl_rows_to_insert, indent=2)}")
        print(f"LF Rows to Update: {json.dumps(LF_asl_rows_to_update, indent=2)}")

        # Insert new rows into lf table
        if LF_asl_rows_to_insert:
            supabase.table("LF Rate Detail").insert(LF_asl_rows_to_insert).execute()

        # Update existing rows in lf t
        for update_row in LF_asl_rows_to_update:
            supabase.table("LF Rate Detail").update(update_row).eq("RateId", update_row["RateId"]).execute()


        

        # Fetch existingdata
        existing_lf_claims_query = supabase.table("LF Rate Detail").select("*").eq("ClientId", client_id).execute()
        existing_lf_claims = {
            f"{row['RateId']}_{row['PlanId']}_{row['ClientId']}_{row['StartDate']}_{row['SystemTierTrans']}_{row['Component']}": row
            for row in existing_lf_isl_query.data
        }

        LF_claims_rows_to_insert = []
        LF_claims_rows_to_update = []

        # Process all lf admin rows
        for key, values in submitted_data.items():
            if key.startswith("Claims_Funding_Budget_"):
                print(key)
                key_parts = key.split("_")
                system_tier_trans = f"{key_parts[3]} {key_parts[4]}"
                print(system_tier_trans)
                plan_identifier = "_".join(key_parts[5:-1])
                print(plan_identifier)
                field_value=values[0]
                

                if plan_identifier in plans_data:
                    plan_name = plans_data[plan_identifier]["plan_name"]
                    plan_type = plans_data[plan_identifier].get("plan_type", "").strip().upper()
                    plan_id = all_plans.get(plan_name)

                    if not plan_id:
                        continue

                    
                    
                    

                    lf_claims_key = f"{plan_id}_{client_id}_{plans_data[plan_identifier].get('start_date')}_{system_tier_trans}_'Aggregate Stop Loss'"
                    
                    # Check if this premium already exists in the database
                    if lf_claims_key in existing_lf_claims_query:
                        LF_claims_rows_to_update.append({
                            "RateId": existing_lf_claims[lf_claims_key]["RateId"],
                            "RateAmt": field_value,
                            "RateAmt_Annual": field_value * 12,
                        })
                    else:
                        LF_claims_rows_to_insert.append({
                            "PlanId": plan_id,
                            "ClientId": client_id,
                            "StartDate": plans_data[plan_identifier].get("start_date"),
                            "EndDate": plans_data[plan_identifier].get("end_date"),
                            "SystemTierTrans": system_tier_trans,
                            "Component": "Claims Funding Budget",
                            "RateAmt": field_value,
                            
                            "RateFreq": "Monthly",
                            "RateAmt_Annual": float(field_value) * 12 ,
                            
                        })

        
        # Print debug information for inserted rows
        print(f"LF Rows to Insert: {json.dumps(LF_claims_rows_to_insert, indent=2)}")
        print(f"LF Rows to Update: {json.dumps(LF_claims_rows_to_update, indent=2)}")

        # Insert new rows into lf table
        if LF_claims_rows_to_insert:
            supabase.table("LF Rate Detail").insert(LF_claims_rows_to_insert).execute()

        # Update existing rows in lf t
        for update_row in LF_claims_rows_to_update:
            supabase.table("LF Rate Detail").update(update_row).eq("RateId", update_row["RateId"]).execute()


        
        
        
        # Fetch existingdata
        existing_lf_rebate_query = supabase.table("LF Rate Detail").select("*").eq("ClientId", client_id).execute()
        existing_lf_rebate = {
            f"{row['RateId']}_{row['PlanId']}_{row['ClientId']}_{row['StartDate']}_{row['SystemTierTrans']}_{row['Component']}": row
            for row in existing_lf_rebate_query.data
        }

        LF_rebate_rows_to_insert = []
        LF_rebate_rows_to_update = []

        # Process all lf admin rows
        for key, values in submitted_data.items():
            if key.startswith("Rx_Rebate_Offset_"):
                print(key)
                key_parts = key.split("_")
                system_tier_trans = f"{key_parts[3]} {key_parts[4]}"
                print(system_tier_trans)
                plan_identifier = "_".join(key_parts[5:-1])
                print(plan_identifier)
                field_value=values[0]
                

                if plan_identifier in plans_data:
                    plan_name = plans_data[plan_identifier]["plan_name"]
                    plan_type = plans_data[plan_identifier].get("plan_type", "").strip().upper()
                    plan_id = all_plans.get(plan_name)

                    if not plan_id:
                        continue

                    
                    
                    

                    lf_rebate_key = f"{plan_id}_{client_id}_{plans_data[plan_identifier].get('start_date')}_{system_tier_trans}_'Aggregate Stop Loss'"
                    
                    # Check if this premium already exists in the database
                    if lf_rebate_key in existing_lf_rebate_query:
                        LF_claims_rows_to_update.append({
                            "RateId": existing_lf_claims[lf_claims_key]["RateId"],
                            "RateAmt": field_value*-1,
                            "RateAmt_Annual": field_value * -12,
                        })
                    else:
                        LF_rebate_rows_to_insert.append({
                            "PlanId": plan_id,
                            "ClientId": client_id,
                            "StartDate": plans_data[plan_identifier].get("start_date"),
                            "EndDate": plans_data[plan_identifier].get("end_date"),
                            "SystemTierTrans": system_tier_trans,
                            "Component": "Rx Rebate Offset",
                            "RateAmt": float(field_value)*-1,
                            
                            "RateFreq": "Monthly",
                            "RateAmt_Annual": float(field_value) * -12 ,
                            
                        })

        
        

        # Insert new rows into lf table
        if LF_rebate_rows_to_insert:
            supabase.table("LF Rate Detail").insert(LF_rebate_rows_to_insert).execute()

        # Update existing rows in lf t
        for update_row in LF_rebate_rows_to_update:
            supabase.table("LF Rate Detail").update(update_row).eq("RateId", update_row["RateId"]).execute()

        #FI Details
        insured_policy_rows_to_insert = []
        insured_policy_rows_to_update = []

        # Fetch existing insured policy data
        existing_insured_policies_query = supabase.table("Insured Policy Details").select("*").eq("ClientId", client_id).execute()
        existing_insured_policies = {
            row["PlanId"]: row for row in existing_insured_policies_query.data
        }

        # Fetch plan data to get LOC values
        plans_with_loc_query = supabase.table("Plan").select("PlanId, LOC").eq("ClientId", client_id).execute()
        plans_with_loc = {plan["PlanId"]: plan["LOC"] for plan in plans_with_loc_query.data}

        # Create a mapping to aggregate values by PlanId
        insured_policy_data = defaultdict(lambda: {
            "PlanId": None,
            "ClientId": client_id,
            "StartDate": None,
            "EndDate": None,
            "LOC": None,
            "RetentionPEPM": None,
            "ClaimsPEPM": None,
            "RxRebateOffsetPEPM": None,
            "PoolingLevel": None,
            "PoolingFeePEPM": None,
        })

        # Process all insured policy rows
        for key, values in submitted_data.items():
            if key.startswith(("retention_pepm_", "claims_funding_", "rebate_pepm_", "pooling_level_", "pooling_pepm_")):
                key_parts = key.split("_")
                plan_identifier = "_".join(key_parts[2:-1])  # Extract plan identifier
                field_name = "_".join(key_parts[:2])  # Determine which field this corresponds to (e.g., retention_pepm)
                field_value = values[0]  # Retrieve the value submitted for this field

                if plan_identifier in plans_data:
                    plan_name = plans_data[plan_identifier]["plan_name"]
                    plan_id = all_plans.get(plan_name)

                    if not plan_id:
                        continue

                    # Get LOC for the plan from the Plan table
                    loc_value = plans_with_loc.get(plan_id, None)

                    # Map form field names to table columns
                    column_mapping = {
                        "retention_pepm": "RetentionPEPM",
                        "claims_funding": "ClaimsPEPM",
                        "rebate_pepm": "RxRebateOffsetPEPM",
                        "pooling_level": "PoolingLevel",
                        "pooling_pepm": "PoolingFeePEPM",
                    }
                    column_name = column_mapping[field_name]

                    # Aggregate values for this plan
                    insured_policy_data[plan_id]["PlanId"] = plan_id
                    insured_policy_data[plan_id]["StartDate"] = plans_data[plan_identifier].get("start_date")
                    insured_policy_data[plan_id]["EndDate"] = plans_data[plan_identifier].get("end_date")
                    insured_policy_data[plan_id]["LOC"] = loc_value
                    insured_policy_data[plan_id][column_name] = field_value

        # Process rows for insertion or update
        for plan_id, policy_data in insured_policy_data.items():
            if plan_id in existing_insured_policies:
                # Prepare update row
                update_row = {"InsuredPolicyId": existing_insured_policies[plan_id]["InsuredPolicyId"]}
                update_row.update({k: v for k, v in policy_data.items() if v is not None})
                insured_policy_rows_to_update.append(update_row)
            else:
                # Prepare insert row
                insured_policy_rows_to_insert.append(policy_data)

        # Insert new rows into the Insured Policy Details table
        if insured_policy_rows_to_insert:
            supabase.table("Insured Policy Details").insert(insured_policy_rows_to_insert).execute()

        # Update existing rows in the Insured Policy Details table
        for update_row in insured_policy_rows_to_update:
            supabase.table("Insured Policy Details").update(update_row).eq("InsuredPolicyId", update_row["InsuredPolicyId"]).execute()

        return redirect(url_for('group_structure', client_id=client_id))
        

    except Exception as e:
        print(f"Error in save_plan_overview: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/client/<int:client_id>/group_structure', methods=['GET'])
def group_structure(client_id):
    try:
        # Fetch active plans for the client
        plans_query = supabase.table("Plan").select("PlanId, PlanName").eq("ClientId", client_id).eq("Status", "Active").execute()
        plans = plans_query.data if plans_query.data else []

        # Fetch all possible start and end dates for each plan
        premium_query = supabase.table("Premium").select("PlanId, StartDate, EndDate, RateDescription").eq("ClientId", client_id).execute()
        premiums = premium_query.data if premium_query.data else []

        # ✅ Organize premium data by PlanId and StartDate
        premium_data = {}
        for row in premiums:
            plan_id = str(row["PlanId"])  # Convert to string for JS compatibility
            start_date = row["StartDate"]
            end_date = row["EndDate"]
            rate_description = row["RateDescription"]

            # Ensure PlanId exists in dictionary
            if plan_id not in premium_data:
                premium_data[plan_id] = {
                    "start_dates": set(),
                    "end_dates": {},
                    "rate_descriptions": {}
                }

            # Add unique Start Dates
            premium_data[plan_id]["start_dates"].add(start_date)

            # Store End Dates under the corresponding Start Date
            if start_date not in premium_data[plan_id]["end_dates"]:
                premium_data[plan_id]["end_dates"][start_date] = set()
            premium_data[plan_id]["end_dates"][start_date].add(end_date)

            # Store Rate Descriptions under the corresponding Start Date
            if start_date not in premium_data[plan_id]["rate_descriptions"]:
                premium_data[plan_id]["rate_descriptions"][start_date] = set()
            premium_data[plan_id]["rate_descriptions"][start_date].add(rate_description)

        # ✅ Convert sets to lists before passing to JSON
        for plan_id, data in premium_data.items():
            premium_data[plan_id]["start_dates"] = list(data["start_dates"])
            for start_date in data["end_dates"]:
                premium_data[plan_id]["end_dates"][start_date] = list(data["end_dates"][start_date])
            for start_date in data["rate_descriptions"]:
                premium_data[plan_id]["rate_descriptions"][start_date] = list(data["rate_descriptions"][start_date])

        # ✅ Debugging: Print JSON structure to verify correctness
        print("🔍 Final premium_data JSON structure:")
        print(json.dumps(premium_data, indent=4))

        return render_template("group_structure.html", client_id=client_id, plans=plans, premium_data=premium_data)

    except Exception as e:
        print(f"❌ Error in group_structure route: {str(e)}")
        return jsonify({"error": str(e)}), 500




@app.route('/client/<int:client_id>/save_group_structure', methods=['POST'])
def save_group_structure(client_id):
    # Process form data and save to the database
    return redirect(url_for('client_dashboard', client_id=client_id))


if __name__ == '__main__':
    app.run(debug=True)
