"""Google Earth Engine (GEE) Authentication Utility.

Provides step-by-step OAuth2 authentication for Earth Engine access:
1. Generates PKCE authorization URL for browser sign-in.
2. Exchanges authorization code for refresh tokens and writes ~/.config/earthengine/credentials.
3. Tests and verifies ee.Initialize() connectivity.
"""
import argparse
import json
import os
import sys
import ee
import ee.oauth


VERIFIER_CACHE_FILE = os.path.expanduser("~/.config/earthengine/.pending_verifier")


def generate_auth_url():
    """Generate a PKCE OAuth authorization URL and cache code verifier."""
    os.makedirs(os.path.dirname(VERIFIER_CACHE_FILE), exist_ok=True)
    flow = ee.oauth.Flow(auth_mode="notebook")
    
    with open(VERIFIER_CACHE_FILE, "w", encoding="utf-8") as f:
        f.write(flow.code_verifier)

    print("\n" + "=" * 70)
    print("GOOGLE EARTH ENGINE OAUTH2 AUTHORIZATION REQUIRED")
    print("=" * 70)
    print("\n1. Open the following URL in your web browser:")
    print(f"\n   {flow.auth_url}\n")
    print("2. Sign in with your Earth Engine enabled Google Account.")
    print("3. Click 'Generate Token' and copy the authorization code.")
    print("4. Complete authentication by running:")
    print("   python app/scripts/authenticate_ee.py --code <YOUR_AUTHORIZATION_CODE>\n")
    print("=" * 70)
    return flow.auth_url


def exchange_code(auth_code: str):
    """Exchange authorization code using cached code verifier and save credentials."""
    if not os.path.exists(VERIFIER_CACHE_FILE):
        print("Error: No pending authorization session found. Run --generate first.")
        sys.exit(1)

    with open(VERIFIER_CACHE_FILE, "r", encoding="utf-8") as f:
        verifier = f.read().strip()

    try:
        ee.oauth.authenticate(
            cli_authorization_code=auth_code.strip(),
            cli_code_verifier=verifier
        )
        print("\n✅ Authentication successful! Credentials written to ~/.config/earthengine/credentials")
        
        # Clean up verifier
        if os.path.exists(VERIFIER_CACHE_FILE):
            os.remove(VERIFIER_CACHE_FILE)

        # Test initialization
        verify_status()
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        sys.exit(1)


def verify_status(project: str = None):
    """Test ee.Initialize() with current credentials."""
    try:
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
        print("✅ Earth Engine initialized successfully! Live GEE pipeline is ready.")
        return True
    except Exception as e:
        print(f"⚠️ Earth Engine initialization test: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Google Earth Engine Authentication Helper")
    parser.add_argument("--generate", action="store_true", help="Generate authorization URL")
    parser.add_argument("--code", type=str, help="Authorization code from Google OAuth")
    parser.add_argument("--status", action="store_true", help="Check current EE authentication status")
    parser.add_argument("--project", type=str, default=None, help="GCP project ID for Earth Engine")

    args = parser.parse_args()

    if args.code:
        exchange_code(args.code)
    elif args.status:
        verify_status(args.project)
    else:
        generate_auth_url()


if __name__ == "__main__":
    main()
