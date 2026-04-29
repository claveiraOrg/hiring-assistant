import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const HIREMATCH_API_URL = process.env.HIREMATCH_API_URL ?? "http://localhost:8001";
const HIREMATCH_API_KEY = process.env.HIREMATCH_API_KEY ?? "dev-secret-key";

async function proxy(req: NextRequest, params: { path: string[] }) {
  const path = params.path.join("/");
  const url = `${HIREMATCH_API_URL}/${path}`;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    "X-API-Key": HIREMATCH_API_KEY,
  };

  const init: RequestInit = { method: req.method, headers };

  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.text();
  }

  const upstream = await fetch(url, init);
  const body = await upstream.text();

  return new NextResponse(body, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("Content-Type") ?? "application/json" },
  });
}

export async function GET(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params);
}

export async function POST(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params);
}
