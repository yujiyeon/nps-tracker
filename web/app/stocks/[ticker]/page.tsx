import { notFound } from 'next/navigation'
import { getStockDetail } from '@/lib/api'
import { StockDetail } from '@/components/stock-detail'

interface Props {
  params: Promise<{ ticker: string }>
}

export default async function StockDetailPage({ params }: Props) {
  const { ticker } = await params

  let data = null
  try {
    data = await getStockDetail(ticker)
  } catch {
    notFound()
  }

  if (!data) notFound()

  return <StockDetail ticker={ticker} initialData={data} />
}
