import { Skeleton, SkeletonTable, SkeletonText } from '@/components/ui/skeleton';

export default function ReportsLoading() {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Loading report builder"
      className="min-h-screen bg-terminal-black p-8 text-terminal-green font-terminal-mono"
    >
      <span className="sr-only">Loading report builder</span>

      <div className="mx-auto max-w-6xl space-y-6">
        {/* Header */}
        <header className="space-y-2">
          <Skeleton width={120} height={14} animation="pulse" />
          <Skeleton width={320} height={32} animation="pulse" />
          <Skeleton width={440} height={16} animation="pulse" />
        </header>

        {/* Filters Section */}
        <section className="grid grid-cols-1 md:grid-cols-4 gap-4 rounded border border-terminal-green/20 p-4">
          <Skeleton width="100%" height={40} animation="pulse" />
          <Skeleton width="100%" height={40} animation="pulse" />
          <Skeleton width="100%" height={40} animation="pulse" />
          <div className="self-center">
            <Skeleton width={90} height={20} animation="pulse" />
          </div>
        </section>

        {/* Export Buttons */}
        <section className="flex gap-2 flex-wrap">
          <Skeleton width={100} height={38} animation="pulse" />
          <Skeleton width={100} height={38} animation="pulse" />
          <Skeleton width={120} height={38} animation="pulse" />
        </section>

        {/* Column Selection */}
        <section className="rounded border border-terminal-green/20 p-4 space-y-3">
          <SkeletonText lines={1} width={80} lineHeight={14} />
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 5 }, (_, i) => (
              <Skeleton key={i} width={90} height={28} animation="pulse" />
            ))}
          </div>
        </section>

        {/* Data Preview Table */}
        <section className="rounded border border-terminal-green/20 overflow-hidden">
          <SkeletonTable
            rows={5}
            columns={5}
            rowHeight={20}
            animation="pulse"
            animationSpeed="normal"
          />
        </section>
      </div>
    </div>
  );
}
