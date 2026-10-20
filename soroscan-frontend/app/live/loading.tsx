import { Skeleton, SkeletonText } from '@/components/ui/skeleton';

export default function LiveLoading() {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Loading live event stream"
      className="min-h-screen bg-terminal-black text-terminal-green font-terminal-mono p-4 sm:p-8 flex flex-col"
    >
      <span className="sr-only">Loading live event stream</span>

      {/* Top Header Control Bar Skeleton */}
      <div className="flex flex-col gap-4 mb-4 border-b border-terminal-green/30 pb-4 shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Skeleton width={24} height={24} variant="circle" animation="pulse" />
            <div className="space-y-1">
              <SkeletonText
                lines={2}
                width={360}
                lineHeight={18}
                gap={8}
                lineWidths={['55%', '90%']}
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Skeleton width={120} height={36} animation="pulse" />
            <Skeleton width={130} height={36} animation="pulse" />
            <Skeleton width={100} height={36} animation="pulse" />
          </div>
        </div>

        {/* Filter Controls Bar Skeleton */}
        <div className="flex flex-wrap items-center gap-3 pt-2">
          <Skeleton width={60} height={28} animation="pulse" />
          <Skeleton width={180} height={28} animation="pulse" />
          <Skeleton width={140} height={28} animation="pulse" />
          <Skeleton width={130} height={28} animation="pulse" />
          <div className="ml-auto">
            <Skeleton width={110} height={20} animation="pulse" />
          </div>
        </div>
      </div>

      {/* Main Stream Console Window Skeleton */}
      <div
        className="flex-1 overflow-hidden rounded border border-terminal-green/30 bg-terminal-dark/80 p-4 space-y-3"
        style={{ minHeight: '360px' }}
      >
        {Array.from({ length: 4 }, (_, idx) => (
          <div
            key={idx}
            className="rounded border border-terminal-green/15 bg-terminal-black/60 p-3 space-y-3"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Skeleton width={70} height={22} animation="pulse" />
                <Skeleton width={110} height={16} animation="pulse" />
                <Skeleton width={160} height={16} animation="pulse" />
              </div>
              <Skeleton width={80} height={16} animation="pulse" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <Skeleton width="80%" height={14} animation="pulse" />
              <Skeleton width="60%" height={14} animation="pulse" />
            </div>
            <div className="pt-2 border-t border-terminal-green/5">
              <Skeleton width="90%" height={14} animation="pulse" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
