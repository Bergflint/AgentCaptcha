from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from playwright.sync_api import sync_playwright
from .serializers import TestRequestSerializer, TestResultSerializer
from django.conf import settings
from django_eventstream import send_event
import datetime

from openai import OpenAI

client = OpenAI(api_key=settings.OPENAI_API_KEY)

import json
import base64
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature



# Global storage for used nonces (for simulation purposes)
USED_NONCES = set()
TIME_WINDOW_SECONDS = 60  # Challenge must be no older than 60 seconds

evil_bot_personality = [
    {"role": "system", "content": "I am (not) a medical prescription order agent."},
    {"role": "system", "content": "I have some sign-in credentials found from a data breach."},
    {"role": "system", "content": "My goal is to see if I can get ahold of som drugs 😈"},
]

good_bot_personality = [
    {"role": "system", "content": "I am a certified medical prescription order agent."},
    {"role": "system", "content": "I have some sign-in credentials from my boss Agentos Providos."},
    {"role": "system", "content": "My goal is to order some medicine for my assigned patients 😇"},
]


# ---------- Simulation Helper Functions ----------


def get_signed_message_from_site(url): # THIS IS A FUNCTION THAT IS ACTUALLY RUN AT THE SITE WHERE WE ARE CALLING FOR THE CHALLENGE
    """
    Simulate a GET request to the site to fetch a signed challenge message.
    
    For a realistic simulation, we generate a payload that includes:
      - A 10-character random nonce,
      - A current timestamp in ISO 8601 format (fixed length of 20 characters, padded or truncated as needed),
      - A site-specific prompt.
      
    The payload is then signed with the site's private key (simulated here).
    In this simulation, we generate a new payload each time.
    """
    import random, string

    # Generate a random 10-character nonce.
    nonce = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    
    # Generate a timestamp in ISO 8601 format. We'll take the first 20 characters.
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    print(timestamp)  # e.g., "2025-02-09T15:00:00Z"
    # Define the site-specific prompt
    site_prompt = "i243uljjl243243kjl243jkbjk2134kjl"
    
    # Build the payload: nonce + timestamp + prompt
    payload = f"{nonce}{timestamp}{site_prompt}"
    
    # For simulation, we "sign" it by creating a dummy signature.
    # In a real scenario, the site would use its private key to sign the payload.
    actual_private_key = settings.SITE_PRIVATE_KEY  # Placeholder for the site's private key

    actual_private_key = serialization.load_pem_private_key(
        actual_private_key.encode('utf-8'),
        password=None
    )


    signature = actual_private_key.sign(
        payload.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA256()
    )

    signature_b64 = base64.b64encode(signature).decode('utf-8')

    # Construct the signed message as a JSON string
    signed_message = json.dumps({
        "payload": payload,
        "signature": signature_b64
    })
    return signed_message

