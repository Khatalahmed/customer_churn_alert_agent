/**
 * Server-side proxy for the command palette's customer search.
 *
 * The palette runs in the browser and needs live results as someone types.
 * It calls this route, which calls FastAPI: the service's address stays on
 * the server, so nothing about the backend is exposed to the client.
 */
import { NextResponse } from "next/server";

import { api } from "@/lib/api";

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const query = params.get("q") ?? "";
  const limit = Number(params.get("limit") ?? 6);

  if (query.trim().length < 2) {
    return NextResponse.json({ customers: [] });
  }
  try {
    const body = await api.customers(query, Number.isFinite(limit) ? limit : 6);
    return NextResponse.json({ customers: body.customers });
  } catch {
    // A dead search box must not raise: the palette still navigates to pages.
    return NextResponse.json({ customers: [] }, { status: 200 });
  }
}
