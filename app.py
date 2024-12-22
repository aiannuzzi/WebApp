from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from forms import BuildInitForm, TierStructureForm, RateStructuresForm
from flask_wtf.csrf import CSRFProtect, generate_csrf
from supabase import create_client, Client
from dotenv import load_dotenv
from itertools import product
from collections import defaultdict
import os

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
        "Medical": [plan for plan in plans if plan['LOC'] == 'Medical/Rx'],
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
        plan_tier_data = defaultdict(lambda: {"tier_count": None, "tiers": [], "plans": []})

        

        # Normalize the keys for tier counts
        normalized_form = {}
        for key, value in request.form.items():
            if key == "number_of_tiers":  # Treat `number_of_tiers` as `tier_count_1`
                normalized_form["tier_count_1"] = value
            else:
                normalized_form[key] = value

        # Dynamically process tier structures
        for key, value in normalized_form.items():
            if key.startswith("tier_count_"):  # Detect tier count keys
                # Extract structure ID (e.g., "tier_count_1" -> "1")
                structure_id = int(key.split("_")[2])

                # Initialize the structure if not already present
                if structure_id not in plan_tier_data:
                    plan_tier_data[structure_id] = {"tier_count": None, "tiers": [], "plans": []}

                # Set the tier count for this structure
                plan_tier_data[structure_id]["tier_count"] = int(value)

            elif key.startswith("choose_tier_"):  # Detect tier names
                # Parse the key structure: "choose_tier_<structure_id>_<tier_index>"
                parts = key.split("_")
                if len(parts) == 3:
                    structure_id = int(parts[2])
                    tier_index = int(parts[3]) - 1  # Convert to zero-based index

                    # Ensure the structure and tier exist
                    while len(plan_tier_data[structure_id]["tiers"]) <= tier_index:
                        plan_tier_data[structure_id]["tiers"].append({"tier_name": None, "single_family": None})

                    # Set the tier name
                    plan_tier_data[structure_id]["tiers"][tier_index]["tier_name"] = value

            elif key.startswith("single_family_"):  # Detect single/family designations
                # Parse the key structure: "single_family_<structure_id>_<tier_index>"
                parts = key.split("_")
                if len(parts) == 3:
                    structure_id = int(parts[2])
                    tier_index = int(parts[3]) - 1  # Convert to zero-based index

                    # Ensure the structure and tier exist
                    while len(plan_tier_data[structure_id]["tiers"]) <= tier_index:
                        plan_tier_data[structure_id]["tiers"].append({"tier_name": None, "single_family": None})

                    # Set the single/family value
                    plan_tier_data[structure_id]["tiers"][tier_index]["single_family"] = value

            elif key.startswith("selected_plans_"):  # Detect selected plans
                # Extract structure ID (e.g., "selected_plans_1" -> "1")
                structure_id = int(key.split("_")[2])

                # Ensure the structure exists
                if structure_id not in plan_tier_data:
                    plan_tier_data[structure_id] = {"tier_count": None, "tiers": [], "plans": []}

                # Use request.form.getlist to handle multiple values for the key
                plan_tier_data[structure_id]["plans"] = request.form.getlist(key)

        

        # Save the tier data to the session
        session['tier_data'] = dict(plan_tier_data)
        print(plan_tier_data)

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
    # Initialize plan_data
    plan_data = defaultdict(dict)

    # Retrieve data from session
    active_plans = session.get('available_plans', [])  # [(plan_id, plan_name)]
    rate_data = session.get('rate_data', {})  # Rate data with options
    tier_data = session.get('tier_data', {})  # Tier structure data
    generated_plans = session.get('generated_plans', [])  # Plans generated by the user
    
    
    # Combine active plans and generated plans into one loop
    for plan in active_plans:
            plan_id = plan['PlanId']
            plan_name = plan['PlanName']
            start_date=plan.get('StartDate')
            end_date=plan.get('EndDate')

            if plan_id is not None:
                # Fetch details for existing plans from the database
                plan_query = supabase.table('Plan').select('PlanName', 'FundingType', 'LOC', 'PrimaryCarrierName').eq('PlanId', plan_id).execute()
                if plan_query.data:
                    plan_data[plan_id] = {
                        'name': plan_query.data[0]['PlanName'],
                        'funding_type': plan_query.data[0]['FundingType'],
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
        for plan_id in structure_info.get('plans', []):
            # Handle both integers and string names
            plan_id = int(plan_id) if isinstance(plan_id, str) and plan_id.isdigit() else plan_id

            # Get the number of tiers for this structure
            num_tiers = structure_info.get('tier_count', 0)

            # Update or initialize the plan_data entry for num_tiers
            if plan_id in plan_data:
                plan_data[plan_id]["num_tiers"] = num_tiers
            else:
                # If plan_data entry does not exist, create a placeholder entry with num_tiers
                plan_data[plan_id] = {
                    "num_tiers": num_tiers,
                    "name": None,
                    "funding_type": None,
                    "loc": None,
                    "carrier": None,
                    "start_date": None,
                    "end_date": None,
                    "rate_combinations": [],
                }

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


    print(plan_data)
    
    # Render the template
    return render_template(
        'plan_overview.html',
        client_id=client_id,
        plan_data=plan_data,
        tier_data=tier_data,
        plan_rate_data=rate_data
    )


@app.route('/client/<int:client_id>/plan_overview/save', methods=['POST'])
def save_plan_overview(client_id):
    # Process the form data here
    form_data = request.form  # Access submitted form data
    print("Submitted data:", form_data)

    # Save to database or session
    # Redirect to another page or return a response
    return redirect(url_for('some_other_route', client_id=client_id))


   
if __name__ == '__main__':
    app.run(debug=True)
