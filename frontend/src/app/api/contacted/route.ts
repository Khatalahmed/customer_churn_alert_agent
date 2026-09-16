/**
 * Records outreach, by proxying to the service's POST /contacted.
 *
 * This is the only write the interface makes, and it is what closes the loop:
 * the contact log feeds the next scan's skip list, and the action log feeds
 * the uplift measurement. Without it the product can say who to act on but
 * never learns that anyone acted.
 *
 * It runs on the server, like every other call, so the service address stays
 * off the client.
 */
import { NextResponse } from "next/server";
import { revalidatePath } from "next/cache";

const BASE = process.env.CHURN_API_URL ?? "http://127.0.0.1:8000";

export async function POST(request: Request) {
  let userIds: unknown;
  try {
    ({ user_ids: userIds } = await request.json());
  } catch {
    return NextResponse.json({ error: "expected a JSON body" }, { status: 400 });
  }

  if (!Array.isArray(userIds) || userIds.some((id) => !Number.isInteger(id))) {
    return NextResponse.json(
      { error: "user_ids must be an array of integers" },
      { status: 400 },
    );
  }
  if (userIds.length === 0) {
    return NextResponse.json({ error: "no customers selected" }, { status: 400 });
  }

  try {
    const response = await fetch(`${BASE}/contacted`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ user_ids: userIds }),
    });
    if (!response.ok) {
      const detail = await response.text().catch(() => "");
      return NextResponse.json(
        { error: detail.slice(0, 200) || "the service refused the request" },
        { status: response.status },
      );
    }
    const body = await response.json();
    // The worklist skips recently contacted customers, so its cached copy is
    // wrong the moment this succeeds.
    revalidatePath("/worklist");
    revalidatePath("/dashboard");
    return NextResponse.json(body);
  } catch {
    return NextResponse.json(
      { error: `Cannot reach the churn service at ${BASE}` },
      { status: 503 },
    );
  }
}
