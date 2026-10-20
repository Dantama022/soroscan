import { Skeleton, SkeletonCard, SkeletonText } from '@/components/ui/skeleton';

export default function AlertsLoading() {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Loading alerts"
      className="min-h-screen bg-terminal-black p-8 text-terminal-green font-terminal-mono"
    >
      <span className="sr-only">Loading alerts</span>

      <div className="mx-auto max-w-5xl space-y-6">
        {/* Header */}
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-2">
            <Skeleton width={100} height={14} animation="pulse" />
            <Skeleton width={260} height={32} animation="pulse" />
            <Skeleton width={380} height={16} animation="pulse" />
          </div>

          <Skeleton width={140} height={40} animation="pulse" />
        </header>

        {/* Templates section skeleton */}
        <section className="rounded border border-terminal-green/20 p-4 space-y-3">
          <SkeletonText lines={1} width={120} lineHeight={14} />
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {Array.from({ length: 3 }, (_, i) => (
              <SkeletonCard
                key={i}
                showMedia={false}
                lines={2}
                height={90}
                animation="pulse"
              />
            ))}
          </div>
        </section>

        {/* Alert rules list */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <SkeletonText lines={1} width={140} lineHeight={16} />
            <Skeleton width={80} height={20} animation="pulse" />
          </div>

          <div className="space-y-3">
            {Array.from({ length: 4 }, (_, i) => (
              <div
                key={i}
                className="rounded border border-terminal-green/20 bg-terminal-dark/60 p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
              >
                <div className="space-y-2 flex-1">
                  <div className="flex items-center gap-2">
                    <Skeleton width={180} height={20} animation="pulse" />
                    <Skeleton width={60} height={20} animation="pulse" />
                  </div>
                  <Skeleton width={280} height={14} animation="pulse" />
                </div>
                <div className="flex items-center gap-3">
                  <Skeleton width={80} height={24} animation="pulse" />
                  <Skeleton width={44} height={24} animation="pulse" />
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
