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
        tier_name_mapping = defaultdict(dict)  # Map enrollment tiers to tier names

        # Populate tier_name_mapping from session tier_data
        for tier_set in tier_data.values():
            plans = tier_set.get("plans", [])
            tiers = tier_set.get("tiers", {})
            for plan in plans:
                for tier_name, tier_info in tiers.items():
                    if tier_info.get("tier_name"):  # Ensure the tier has a name
                        tier_name_mapping[plan][tier_name] = tier_info["tier_name"]

        print(f"Tier Name Mapping: {json.dumps(tier_name_mapping, indent=2)}")

        for key, value in submitted_data.items():
            if key.startswith("plans["):
                plan_key = key.split("[")[1].split("]")[0].rsplit("_", 1)[0]

                attribute_key = key.split("][")[1].replace("]", "")
                plans_data[plan_key][attribute_key] = value[0]

        print(f"Parsed Plans Data: {json.dumps(plans_data, indent=2)}")

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
                "PlanType": attributes.get("plan_type"),
                "EffDate": attributes.get("start_date"),
                "CloseDate": None,
                "Status": "Active",
            })

        print(f"Structured Plans for Plan Table: {json.dumps(structured_plans, indent=2)}")

        # Fetch existing plans
        existing_plans_query = supabase.table("Plan").select("PlanName, LOC, ClientId").eq("ClientId", client_id).execute()
        existing_plans = {(plan["PlanName"], plan["LOC"], plan["ClientId"]) for plan in existing_plans_query.data}
        print(f"Existing Plans in DB: {existing_plans}")

        # Identify new plans to insert
        new_plans = []
        for plan in structured_plans:
            if (plan["PlanName"], plan["LOC"], plan["ClientId"]) not in existing_plans:
                new_plans.append(plan)

        print(f"New Plans to Insert: {json.dumps(new_plans, indent=2)}")

        # Insert new plans
        if new_plans:
            response = supabase.table("Plan").insert(new_plans).execute()
            print(f"Insert Response for Plans: {response}")

        # Fetch all plans with IDs
        all_plans_query = supabase.table("Plan").select("PlanId, PlanName").eq("ClientId", client_id).execute()
        all_plans = {plan["PlanName"]: plan["PlanId"] for plan in all_plans_query.data}
        print(f"All Plans with PlanIds: {json.dumps(all_plans, indent=2)}")

        # Process premiums and contributions
        premium_rows_to_insert = []
        contribution_rows_to_insert = []

        for key, values in submitted_data.items():
            if key.startswith("premium_") or key.startswith("contribution_"):
                print(f"Processing key: {key}")  # Debugging

                # Parse the key to extract components
                key_parts = key.split("_")

                # Tier name includes both "Tier" and the number following it
                tier_number = f"{key_parts[1]} {key_parts[2]}"
                print(f"Extracted tier_number: {tier_number}")  # Debugging

                # Plan identifier starts after "Tier" and tier number, up to the second-to-last component
                plan_identifier = "_".join(key_parts[3:-2])
                print(f"Extracted plan_identifier: {plan_identifier}")  # Debugging

                # Rate description is the last component
                rate_description = key_parts[-1]
                print(f"Extracted rate_description: {rate_description}")  # Debugging

                # Crosswalk to get the plan name from identifier
                if plan_identifier in plans_data:
                    plan_name = plans_data[plan_identifier]["plan_name"]
                    print(f"Matched plan_identifier to plan_name: {plan_identifier} -> {plan_name}")  # Debugging
                else:
                    print(f"Plan Identifier '{plan_identifier}' not found in plans_data.")
                    continue

                # Get the database-assigned PlanId
                if plan_name in all_plans:
                    plan_id = all_plans[plan_name]
                    print(f"Matched plan_name to PlanId: {plan_name} -> {plan_id}")  # Debugging
                else:
                    print(f"Plan Name '{plan_name}' not found in all_plans.")
                    continue

                # Retrieve the tier name from the tier mapping for the specific plan
                if plan_identifier in tier_name_mapping:
                    tier_name = tier_name_mapping[plan_identifier].get(tier_number, tier_number)
                    print(f"Retrieved tier_name: {tier_name}")  # Debugging
                else:
                    print(f"No tier data found for Plan Identifier '{plan_identifier}'")
                    tier_name = tier_number  # Default to "Tier 1", "Tier 2", etc.

                # Correct SystemTierTrans formatting
                system_tier_trans = tier_number
                print(f"Formatted SystemTierTrans: {system_tier_trans}")  # Debugging

                # Add rows for each value in the submitted data
                for value in values:
                    if key.startswith("premium_"):
                        premium_row = {
                            "PlanId": plan_id,
                            "ClientId": client_id,
                            "StartDate": plans_data[plan_identifier].get("start_date"),
                            "SystemTierTrans": system_tier_trans,
                            "TierName": tier_name,
                            "RateDescription": rate_description,
                            "PremAmt": float(value) if value else None,
                            "PremFreq": "Monthly",
                            "PremAmt_Annual": float(value) * 12 if value else None,
                        }
                        premium_rows_to_insert.append(premium_row)

                    elif key.startswith("contribution_"):
                        contribution_row = {
                            "PlanId": plan_id,
                            "ClientId": client_id,
                            "StartDate": plans_data[plan_identifier].get("start_date"),
                            "SystemTierTrans": system_tier_trans,
                            "TierName": tier_name,
                            "RateDescription": rate_description,
                            "CtrbAmt": float(value) if value else None,
                            "CtrbFreq": "Monthly",
                            "CtrbAmt_Annual": float(value) * 12 if value else None,
                        }
                        contribution_rows_to_insert.append(contribution_row)

        print(f"Premium Rows to Insert: {json.dumps(premium_rows_to_insert, indent=2)}")
        print(f"Contribution Rows to Insert: {json.dumps(contribution_rows_to_insert, indent=2)}")

        # Insert premiums
        if premium_rows_to_insert:
            response = supabase.table("Premium").insert(premium_rows_to_insert).execute()
            print(f"Insert Response for Premiums: {response}")

        # Insert contributions
        if contribution_rows_to_insert:
            response = supabase.table("Contribution").insert(contribution_rows_to_insert).execute()
            print(f"Insert Response for Contributions: {response}")

        return jsonify({"message": "Plans, premiums, and contributions saved successfully"}), 200

    except Exception as e:
        print(f"Error in save_plan_overview: {str(e)}")
        return jsonify({"error": str(e)}), 500


         
if __name__ == '__main__':
    app.run(debug=True)
