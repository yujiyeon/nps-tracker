import { NextRequest, NextResponse } from 'next/server'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl
  const qs = searchParams.toString()

  const upstream = `${API_BASE}/api/investor-recommendations/top${qs ? `?${qs}` : ''}`

  const res = await fetch(upstream, { cache: 'no-store' })
  const data = await res.json()

  return NextResponse.json(data, { status: res.status })
}
