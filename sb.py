import os
from supabase import create_client, Client

url: str = os.environ.get('SUPABASE_URL')
key: str = os.environ.get("SUPABASE_KEY")
sb1 = create_client(url, key)

import requests
import jwt

SUPABASE_PROJECT_ID = os.environ.get("SUPABASE_URL").split(".")[0].split("//")[1]
JWKS_URL = f"https://{SUPABASE_PROJECT_ID}.supabase.co/auth/v1/keys"
JWKS = requests.get(JWKS_URL).json()
JWKS = requests.get(JWKS_URL).json()

def verify_token(token):
    try:
        # Get the token's header to find the key ID (kid)
        header = jwt.get_unverified_header(token)
        
        # Find the matching key in the JWKS
        key = next((k for k in JWKS['keys'] if k['kid'] == header['kid']), None)
        if key is None:
            return None
        
        # Convert JWK to RSA public key
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
        
        # Decode the token
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=None  # Only needed if you're validating the `aud` claim
        )
        return payload  # Contains user info like 'sub' (user ID), 'email', etc.

    except Exception as e:
        print("Token verification failed:", e)
        return None