from flask import Flask, request, json, render_template_string
import requests
import os
from dotenv import load_dotenv

app = Flask(__name__)

# --- CONFIGURATION ---
# API Tokens are managed via .env file which is in .gitignore to maintain HIPAA compliance and security
load_dotenv()
API_TOKEN_A = os.getenv("REDCAP_TOKEN_NON_CONSENT_Database")
API_TOKEN_B = os.getenv("REDCAP_TOKEN_CONSENT_Database")
REDCAP_API_URL = os.getenv("TRACE_AI_REDCAP_URL")



# This verifies a secure SSL Connection to the REDCap Server
try:
    response = requests.get(REDCAP_API_URL.split('api/')[0], timeout=10)
    print(f"REDCAP Connection Check: {response.status_code} - Secure")
except Exception as e:
    print(f"Warning: Could not verify REDCap connection: {e}")



@app.route('/transfer', methods=['GET'])
def transfer_data():
    """
    Handles the secure transfer of screened participants from 
    Project A (Eligibility) to Project B (Consent Database)
    and displays a dynamic UI based on consent choice.
    """

    record_id = request.args.get('record')
    if not record_id:
        return "Error: No record ID provided.", 400

    # 1. Export: The record is obtained using the record id from Project A (the non-consent redcap database)
    export_payload = {
        'token': API_TOKEN_A,
        'content': 'record',
        'format': 'json',
        'type': 'flat',
        'records[0]': record_id,
        'exportSurveyFields': 'true'
    }
    
    try:
        response_a = requests.post(REDCAP_API_URL, data=export_payload)
        records = response_a.json()

        if not records or len(records) == 0:
            return f"Error: Record {record_id} not found in Project TRACE-AI Prospective Study.", 404

        data_from_a = records[0]
        consent_choice = str(data_from_a.get('interested_consent', ''))


        # 2. This ensures only the necessary fields needed are exported from Project A and sent to Project B (the consent database)
        # This maintains protocol by not transferring any unnecessary screening data
        clean_data_for_b = {
            'record_id': record_id,
            'pt_email': data_from_a.get('pt_email'),
            'pt_phone': data_from_a.get('pt_phone'),
            'res_email': data_from_a.get('res_email'),
            'elig_date': data_from_a.get('elig_date'),
            'interested_consent': consent_choice, # 1=Electronic-consent, 2=In-person
            # This sets the form status to 'Complete' (2) in Project B
            'trace_ai_eligibility_screening_draft_complete': '2',
            'record_set_up_complete': '2'
        }

        # 3. Import: The necessary data from Project A is imported/copied into Project B
        import_payload = {
            'token': API_TOKEN_B,
            'content': 'record',
            'format': 'json',
            'type': 'flat',
            'overwriteBehavior': 'normal',
            'data': json.dumps([clean_data_for_b])
        }
        
        response_b = requests.post(REDCAP_API_URL, data=import_payload)
        
        # This log in printed out in output terminal to keep track of what is happening.
        print(f"Sync Event: Record {record_id} | Status: {response_b.status_code}")

    except Exception as e:
        return f"System Error during transfer: {str(e)}", 500



    # 4. Dynamic User Interface: what the user sees prompting them to the next step so the email can be sent to the user via the data imported from project A to B.
    
    return render_template_string('''
        <div style="font-family: sans-serif; text-align: center; margin-top: 100px;">
            <div style="border: 1px solid #ccc; display: inline-block; padding: 40px; border-radius: 10px; max-width: 500px;">
                <h1 style="color: #2c3e50;">Eligibility Form Submitted</h1>
                <p style="font-size: 1.1em;">Record <strong>{{ rec }}</strong> has been synced to the Consent Database.</p>
                <hr style="margin: 25px 0;">
                
                {% if choice == '1' %}
                    <p>The participant selected <strong>Electronic Consent</strong>.</p>
                    <p>Click below to send the Questionnaire link to their email.</p>
                    <form action="/trigger-email" method="POST">
                        <input type="hidden" name="rec_id" value="{{ rec }}">
                        <button type="submit" style="background: #007bff; color: white; border: none; padding: 15px 30px; font-size: 18px; border-radius: 5px; cursor: pointer;">
                            Send My Questionnaire
                        </button>
                    </form>
                {% elif choice == '2' %}
                    <p>The participant selected <strong>In-Person Consent</strong>.</p>
                    <p>Click below to trigger the internal notification for in-person setup.</p>
                    <form action="/trigger-email" method="POST">
                        <input type="hidden" name="rec_id" value="{{ rec }}">
                        <button type="submit" style="background: #28a745; color: white; border: none; padding: 15px 30px; font-size: 18px; border-radius: 5px; cursor: pointer;">
                            Prepare In-Person Consent
                        </button>
                    </form>
                {% else %}
                    <p style="color: #e74c3c; font-weight: bold;">Warning: No consent preference was recorded (Value: {{ choice }}).</p>
                    <p>Please review the record in REDCap.</p>
                {% endif %}
            </div>
        </div>
    ''', rec=record_id, choice=consent_choice)



@app.route('/trigger-email', methods=['POST'])
def trigger_email():
    """
    Updates the trigger field in Project B to fire the automated REDCap Alert based on the choice stored.
    """
    record_id = request.form.get('rec_id')


    
    #1. This quickly fetches the choice back from Project B (either E-Consent (1) or In-Person (2)) to decide the payload:
    
    # First we determine WHAT they chose by pullling the data from Project B:
    res = requests.post(REDCAP_API_URL, data={
        'token': API_TOKEN_B,
        'content': 'record',
        'format': 'json',
        'records[0]': record_id
    })



    try:
        #choice = res.json()[0].get('interested_consent')
        data = res.json()[0]
        choice = str(data.get('interested_consent', ''))
    except (IndexError, KeyError):
        return "Error: Could not retrieve record details from Project B.", 500
    


    # 2. Logic to choose the correct Alert Variable

    # Initialize trigger payload
    trigger_payload = {'record_id': record_id}


    if choice == "1":
        # Trigger the Electronic Consent Alert
        trigger_payload['trigger_email'] = "1"
        #trigger_payload['cons_in_person_email'] = "0"
    elif choice == "2":
        # Trigger the In-Person Consent Alert
        #trigger_payload['trigger_email'] = "0"
        trigger_payload['cons_in_person_email'] = "1"
    else:
        print(f"No consent alert sent for Record {record_id} (Choice: {choice})")
        return "No alert needed for this choice."

    

    # Send update to Project B
    response = requests.post(REDCAP_API_URL, data={
        'token': API_TOKEN_B,
        'content': 'record',
        'format': 'json',
        'type': 'flat',
        'data': json.dumps([trigger_payload])
    })
    

    # DEBUG: This will print the EXACT error from REDCap if it's 400
    if response.status_code != 200:
        print(f"REDCAP ERROR for Record {record_id}: {response.text}")
    else:
        print(f"Success! Record {record_id} updated. Choice: {choice}")

    print(f"Email Alert Triggered: Record {record_id} | Response: {response.text}. |  Status: {response.status_code} for Choice {choice}")

    
    return """
        <div style="font-family: sans-serif; text-align: center; margin-top: 100px;">
            <h2 style="color: #2c3e50;">Action Complete!</h2>
            <p style="font-size: 1.1em;">The corresponding alert has been triggered in REDCap.</p>
            <p>You may now close this window or return to the dashboard.</p>
        </div>
    """



if __name__ == '__main__':
    # Debug mode is set to False for production/EC2 deployment
    app.run(debug=False, port=5000)