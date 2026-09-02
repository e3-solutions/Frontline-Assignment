import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { adminServices } from "@/src/services/supabase/admin";

const hashToken = (token: string): string =>
  crypto.createHash("sha256").update(token).digest("hex");

const validateCompanySecret = (secret: string): boolean => {
  const storedHash = process.env.COMPANY_REGISTRATION_SECRET_HASH;
  if (!storedHash) return true;
  return storedHash === hashToken(secret);
};

export const POST = async (request: NextRequest) => {
  try {
    const body = await request.json();
    const { type } = body;

    if (type === "company") {
      return handleCompanyRegistration(body);
    }

    if (type === "invite") {
      return handleInviteRegistration(body);
    }

    return NextResponse.json({ error: "Invalid registration type" }, { status: 400 });
  } catch {
    return NextResponse.json({ error: "Registration failed" }, { status: 500 });
  }
};

interface CompanyRegistrationBody {
  email: string;
  password: string;
  fullName: string;
  organizationName: string;
  companySecret: string;
}

const handleCompanyRegistration = async (body: CompanyRegistrationBody) => {
  const { email, password, fullName, organizationName, companySecret } = body;

  if (!validateCompanySecret(companySecret)) {
    return NextResponse.json({ error: "Invalid company registration code" }, { status: 400 });
  }

  const { data: authData, error: authError } = await adminServices.auth.createUser({
    email,
    password,
  });

  if (authError || !authData.user) {
    return NextResponse.json(
      { error: authError?.message || "Failed to create account" },
      { status: 400 }
    );
  }

  const { data: orgData, error: orgError } =
    await adminServices.organizations.create(organizationName);

  if (orgError || !orgData) {
    await adminServices.auth.deleteUser(authData.user.id);
    return NextResponse.json(
      { error: orgError?.message || "Failed to create organization" },
      { status: 400 }
    );
  }

  const { error: userError } = await adminServices.users.create({
    userId: authData.user.id,
    fullName,
    orgId: orgData.id,
    role: "admin",
  });

  if (userError) {
    await adminServices.organizations.delete(orgData.id);
    await adminServices.auth.deleteUser(authData.user.id);
    return NextResponse.json(
      { error: userError.message || "Failed to create user profile" },
      { status: 400 }
    );
  }

  return NextResponse.json({ success: true });
};

interface InviteRegistrationBody {
  email: string;
  password: string;
  fullName: string;
  inviteToken: string;
}

const handleInviteRegistration = async (body: InviteRegistrationBody) => {
  const { email, password, fullName, inviteToken } = body;

  const tokenHash = hashToken(inviteToken);
  const { data: invite, error: inviteError } =
    await adminServices.invites.getByTokenHash(tokenHash);

  if (inviteError || !invite) {
    return NextResponse.json({ error: "Invalid or expired invitation" }, { status: 400 });
  }

  if (new Date(invite.expires_at) < new Date()) {
    return NextResponse.json({ error: "Invitation has expired" }, { status: 400 });
  }

  if (invite.email.toLowerCase() !== email.toLowerCase()) {
    return NextResponse.json({ error: "Email does not match invitation" }, { status: 400 });
  }

  const { data: authData, error: authError } = await adminServices.auth.createUser({
    email,
    password,
  });

  if (authError || !authData.user) {
    return NextResponse.json(
      { error: authError?.message || "Failed to create account" },
      { status: 400 }
    );
  }

  const { error: userError } = await adminServices.users.create({
    userId: authData.user.id,
    fullName,
    orgId: invite.org_id,
    role: invite.role,
  });

  if (userError) {
    await adminServices.auth.deleteUser(authData.user.id);
    return NextResponse.json(
      { error: userError.message || "Failed to create user profile" },
      { status: 400 }
    );
  }

  await adminServices.invites.markAsUsed(invite.id);

  return NextResponse.json({ success: true });
};
