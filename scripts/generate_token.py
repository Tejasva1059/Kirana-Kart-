import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.mongodb import mongo_manager
from app.services.token_service import TokenService


async def generate():
    await mongo_manager.connect(use_mock=False)
    db = mongo_manager.db

    # Look for or create test customer
    mobile = "9876543210"
    customer = await db.customers.find_one({"mobileNumberNormalized": mobile})
    if not customer:
        now = datetime.now(timezone.utc)
        insert_res = await db.customers.insert_one({
            "fullName": "Rahul Sharma",
            "emailNormalized": "rahul.sharma@example.com",
            "mobileNumberNormalized": mobile,
            "role": "customer",
            "status": "active",
            "mobileVerified": True,
            "emailVerified": False,
            "acceptedTerms": True,
            "createdAt": now,
            "updatedAt": now,
            "lastLoginAt": now,
        })
        customer_id = str(insert_res.inserted_id)
        print(f"[INFO] Created customer account with ID: {customer_id}")
    else:
        customer_id = str(customer["_id"])
        print(f"[INFO] Using existing customer account with ID: {customer_id}")

    # Create active session and issue tokens
    tokens = await TokenService.create_session_and_tokens(
        customer_id=customer_id,
        role="customer",
        device_info={"client": "manual_token_generator"},
    )

    print("\n" + "=" * 80)
    print("CUSTOMER DETAILS:")
    print(f"  Name: Rahul Sharma")
    print(f"  Mobile: {mobile}")
    print(f"  Customer ID: {customer_id}")
    print("\nBEARER ACCESS TOKEN (valid for 15 minutes):")
    print(tokens.accessToken)
    print("\nOPAQUE REFRESH TOKEN (valid for 30 days):")
    print(tokens.refreshToken)
    print("=" * 80 + "\n")

    await mongo_manager.close()


if __name__ == "__main__":
    asyncio.run(generate())
