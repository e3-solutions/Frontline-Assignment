import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

/**
 * Server-side validation of company registration secret.
 * The secret is hashed with SHA256 and compared against the stored hash.
 *
 * Environment variable: COMPANY_REGISTRATION_SECRET_HASH
 * Should contain the SHA256 hash of the valid secret.
 *
 * To generate a hash, run:
 * echo -n "your-secret" | sha256sum
 */
export async function POST(request: NextRequest) {
  try {
    const { secret } = await request.json();

    if (!secret || typeof secret !== "string") {
      return NextResponse.json(
        { valid: false, error: "Secret is required" },
        { status: 400 }
      );
    }

    const storedHash = process.env.COMPANY_REGISTRATION_SECRET_HASH;

    // If no hash is configured, allow any registration (development mode)
    if (!storedHash) {
      console.warn(
        "COMPANY_REGISTRATION_SECRET_HASH not set - allowing any registration"
      );
      return NextResponse.json({ valid: true });
    }

    // Hash the provided secret with SHA256
    const providedHash = crypto
      .createHash("sha256")
      .update(secret)
      .digest("hex");

    const isValid = storedHash === providedHash;

    return NextResponse.json({ valid: isValid });
  } catch (error) {
    console.error("Error validating secret:", error);
    return NextResponse.json(
      { valid: false, error: "Validation failed" },
      { status: 500 }
    );
  }
}
