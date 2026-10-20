import {
  Skeleton,
  SkeletonCard,
  SkeletonChart,
  SkeletonTable,
  SkeletonText,
} from '@/components/ui/skeleton';

export default function AdminLoading() {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Loading admin dashboard"
      className="min-h-screen bg-terminal-black p-4 font-terminal-mono sm:p-8"
    >
      <span className="sr-only">Loading admin dashboard</span>

      <div className="mx-auto max-w-7xl space-y-6">
        {/* Header toolbar */}
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <SkeletonText
            lines={2}
            width={380}
            lineHeight={18}
            gap={10}
            lineWidths={['60%', '100%']}
          />

          <div className="flex gap-2">
            <Skeleton width={110} height={38} animation="pulse" />
            <Skeleton width={130} height={38} animation="pulse" />
          </div>
        </header>

        {/* Metrics cards grid */}
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, index) => (
            <SkeletonCard
              key={index}
              showMedia={false}
              lines={1}
              height={110}
              animation="pulse"
              animationSpeed="normal"
            />
          ))}
        </section>

        {/* Chart section */}
        <section className="space-y-2 rounded-lg border border-terminal-green/20 p-4">
          <SkeletonText lines={1} width={200} lineHeight={16} />
          <SkeletonChart height={220} bars={12} animation="pulse" animationSpeed="normal" />
        </section>

        {/* Data table section */}
        <section className="space-y-4 rounded-lg border border-terminal-green/20 p-4">
          <div className="flex items-center justify-between">
            <SkeletonText lines={1} width={180} lineHeight={18} />
            <Skeleton width={100} height={32} animation="pulse" />
          </div>

          <SkeletonTable
            rows={6}
            columns={5}
            rowHeight={18}
            animation="pulse"
            animationSpeed="normal"
          />
        </section>
      </div>
    </div>
  );
}
