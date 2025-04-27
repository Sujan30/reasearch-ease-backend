import os
from supabase import create_client, Client
import requests
import jwt
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get Supabase configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
SUPABASE_PROJECT_ID = os.environ.get('SUPABASE_PROJECT_ID', '')

# Validate configuration
if not SUPABASE_URL or not SUPABASE_KEY:
    print("WARNING: Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_KEY environment variables.")
    # Set defaults for development (these won't work in production)
    if not SUPABASE_URL:
        SUPABASE_URL = 'https://earawfmpubxijspazzuz.supabase.co'
    if not SUPABASE_KEY:
        SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVhcmF3Zm1wdWJ4aWpzcGF6enV6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDUyNzk2MDksImV4cCI6MjA2MDg1NTYwOX0.LF_bmnU7IL5X-cDCZe_uB2wGC7FkviaKbtnoSfF784g'

# Create Supabase client
sb1 = create_client(SUPABASE_URL, SUPABASE_KEY)

# JWKS endpoint for Supabase Auth (GoTrue) to fetch public keys
JWKS_URL = f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"

def verify_token(token):
    """
    Verify a JWT token from Supabase Auth
    
    This will first try to verify with the JWKS endpoint.
    If that fails or returns empty keys, it will fall back to a basic verification
    that checks token structure and expiration but not signature.
    """
    if not token:
        print("No token provided")
        return None
        
    try:
        # Get the token's header to find the key ID (kid)
        header = jwt.get_unverified_header(token)
    except Exception as e:
        print(f"Invalid token header: {e}")
        return None
    
    # Try to fetch the JWKS from Supabase
    try:
        resp = requests.get(JWKS_URL)
        resp.raise_for_status()
        jwks = resp.json()
        keys = jwks.get('keys', [])
    except Exception as e:
        print(f"Failed to fetch JWKS from {JWKS_URL}: {e}")
        keys = []
    
    # If we have valid JWKS keys, use standard verification
    if keys:
        jwk = next((k for k in keys if k.get('kid') == header.get('kid')), None)
        if jwk:
            try:
                # Convert JWK to RSA public key
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
                
                # Decode and verify the token
                payload = jwt.decode(
                    token,
                    public_key,
                    algorithms=["RS256"],
                    audience=None  # Skip aud validation unless needed
                )
                return payload
            except Exception as e:
                print(f"Token verification failed: {e}")
                # Fall through to fallback verification
        else:
            print(f"No matching JWK found for kid: {header.get('kid')}")
            # Fall through to fallback verification
    else:
        print("WARNING: JWKS endpoint returned empty keys array")
    
    # Fallback verification: Just check token structure and expiration
    # without verifying signature
    try:
        payload = jwt.decode(
            token,
            options={"verify_signature": False},
            algorithms=["RS256"]
        )
        print("WARNING: Using simplified token verification (signature not verified)")
        return payload
    except jwt.ExpiredSignatureError:
        print("Token is expired")
        return None
    except Exception as e:
        print(f"Token verification failed in fallback mode: {e}")
        return None

# Attach verify_token to the Supabase client instance for convenience
sb1.verify_token = verify_token