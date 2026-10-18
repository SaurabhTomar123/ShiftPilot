import { fixtureResponse } from '@/api/fixture-gateway';

async function handler(request: Request, { params }: { params: Promise<{ segments: string[] }> }) {
  const { segments } = await params;
  const query = new URL(request.url).search;
  return fixtureResponse(`/${segments.join('/')}${query}`, request);
}

export { handler as GET, handler as POST, handler as PUT, handler as PATCH };