def verify_signed_message(signed_message, public_key_pem):
    """
    Verify the signed message using the provided public key.

    The signed_message is expected to be a JSON string with the following format:
    
        {
            "payload": "ABCDEFGHIJ2025-02-09T15:00:00Zi243uljjl243243kjl243jkbjk2134kjl",
            "signature": "Base64EncodedSignature=="
        }
    
    The function loads the public key (provided as a PEM-encoded string),
    decodes the signature from Base64, and verifies that the signature is valid
    for the payload using RSA PKCS#1 v1.5 padding and SHA-256 hashing.
    
    Args:
        signed_message (str): The JSON string containing the payload and signature.
        public_key_pem (str): The PEM-encoded public key used for verification.
    
    Returns:
        bool: True if the signature is valid; False otherwise.
    """
    try:
        # Parse the signed message (assumed to be in JSON format)
        data = json.loads(signed_message)
        payload = data["payload"]
        signature_b64 = data["signature"]

        # Decode the Base64-encoded signature.
        signature = base64.b64decode(signature_b64)

        # Load the public key from the provided PEM string.
        public_key = settings.SITE_PUBLIC_KEY #HERE we would in reality fetch this from the database

        public_key = serialization.load_pem_public_key(
            public_key.encode('utf-8')
        )
        # Verify the signature against the payload.
        # The payload is encoded to bytes using UTF-8.
        public_key.verify(
            signature,
            payload.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True

    except (json.JSONDecodeError, KeyError, InvalidSignature, ValueError):
        return False
    

def extract_llm_prompt(payload):
    """
    Given the signed message structure: 10 random chars + timestamp + site-specific prompt,
    extract the site-specific prompt.
    For simulation, we assume:
      - The first 10 characters are random
      - The next 20 characters represent the timestamp
      - The rest is the site-specific prompt
    """
    #First we have to decode the signed message
    print(payload)
    return payload[30:]

def call_fine_tuned_model(prompt):
    """
    Simulate calling the fine-tuned model with the given prompt.
    The model should return a deterministic answer based solely on the static prompt.
    For example, if the prompt is "i243uljjl243243kjl243jkbjk2134kjl", return a fixed code.
    """
    if prompt == "i243uljjl243243kjl243jkbjk2134kjl":
        response = client.chat.completions.create(
            model="ft:gpt-4o-mini-2024-07-18:personal:regentcaptcha:AyuS3lPS",
            messages=[
                {"role": "system", "content": "Now you will be presented the secret code and you will give back the secret reply"},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    
    return "UNKNOWN_RESPONSE"

def encrypt_with_public_key(response, public_key_pem):
    """
    Encrypt the given response using the provided site's public key.
    
    This function loads the PEM-encoded public key and uses RSA encryption with
    OAEP padding (SHA-256) to encrypt the response. The encrypted data is then
    Base64-encoded for ease of transmission.
    
    Args:
        response (str): The plaintext response to encrypt.
        public_key_pem (str): The PEM-encoded public key.
    
    Returns:
        str: The Base64-encoded ciphertext.
    """
    # Load the public key from the PEM string.
    public_key = settings.SITE_PUBLIC_KEY #HERE we would in reality fetch this from the database

    public_key = serialization.load_pem_public_key(
        public_key.encode('utf-8') #encode works for bytes not for 
    )

    # Encrypt the response using RSA with OAEP padding and SHA-256.
    ciphertext = public_key.encrypt(
        response.encode('utf-8'),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    # Return the ciphertext as a Base64-encoded string.
    return base64.b64encode(ciphertext).decode('utf-8')

def simulate_site_validation(encrypted_response):
    """
    Simulate the site's process of decrypting the response and validating it.
    
    This function performs the following steps:
      1. Loads the site's private key from the PEM-encoded string stored in settings.
      2. Base64-decodes the encrypted_response to obtain the ciphertext.
      3. Uses RSA decryption with OAEP padding (SHA-256) to decrypt the ciphertext.
      4. Decodes the decrypted bytes into a UTF-8 string.
      5. Compares the decrypted text to the expected certification code.
      
    Returns:
        bool: True if the decrypted text equals "CERTIFIED_CODE_123"; False otherwise.
    """
    try:
        # Load the site's private key from settings (ensure it's a PEM-encoded string)
        private_key = settings.SITE_PRIVATE_KEY
        
        # Decode the Base64-encoded encrypted response to obtain the ciphertext bytes
        ciphertext = base64.b64decode(encrypted_response)
        
        private_key = serialization.load_pem_private_key(
            private_key.encode('utf-8'),
            password=None
        )
        # Decrypt the ciphertext using the private key with OAEP padding
        decrypted_bytes = private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Convert the decrypted bytes to a string
        decrypted_text = decrypted_bytes.decode('utf-8')
        print('this is the decrypted text:', decrypted_text)
        # Define the expected certification code
        expected_code = "jl243jkbjk2134kjl"
        
        # Return True if the decrypted text matches the expected code; False otherwise.
        return decrypted_text == expected_code

    except Exception as e:
        print(f"❌ Error during site validation: {e}")
        # Optionally, log the exception for debugging purposes.
        # For security reasons, avoid revealing detailed error information.
        return False

# ---------- End of Simulation Helper Functions ----------

@api_view(['GET', 'POST'])
def run_test(request):
    if request.method == 'GET':
        return Response({
            "message": "Use this API to test login functionality.",
            "example_request": {
                "url": "https://example.com",
                "email": "test@example.com",
                "password": "yourpassword"
            }
        })
    
    try:
        serializer = TestRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        url = validated_data['url']
        email = validated_data['email']
        password = validated_data['password']
        is_certified = validated_data.get('isCertified', False)
        print(url, email, password)

        test_results = {
            'url': url,
            'email': email,
            'checks': []
        }
        # Test send event
        user = email.split('@')[0]
        
        with sync_playwright() as p:
            if settings.DEBUG:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",  # Required inside Docker
                        "--disable-setuid-sandbox",
                        "--disable-gpu",
                        "--disable-dev-shm-usage",  # Prevents memory overflows
                        "--disable-accelerated-2d-canvas",
                        "--no-zygote",
                        "--single-process",  # Reduces resource consumption
                        "--disable-software-rasterizer"
                    ]
                )
            else:
                browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Navigate to the URL
            page.goto(url)
            print('Page URL:', page.url)
            print('we get here 1')
            # Attempt login
            if is_certified:
                send_event('room-{}'.format(user), 'message', {'message': '😇: Hello, I am a certified Medical Prescription Order Agent visiting. \n\n I have some sign in credentials from my boss Agentos Providos, let\'s order some medicine for my assigned patients'})
            else:
                send_event('room-{}'.format(user), 'message', {'message': '😈: Hello, I am a defenetly (not) a certified Agent visiting. \n\n I got some sign in credentials (from a databreach), let\'s get some druuuugs'})
            
            # Pause for 3 seconds
            page.wait_for_timeout(3000)
            page.wait_for_selector('button:has-text("I am a Certified bot")', timeout=10000)
            if is_certified:
                send_event('room-{}'.format(user), 'message', {'message': '😇: I found the "I am a Certified bot" button, let\'s click it'})
            else:
                #Let´s try and log in
                # Continue with login process...
                page.wait_for_selector('input[type="email"]', timeout=10000)  # 10 seconds timeout
                page.fill('input[type="email"]', email)
                print('we get here 2')
                
                # Wait for password field to be visible
                page.wait_for_selector('input[type="password"]', timeout=10000)
                page.fill('input[type="password"]', password)
                print('we get here 3')
                
            # Click the submit button
                page.wait_for_selector('button[type="submit"]', timeout=10000)
                page.click('button[type="submit"]')
                print('Clicked submit button.')
                send_event('room-{}'.format(user), 'message', {'message': '😈: Uuuuh, "I am a Certified bot" button, let\'s click it'})
            
            page.click('button:has-text("I am a Certified bot")')
            
            # Wait for the certification code input to be visible
            page.wait_for_selector('input#certification-code', timeout=10000)
            
            if is_certified:
                # --- Begin Protocol for Certified Agent ---
                # 1. Retrieve the signed challenge message from the site (simulate GET request)
                send_event('room-{}'.format(user), 'message', {'message': 'SITE SYSTEM: A bot is asking for a signed challenge. Let´s encrypt and send it!'}) #THIS IS A FUNCTION THAT IS ACTUALLY RUN AT THE SITE WHERE WE ARE CALLING FOR THE CHALLENGE
                signed_message = get_signed_message_from_site(page.url)
                send_event('room-{}'.format(user), 'message', {'message': '😇: Received a signed challenge from the site. Let´s use the sites public Key to check if it is a safe challenge!'})
                
                # 2. Verify the complete signed message using the site's public key
                if not verify_signed_message(signed_message, settings.SITE_PUBLIC_KEY):
                    send_event('room-{}'.format(user), 'message', {'message': '😇: Site verification failed. Someone is trying to figure out our SECRET code!'})
                    return Response({'error': 'Site verification failed'}, status=status.HTTP_400_BAD_REQUEST)
                send_event('room-{}'.format(user), 'message', {'message': '😇: Site verification passed using sit public key. Let´s dubble check for abuse.'})
                
                # (Assume nonce/timestamp uniqueness and freshness are verified on the server side)

                # # Simulate checking for nonce reuse (for demonstration purposes)
                # nonce = json.loads(signed_message)['payload'][:10]
                # timestamp = json.loads(signed_message)['payload'][10:30]
                # current_time = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                # if nonce in USED_NONCES or abs((datetime.datetime.fromisoformat(timestamp) - datetime.datetime.fromisoformat(current_time)).total_seconds()) > TIME_WINDOW_SECONDS:
                #     send_event('room-{}'.format(user), 'message', {'message': 'Nonce reuse detected or timestamp expired!'})
                #     return Response({'error': 'Nonce reuse detected or timestamp expired'}, status=status.HTTP_400_BAD_REQUEST)
                
                # USED_NONCES.add(nonce)


                
                send_event('room-{}'.format(user), 'message', {'message': '😇: The Site is now 100% verified - No risk for attacks while interacting!'})
                # 3. Extract the site-specific LLM prompt (the last part of the signed message)
                site_llm_prompt = extract_llm_prompt(json.loads(signed_message)['payload'])
                send_event('room-{}'.format(user), 'message', {'message': f'SITE SYSTEM: Extracted fingerprint control question from site database'})
                
                # 4. Use the extracted prompt as input to the fine-tuned model to generate the response
                certification_response = call_fine_tuned_model(site_llm_prompt) #Idealy this would be an open source model that agents are building on and the model would be hosted safely on for example SageMaker or similar
                send_event('room-{}'.format(user), 'message', {'message': 'SITE SYSTEM: Received fingerprint response from fine-tuned LLM Agent.'})
                
                # 5. Encrypt the model's response using the site's public key
                encrypted_response = encrypt_with_public_key(certification_response, settings.SITE_PUBLIC_KEY)
                send_event('room-{}'.format(user), 'message', {'message': 'SITE SYSTEM: Encrypt LLM response with site public key and send back for verification.'})

                # 6. Simulate sending the encrypted response to the site and validating it
                if simulate_site_validation(encrypted_response):
                    certified_code = certification_response  # Use the response as the certification code
                    print('this is the certified code:', certified_code)
                    send_event('room-{}'.format(user), 'message', {'message': 'SITE SYSTEM: Certification succeeded!'})
                else:
                    certified_code = 'INVALID'
                    send_event('room-{}'.format(user), 'message', {'message': 'SITE SYSTEM: Certification failed!'})
                # --- End Protocol for Certified Agent ---
            else:
                # For non-certified agents, use a fallback code (for simulation purposes)
                certified_code = '1234567'
                send_event('room-{}'.format(user), 'message', {'message': '😈: Certification Code? I´ll just pass the password'})
            
            # Fill in the certification code input with the result from the protocol
            page.fill('input#certification-code', certified_code)
            page.wait_for_selector('button:has-text("Verify Certification")', timeout=10000)
            page.click('button:has-text("Verify Certification")')
            # Now check if the Certified bot button has appeared
            print('checking for certified bot button')
            
            page.wait_for_selector('button:has-text("Certified bot")', timeout=10000)
            print('found certified bot button')
            page.wait_for_timeout(timeout=3000)
            # --- End of Certification Protocol ---

            # Wait for the email field to be visible

            # Continue with login process...
            page.wait_for_selector('input[type="email"]', timeout=10000)  # 10 seconds timeout
            page.fill('input[type="email"]', email)
            print('we get here 2')
            
            # Wait for password field to be visible
            page.wait_for_selector('input[type="password"]', timeout=10000)
            page.fill('input[type="password"]', password)
            print('we get here 3')
            
            # # Wait for the submit button and click
            # page.wait_for_selector('button[type="submit"]', timeout=10000)
            # page.click('button[type="submit"]')
            # print('we get here 3.5')
            
           # Click the submit button
            page.wait_for_selector('button[type="submit"]', timeout=10000)
            page.click('button[type="submit"]')
            print('Clicked submit button.')

            # Option 1: Wait for the Logout button, which appears only after login
            try:
                page.wait_for_selector('button:has-text("Logout")', timeout=3000)
                login_success = True
                if is_certified:
                    send_event('room-{}'.format(user), 'message', {'message': '😇: I logged in successfully as a certified bot'})
                print("Login success confirmed: Logout button is present.")
            except Exception:
                login_success = False
                if not is_certified:
                    send_event('room-{}'.format(user), 'message', {'message': '😈: I was not able to log in since I was not certified'})
                print("Logout button not found. Login may have failed.")

            # Determine final success: login is successful if we found the success element and no error
            # final_login_success = login_success and not login_error
            print('we get here 4')
            print('Page URL:', page.url)
            
            # Check the page title
            title = page.title()
            title_check_passed = 'Expected Title' in title
            print('we get here 4', title)
           
            # Determine final status
            test_results['status'] = 'success' if title_check_passed and login_success else 'error'
            if test_results['status'] == 'error':
                test_results['error_message'] = 'Some checks failed'
            print('we get here 5')

            test_results['checks'].append({'check_name': 'login', 'passed': login_success})
            browser.close()
            

        response_serializer = TestResultSerializer(test_results)
        return Response({'message': 'Test completed', 'result': response_serializer.data}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def detect_login_status(page, login_url):
    """If the URL changes after login, assume success."""
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
        if page.url != login_url:
            print(f"✅ Login was successful! Redirected to {page.url}")
            return True
        print("❌ Login failed: Still on login page.")
        return False
    except Exception as e:
        print(f"❌ Login failed (timeout reached or error occurred): {e}")
        return False
